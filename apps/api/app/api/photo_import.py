"""P100 photo import API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.photo_import import (
    PhotoImportConfirmPayload,
    PhotoImportConfirmResponse,
    PhotoImportDetectedBookRead,
    PhotoImportHeartbeatPayload,
    PhotoImportImageRead,
    PhotoImportCandidateRead,
    PhotoImportDetectionCandidatesResponse,
    PhotoImportSelectCandidatePayload,
    PhotoImportSessionCreatePayload,
    PhotoImportSessionRead,
)
from app.services.photo_import_detection_service import (
    confirm_detection,
    confirm_session_books,
    list_detection_candidates_debug,
    list_session_detections,
    reject_detection,
    select_candidate,
)
from app.services.photo_import_crop_service import resolve_crop_abs_path
from app.models.photo_import import PhotoImportDetectedBook
from app.services.photo_import_session_service import (
    complete_session,
    create_photo_import_session,
    get_session_by_token_or_404,
    heartbeat_session,
    session_to_read,
    assert_session_owner,
)
from app.services.photo_import_upload_service import upload_session_images

photo_import_router = APIRouter(prefix="/api/v1/photo-import", tags=["Photo Import (P100)"])


def attach_photo_import_layer(app: FastAPI) -> None:
    app.include_router(photo_import_router)


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
        source_device=payload.source_device if payload else None,
        capture_mode=payload.capture_mode if payload else None,
    )


@photo_import_router.get("/sessions/{token}", response_model=PhotoImportSessionRead)
def get_session_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> PhotoImportSessionRead:
    row = get_session_by_token_or_404(session, token=token)
    return session_to_read(row)


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
    return await upload_session_images(session, token=token, files=images)


@photo_import_router.get("/sessions/{token}/detections", response_model=list[PhotoImportDetectedBookRead])
def list_detections_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> list[PhotoImportDetectedBookRead]:
    return list_session_detections(session, token=token)


@photo_import_router.get("/detections/{detection_id}/candidates", response_model=PhotoImportDetectionCandidatesResponse)
def list_candidates_endpoint(
    detection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportDetectionCandidatesResponse:
    assert current_user.id is not None
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
    return reject_detection(session, owner_user_id=int(current_user.id), detection_id=detection_id)


@photo_import_router.post("/detections/{detection_id}/confirm", response_model=PhotoImportDetectedBookRead)
def confirm_detection_endpoint(
    detection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportDetectedBookRead:
    assert current_user.id is not None
    return confirm_detection(session, owner_user_id=int(current_user.id), detection_id=detection_id)


@photo_import_router.post("/sessions/{token}/confirm", response_model=PhotoImportConfirmResponse)
def confirm_session_endpoint(
    token: str,
    payload: PhotoImportConfirmPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoImportConfirmResponse:
    assert current_user.id is not None
    return confirm_session_books(
        session,
        owner_user_id=int(current_user.id),
        token=token,
        payload=payload,
    )
