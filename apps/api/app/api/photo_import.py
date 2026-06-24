"""P100 photo import API."""

from __future__ import annotations

import logging
import os
import socket

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.photo_import import (
    PhotoImportAddAllResponse,
    PhotoImportChooseMatchPayload,
    PhotoImportCatalogMatchBatchPayload,
    PhotoImportConfirmPayload,
    PhotoImportConfirmResponse,
    PhotoImportDetectedBookRead,
    PhotoImportFolderQueueStatusRead,
    PhotoImportHeartbeatPayload,
    PhotoImportImageRead,
    PhotoImportImageVerificationRead,
    PhotoImportCandidateRead,
    PhotoImportDetectionCandidatesResponse,
    PhotoImportProcessPendingResponse,
    PhotoImportFolderVisionResetResponse,
    PhotoImportSelectCandidatePayload,
    PhotoImportSessionCreatePayload,
    PhotoImportSessionRead,
    PhotoImportVisionReadFeedbackPayload,
    PhotoImportVisionReadInventoryResponse,
    PhotoImportVisionReadPayload,
    PhotoImportVisionReadUpdatePayload,
    PhotoImportVisionSandboxMetricsRead,
    PhotoImportVisionSandboxStatusRead,
)
from app.core.config import get_settings
from app.services.ops_admin import ensure_ops_admin_access
from app.services.photo_import_sandbox_flags import assert_photo_import_matching_allowed, photo_import_vision_sandbox_enabled
from app.services.photo_import_detection_service import (
    confirm_detection,
    confirm_session_books,
    list_detection_candidates_debug,
    list_session_detections,
    reject_detection,
    select_candidate,
)
from app.services.photo_import_crop_service import resolve_crop_abs_path
from app.models.photo_import import PhotoImportDetectedBook, PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_session_service import (
    complete_session,
    create_photo_import_session,
    get_session_by_token_or_404,
    heartbeat_session,
    session_to_read,
    assert_session_owner,
)
from app.services.comic_vision_read_mode import normalize_vision_read_mode
from app.services.photo_import_folder_pipeline_service import (
    folder_queue_status,
    kick_folder_process_pending,
    reset_folder_session_vision_for_rerun,
)
from app.services.photo_import_upload_service import upload_barcode_companion_image, upload_session_images
from app.services.photo_import_vision_stream_service import iter_vision_read_sse
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.photo_import_vision_accuracy_service import build_vision_sandbox_accuracy_report
from app.services.photo_import_vision_read_api_service import vision_read_to_payload
from app.services.photo_import_vision_read_actions_service import (
    add_all_session_reads_to_inventory,
    add_vision_read_to_inventory,
    catalog_match_session_reads,
    catalog_match_vision_read,
    cancel_vision_read_catalog_match,
    validate_comicvine_ondemand_vision_read,
    choose_vision_read_match,
    rematch_vision_read,
    reread_vision_read,
    update_vision_read_fields,
)
from app.services.photo_import_catalog_match_service import rematch_stale_automatic_catalog_link
from app.services.photo_import_vision_sandbox_service import (
    backfill_missing_vision_reads_for_session,
    latest_vision_read_for_image,
    vision_reads_for_image,
    vision_reads_for_session,
)

logger = logging.getLogger(__name__)

photo_import_router = APIRouter(prefix="/api/v1/photo-import", tags=["Photo Import (P100)"])


def attach_photo_import_layer(app: FastAPI) -> None:
    app.include_router(photo_import_router)


@photo_import_router.get("/admin/vision-sandbox-status", response_model=PhotoImportVisionSandboxStatusRead)
def vision_sandbox_status_endpoint() -> PhotoImportVisionSandboxStatusRead:
    """P100-26 temporary diagnostic — no auth until sandbox activation is verified in production."""
    settings = get_settings()
    return PhotoImportVisionSandboxStatusRead(
        photo_import_vision_sandbox=bool(settings.photo_import_vision_sandbox),
        photo_import_vision_sandbox_model=settings.photo_import_vision_sandbox_model,
        environment_value=os.getenv("PHOTO_IMPORT_VISION_SANDBOX"),
        hostname=socket.gethostname(),
    )


@photo_import_router.post("/sessions", response_model=PhotoImportSessionRead)
def create_session_endpoint(
    payload: PhotoImportSessionCreatePayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportSessionRead:
    assert current_user.id is not None
    return create_photo_import_session(
        session,
        owner_user_id=int(current_user.id),
        source_device=(payload.source_device if payload else None) or None,
        capture_mode=payload.capture_mode if payload else None,
    )


@photo_import_router.get(
    "/sessions/{token}/folder-queue",
    response_model=PhotoImportFolderQueueStatusRead,
)
def folder_queue_status_endpoint(
    token: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportFolderQueueStatusRead:
    assert current_user.id is not None
    import_row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(import_row, owner_user_id=int(current_user.id))
    return folder_queue_status(session, import_row=import_row)


@photo_import_router.post(
    "/sessions/{token}/folder-process-pending",
    response_model=PhotoImportProcessPendingResponse,
)
def folder_process_pending_endpoint(
    token: str,
    limit: int = Query(default=2, ge=1, le=3),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportProcessPendingResponse:
    assert current_user.id is not None
    import_row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(import_row, owner_user_id=int(current_user.id))
    return kick_folder_process_pending(
        session,
        token=token,
        owner_user_id=int(current_user.id),
        limit=limit,
    )


@photo_import_router.post(
    "/sessions/{token}/folder-reset-vision",
    response_model=PhotoImportFolderVisionResetResponse,
)
def folder_reset_vision_endpoint(
    token: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportFolderVisionResetResponse:
    """Clear bad GPT reads and mark photos uploaded again for accurate folder re-processing."""
    assert current_user.id is not None
    import_row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(import_row, owner_user_id=int(current_user.id))
    reset_count = reset_folder_session_vision_for_rerun(
        session,
        token=token,
        owner_user_id=int(current_user.id),
    )
    queue = folder_queue_status(session, import_row=import_row)
    return PhotoImportFolderVisionResetResponse(images_reset=reset_count, queue=queue)


@photo_import_router.get("/sessions/{token}", response_model=PhotoImportSessionRead)
def get_session_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> PhotoImportSessionRead:
    row = get_session_by_token_or_404(session, token=token)
    payload = session_to_read(row)
    if payload.vision_sandbox:
        logger.info(
            "photo_import.session vision_sandbox=true session_id=%s token_prefix=%s",
            payload.id,
            token[:8],
        )
    return payload


@photo_import_router.post("/sessions/{token}/heartbeat", response_model=PhotoImportSessionRead)
def heartbeat_endpoint(
    token: str,
    payload: PhotoImportHeartbeatPayload | None = None,
    session: Session = Depends(get_session),
) -> PhotoImportSessionRead:
    return heartbeat_session(
        session,
        token=token,
        source_device=payload.source_device if payload else None,
        capture_mode=payload.capture_mode if payload else None,
    )


@photo_import_router.post("/sessions/{token}/complete", response_model=PhotoImportSessionRead)
def complete_session_endpoint(
    token: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportSessionRead:
    assert current_user.id is not None
    return complete_session(session, owner_user_id=int(current_user.id), token=token)


@photo_import_router.post("/sessions/{token}/images", response_model=list[PhotoImportImageRead])
async def upload_images_endpoint(
    token: str,
    images: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
) -> list[PhotoImportImageRead]:
    """Save uploads; clients should call vision-stream (quick) per cover image for GPT reads."""
    saved, _pending_ids = await upload_session_images(session, token=token, files=images)
    return saved


@photo_import_router.post(
    "/sessions/{token}/images/{cover_image_id}/barcode-companion",
    response_model=PhotoImportImageRead,
)
async def upload_barcode_companion_endpoint(
    token: str,
    cover_image_id: int,
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> PhotoImportImageRead:
    """Upload a UPC close-up linked to an existing cover photo (no GPT on this file)."""
    return await upload_barcode_companion_image(
        session,
        token=token,
        cover_image_id=cover_image_id,
        upload=image,
    )


@photo_import_router.get("/sessions/{token}/detections", response_model=list[PhotoImportDetectedBookRead])
def list_detections_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> list[PhotoImportDetectedBookRead]:
    sandbox = photo_import_vision_sandbox_enabled()
    logger.warning(
        "photo_import.detections_called token=%s vision_sandbox=%s",
        token,
        sandbox,
    )
    if sandbox:
        return []
    return list_session_detections(session, token=token)


@photo_import_router.get("/sessions/{token}/images/{image_id}/original")
def get_session_original_image_endpoint(
    token: str,
    image_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    import_row = get_session_by_token_or_404(session, token=token)
    image = session.get(PhotoImportImage, image_id)
    if image is None or int(image.session_id) != int(import_row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import image not found")
    abs_path = resolve_photo_import_storage_path(image.storage_path, image_id=image_id)
    if not abs_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original image not found")
    media = image.mime_type if image.mime_type.startswith("image/") else "image/jpeg"
    return FileResponse(abs_path, media_type=media, filename=image.original_filename or f"photo-import-{image_id}.jpg")


@photo_import_router.get("/detections/{detection_id}/candidates", response_model=PhotoImportDetectionCandidatesResponse)
def list_candidates_endpoint(
    detection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportDetectionCandidatesResponse:
    assert current_user.id is not None
    assert_photo_import_matching_allowed()
    return list_detection_candidates_debug(session, owner_user_id=int(current_user.id), detection_id=detection_id)


@photo_import_router.get("/detections/{detection_id}/crop-image")
def get_detection_crop_image_endpoint(
    detection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    assert current_user.id is not None
    det = session.get(PhotoImportDetectedBook, detection_id)
    if det is None or int(det.user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    abs_path = resolve_crop_abs_path(det.crop_path)
    if abs_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop image not found")
    return FileResponse(abs_path, media_type="image/jpeg", filename=f"photo-import-{detection_id}.jpg")


@photo_import_router.post("/detections/{detection_id}/select-candidate", response_model=PhotoImportDetectedBookRead)
def select_candidate_endpoint(
    detection_id: int,
    payload: PhotoImportSelectCandidatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportDetectedBookRead:
    assert current_user.id is not None
    assert_photo_import_matching_allowed()
    return select_candidate(
        session,
        owner_user_id=int(current_user.id),
        detection_id=detection_id,
        candidate_id=payload.candidate_id,
    )


@photo_import_router.post("/detections/{detection_id}/reject", response_model=PhotoImportDetectedBookRead)
def reject_detection_endpoint(
    detection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportDetectedBookRead:
    assert current_user.id is not None
    assert_photo_import_matching_allowed()
    return reject_detection(session, owner_user_id=int(current_user.id), detection_id=detection_id)


@photo_import_router.post("/detections/{detection_id}/confirm", response_model=PhotoImportDetectedBookRead)
def confirm_detection_endpoint(
    detection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportDetectedBookRead:
    assert current_user.id is not None
    assert_photo_import_matching_allowed()
    return confirm_detection(session, owner_user_id=int(current_user.id), detection_id=detection_id)


@photo_import_router.post("/sessions/{token}/confirm", response_model=PhotoImportConfirmResponse)
def confirm_session_endpoint(
    token: str,
    payload: PhotoImportConfirmPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportConfirmResponse:
    assert current_user.id is not None
    assert_photo_import_matching_allowed()
    return confirm_session_books(
        session,
        owner_user_id=int(current_user.id),
        token=token,
        payload=payload,
    )


@photo_import_router.get("/vision-read/{image_id}", response_model=PhotoImportVisionReadPayload)
def get_vision_read_endpoint(
    image_id: int,
    session_token: str,
    session: Session = Depends(get_session),
) -> PhotoImportVisionReadPayload:
    import_row = get_session_by_token_or_404(session, token=session_token)
    image = session.get(PhotoImportImage, image_id)
    if image is None or int(image.session_id) != int(import_row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import image not found")
    row = latest_vision_read_for_image(session, image_id=image_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision read not found for image")
    return vision_read_to_payload(row)


@photo_import_router.get("/sessions/{token}/vision-reads", response_model=list[PhotoImportVisionReadPayload])
def list_session_vision_reads_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> list[PhotoImportVisionReadPayload]:
    import_row = get_session_by_token_or_404(session, token=token)
    session_id = int(import_row.id or 0)
    backfill_missing_vision_reads_for_session(session, session_id=session_id)
    rows = vision_reads_for_session(session, session_id=session_id)
    for row in rows:
        rematch_stale_automatic_catalog_link(session, row)
    session.commit()
    # For reads with no local catalog match, pull the volume from ComicVine in the background
    # and re-match. Bounded + de-duplicated per session, so polling this endpoint progressively
    # fills in matches without blocking the response. No-op without COMICVINE_API_KEY.
    if any(r.catalog_issue_id is None for r in rows):
        from app.services.photo_import_comicvine_ondemand_service import (
            kick_comicvine_ondemand_backfill,
        )

        kick_comicvine_ondemand_backfill(session_id=session_id)
    return [vision_read_to_payload(r) for r in rows]


@photo_import_router.get(
    "/sessions/{token}/images/{image_id}/verification",
    response_model=PhotoImportImageVerificationRead,
)
def get_image_verification_endpoint(
    token: str,
    image_id: int,
    session: Session = Depends(get_session),
) -> PhotoImportImageVerificationRead:
    """GPT-only verification state for one upload (no catalog matching)."""
    import_row = get_session_by_token_or_404(session, token=token)
    image = session.get(PhotoImportImage, image_id)
    if image is None or int(image.session_id) != int(import_row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import image not found")
    rows = vision_reads_for_image(session, image_id=image_id)
    return PhotoImportImageVerificationRead(
        image_id=image_id,
        image_status=str(image.status),
        reads=[vision_read_to_payload(r) for r in rows],
    )


@photo_import_router.post("/sessions/{token}/images/{image_id}/vision-stream")
def vision_stream_endpoint(
    token: str,
    image_id: int,
    session: Session = Depends(get_session),
    mode: str = Query(default="quick", description="quick (default) or accurate"),
    force: bool = Query(default=False, description="Re-run even if already processed"),
) -> StreamingResponse:
    """Stream GPT vision tokens (ChatGPT-style), then persist vision reads."""
    import_row = get_session_by_token_or_404(session, token=token)
    image = session.get(PhotoImportImage, image_id)
    if image is None or int(image.session_id) != int(import_row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import image not found")
    read_mode = normalize_vision_read_mode(mode)

    def generate():
        from app.db.session import get_engine

        with Session(get_engine()) as db:
            for chunk in iter_vision_read_sse(
                db,
                image_id=image_id,
                mode=read_mode,
                force=force,
            ):
                yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@photo_import_router.post("/vision-read/{read_id}/catalog-match", response_model=PhotoImportVisionReadPayload)
def catalog_match_vision_read_endpoint(
    read_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = catalog_match_vision_read(session, read_id=read_id, owner_user_id=int(current_user.id))
    return vision_read_to_payload(row)


@photo_import_router.post(
    "/vision-read/{read_id}/validate-ondemand",
    response_model=PhotoImportVisionReadPayload,
)
def validate_ondemand_vision_read_endpoint(
    read_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = validate_comicvine_ondemand_vision_read(
        session,
        read_id=read_id,
        owner_user_id=int(current_user.id),
    )
    return vision_read_to_payload(row)


@photo_import_router.post(
    "/vision-read/{read_id}/cancel-catalog-match",
    response_model=PhotoImportVisionReadPayload,
)
def cancel_catalog_match_vision_read_endpoint(
    read_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = cancel_vision_read_catalog_match(
        session,
        read_id=read_id,
        owner_user_id=int(current_user.id),
    )
    return vision_read_to_payload(row)


@photo_import_router.post(
    "/sessions/{token}/catalog-match",
    response_model=list[PhotoImportVisionReadPayload],
)
def catalog_match_batch_endpoint(
    token: str,
    payload: PhotoImportCatalogMatchBatchPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[PhotoImportVisionReadPayload]:
    assert current_user.id is not None
    rows = catalog_match_session_reads(
        session,
        session_token=token,
        owner_user_id=int(current_user.id),
        read_ids=payload.read_ids,
    )
    return [vision_read_to_payload(r) for r in rows]


@photo_import_router.post("/vision-read/{read_id}/feedback", response_model=PhotoImportVisionReadPayload)
def vision_read_feedback_endpoint(
    read_id: int,
    payload: PhotoImportVisionReadFeedbackPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = session.get(PhotoImportVisionRead, read_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision read not found")
    import_row = session.get(PhotoImportSession, int(row.session_id))
    if import_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision read not found")
    assert_session_owner(import_row, owner_user_id=int(current_user.id))
    row.is_correct = payload.is_correct
    row.feedback_notes = (payload.feedback_notes or "").strip() or None
    session.add(row)
    session.commit()
    session.refresh(row)
    return vision_read_to_payload(row)


@photo_import_router.patch("/vision-read/{read_id}", response_model=PhotoImportVisionReadPayload)
def update_vision_read_endpoint(
    read_id: int,
    payload: PhotoImportVisionReadUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = update_vision_read_fields(
        session,
        read_id=read_id,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    return vision_read_to_payload(row)


@photo_import_router.post(
    "/vision-read/{read_id}/add-to-inventory",
    response_model=PhotoImportVisionReadInventoryResponse,
)
def add_vision_read_to_inventory_endpoint(
    read_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadInventoryResponse:
    assert current_user.id is not None
    return add_vision_read_to_inventory(
        session,
        read_id=read_id,
        owner_user_id=int(current_user.id),
    )


@photo_import_router.post(
    "/vision-read/{read_id}/reread", response_model=list[PhotoImportVisionReadPayload]
)
def reread_vision_read_endpoint(
    read_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    mode: str = Query(default="accurate", description="accurate (default) or quick"),
) -> list[PhotoImportVisionReadPayload]:
    assert current_user.id is not None
    read_mode = normalize_vision_read_mode(mode)
    rows = reread_vision_read(
        session,
        read_id=read_id,
        owner_user_id=int(current_user.id),
        mode=read_mode,
    )
    return [vision_read_to_payload(r) for r in rows]


@photo_import_router.post("/vision-read/{read_id}/rematch", response_model=PhotoImportVisionReadPayload)
def rematch_vision_read_endpoint(
    read_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = rematch_vision_read(session, read_id=read_id, owner_user_id=int(current_user.id))
    return vision_read_to_payload(row)


@photo_import_router.post("/vision-read/{read_id}/choose-match", response_model=PhotoImportVisionReadPayload)
def choose_vision_read_match_endpoint(
    read_id: int,
    payload: PhotoImportChooseMatchPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionReadPayload:
    assert current_user.id is not None
    row = choose_vision_read_match(
        session,
        read_id=read_id,
        owner_user_id=int(current_user.id),
        catalog_issue_id=payload.catalog_issue_id,
    )
    return vision_read_to_payload(row)


@photo_import_router.post("/sessions/{token}/add-all", response_model=PhotoImportAddAllResponse)
def add_all_session_reads_endpoint(
    token: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportAddAllResponse:
    assert current_user.id is not None
    results = add_all_session_reads_to_inventory(
        session,
        session_token=token,
        owner_user_id=int(current_user.id),
    )
    total_copies = sum(r.created_count for r in results)
    return PhotoImportAddAllResponse(
        added_count=len(results),
        total_copies=total_copies,
        results=results,
    )


@photo_import_router.get("/admin/vision-sandbox/metrics", response_model=PhotoImportVisionSandboxMetricsRead)
def vision_sandbox_metrics_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportVisionSandboxMetricsRead:
    settings = get_settings()
    ensure_ops_admin_access(current_user, settings)
    report = build_vision_sandbox_accuracy_report(session)
    return PhotoImportVisionSandboxMetricsRead(**report)
