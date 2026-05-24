from fastapi import HTTPException
from redis.exceptions import RedisError
from rq.job import Job
from sqlmodel import Session

from app.db.session import get_engine
from app.models import CoverImageOcrResult, DraftImport, User
from app.schemas.cover_images import CoverImageOcrEnqueueResponse, CoverImageProcessingEnqueueResponse
from app.schemas.gmail import GmailSyncEnqueueResponse
from app.schemas.imports import DraftImportCreate
from app.schemas.jobs import ImportParseJobEnqueueResponse, ImportParseJobStatusResponse
from app.schemas.ops import OpsMetadataReenrichmentEnqueueResponse
from app.services.ai_order_parser import ensure_ai_parser_configured
from app.services.cover_images import (
    create_pending_cover_image_ocr_result,
    get_cover_entity_for_processing_by_ops_or_404,
    get_latest_cover_image_ocr_result_for_cover_or_409,
    get_cover_entity_for_processing_by_owner,
)
from app.services.gmail_ingestion import (
    GmailNotConnectedError,
    ensure_gmail_integration_configured,
    get_gmail_account_for_user,
)
from app.services.imports import serialize_import
from app.services.metadata_reenrichment import (
    enqueue_reenrichment_audit,
    get_draft_import_for_ops_or_404,
    get_inventory_copy_for_ops_or_404,
)
from app.services.ops_events import record_ops_event
from app.tasks.queue import (
    AI_PARSE_IMPORT_JOB_TYPE,
    COVER_IMAGE_OCR_JOB_ID_TEMPLATE,
    COVER_IMAGE_OCR_JOB_TYPE,
    COVER_IMAGE_PROCESS_JOB_TYPE,
    GMAIL_SYNC_JOB_TYPE,
    enqueue_ai_parse_import_job,
    enqueue_cover_image_ocr_job,
    enqueue_cover_image_process_job,
    enqueue_gmail_sync_job,
    enqueue_metadata_reenrich_job,
    fetch_job_by_id,
)


def _extract_job_error(job: Job) -> str | None:
    latest = job.latest_result()
    exc_string = latest.exc_string if latest is not None else None
    if not exc_string:
        return None

    lines = [line.strip() for line in exc_string.splitlines() if line.strip()]
    if not lines:
        return "Job failed"

    for line in reversed(lines):
        if line.startswith("app.services.ai_order_parser.AiOrderParserError: "):
            return line.split("AiOrderParserError: ", maxsplit=1)[1]
        if line.startswith("app.services.gmail_ingestion.GmailIntegrationError: "):
            return line.split("GmailIntegrationError: ", maxsplit=1)[1]
        if line.startswith("Exception: "):
            return line.split("Exception: ", maxsplit=1)[1]
        if line.startswith("ValueError: "):
            return line.split("ValueError: ", maxsplit=1)[1]

    return lines[-1]


def _enqueue_cover_image_ocr_after_validation(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
    draft_import_id: int | None,
    requested_via: str,
    queued_message: str,
    replay_of_ocr_result_id: int | None = None,
    replay_reason: str | None = None,
) -> CoverImageOcrEnqueueResponse:
    pending_result = create_pending_cover_image_ocr_result(
        session,
        cover_image_id=cover_image_id,
        replay_of_ocr_result_id=replay_of_ocr_result_id,
        replay_reason=replay_reason,
    )
    try:
        job = enqueue_cover_image_ocr_job(
            cover_image_id=cover_image_id,
            user_id=current_user.id,
            ocr_result_id=pending_result.id,
        )
    except RedisError as exc:
        pending_entity = session.get(CoverImageOcrResult, pending_result.id)
        if pending_entity is not None:
            session.delete(pending_entity)
            session.commit()
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    details: dict[str, object] = {
        "cover_image_id": cover_image_id,
        "ocr_result_id": pending_result.id,
        "requested_via": requested_via,
    }
    if replay_of_ocr_result_id is not None:
        details["replay_of_ocr_result_id"] = replay_of_ocr_result_id
    if replay_reason:
        details["replay_reason"] = replay_reason

    record_ops_event(
        event_type="cover_image_ocr",
        status="queued",
        user_id=current_user.id,
        job_id=job.id,
        queue_name=COVER_IMAGE_OCR_JOB_TYPE,
        draft_import_id=draft_import_id,
        message=queued_message,
        details=details,
    )
    return CoverImageOcrEnqueueResponse(
        job_id=job.id,
        status="queued",
        cover_image_id=cover_image_id,
        ocr_result_id=pending_result.id,
    )


def enqueue_import_parse_job_for_user(
    current_user: User,
    payload: DraftImportCreate,
) -> ImportParseJobEnqueueResponse:
    ensure_ai_parser_configured()

    try:
        job = enqueue_ai_parse_import_job(user_id=current_user.id, raw_text=payload.raw_text)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    return ImportParseJobEnqueueResponse(job_id=job.id, status="queued")


def get_import_parse_job_status_for_user(
    session: Session,
    current_user: User,
    job_id: str,
) -> ImportParseJobStatusResponse:
    try:
        job = fetch_job_by_id(job_id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if (
        job.meta.get("job_type") != AI_PARSE_IMPORT_JOB_TYPE
        or job.meta.get("user_id") != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get_status(refresh=True)
    result = job.result if isinstance(job.result, dict) else {}
    import_id = result.get("import_id")
    import_record = None

    if import_id is not None:
        draft_import = session.get(DraftImport, import_id)
        if draft_import is not None and draft_import.user_id == current_user.id:
            import_record = serialize_import(session, draft_import)

    return ImportParseJobStatusResponse(
        job_id=job.id,
        job_type=job.meta["job_type"],
        status=status,
        import_id=import_id,
        import_record=import_record,
        error=_extract_job_error(job),
        enqueued_at=job.enqueued_at,
        started_at=job.started_at,
        ended_at=job.ended_at,
    )


def enqueue_gmail_sync_job_for_user(current_user: User) -> GmailSyncEnqueueResponse:
    ensure_gmail_integration_configured()
    with Session(get_engine()) as session:
        account = get_gmail_account_for_user(session, current_user)

    if account is None or account.access_token_encrypted is None:
        raise GmailNotConnectedError("Connect a Gmail account before syncing receipts.")

    try:
        job = enqueue_gmail_sync_job(
            user_id=current_user.id,
            gmail_account_id=account.id,
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    return GmailSyncEnqueueResponse(job_id=job.id, status="queued")


def enqueue_cover_image_processing_for_user(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageProcessingEnqueueResponse:
    job_id = f"cover-image-process-{cover_image_id}"
    existing_before = fetch_job_by_id(job_id)
    cover = get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    try:
        job = enqueue_cover_image_process_job(cover_image_id=cover_image_id, user_id=current_user.id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    record_ops_event(
        event_type="cover_image_process",
        status="queued",
        user_id=current_user.id,
        job_id=job.id,
        queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
        draft_import_id=cover.draft_import_id,
        message="Cover image processing queued",
        details={"cover_image_id": cover_image_id, "requested_via": "owner_route"},
    )
    return CoverImageProcessingEnqueueResponse(
        job_id=job.id,
        status=(
            "already_queued"
            if existing_before is not None
            and existing_before.get_status(refresh=True) in {"queued", "started", "scheduled", "deferred"}
            else "queued"
        ),
        cover_image_id=cover_image_id,
    )


def enqueue_cover_image_processing_for_ops(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageProcessingEnqueueResponse:
    job_id = f"cover-image-process-{cover_image_id}"
    existing_before = fetch_job_by_id(job_id)
    cover = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    try:
        job = enqueue_cover_image_process_job(cover_image_id=cover_image_id, user_id=current_user.id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    record_ops_event(
        event_type="cover_image_process",
        status="queued",
        user_id=current_user.id,
        job_id=job.id,
        queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
        draft_import_id=cover.draft_import_id,
        message="Cover image processing queued by ops",
        details={"cover_image_id": cover_image_id, "requested_via": "ops_route"},
    )
    return CoverImageProcessingEnqueueResponse(
        job_id=job.id,
        status=(
            "already_queued"
            if existing_before is not None
            and existing_before.get_status(refresh=True) in {"queued", "started", "scheduled", "deferred"}
            else "queued"
        ),
        cover_image_id=cover_image_id,
    )


def enqueue_cover_image_ocr_for_user(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageOcrEnqueueResponse:
    job_id = COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=cover_image_id)
    existing_before = fetch_job_by_id(job_id)
    cover = get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    already_active = (
        existing_before is not None
        and existing_before.get_status(refresh=True) in {"queued", "started", "scheduled", "deferred"}
    )
    if already_active:
        return CoverImageOcrEnqueueResponse(
            job_id=existing_before.id,
            status="already_queued",
            cover_image_id=cover_image_id,
            ocr_result_id=None,
        )
    return _enqueue_cover_image_ocr_after_validation(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        draft_import_id=cover.draft_import_id,
        requested_via="owner_route",
        queued_message="Cover image OCR queued",
    )


def enqueue_cover_image_ocr_for_ops(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageOcrEnqueueResponse:
    job_id = COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=cover_image_id)
    existing_before = fetch_job_by_id(job_id)
    cover = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    already_active = (
        existing_before is not None
        and existing_before.get_status(refresh=True) in {"queued", "started", "scheduled", "deferred"}
    )
    if already_active:
        return CoverImageOcrEnqueueResponse(
            job_id=existing_before.id,
            status="already_queued",
            cover_image_id=cover_image_id,
            ocr_result_id=None,
        )
    return _enqueue_cover_image_ocr_after_validation(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        draft_import_id=cover.draft_import_id,
        requested_via="ops_route",
        queued_message="Cover image OCR queued by ops",
    )


def enqueue_cover_image_ocr_replay_for_user(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
    replay_reason: str | None = None,
) -> CoverImageOcrEnqueueResponse:
    job_id = COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=cover_image_id)
    existing_before = fetch_job_by_id(job_id)
    cover = get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    already_active = (
        existing_before is not None
        and existing_before.get_status(refresh=True) in {"queued", "started", "scheduled", "deferred"}
    )
    if already_active:
        return CoverImageOcrEnqueueResponse(
            job_id=existing_before.id,
            status="already_queued",
            cover_image_id=cover_image_id,
            ocr_result_id=None,
        )
    replay_of = get_latest_cover_image_ocr_result_for_cover_or_409(session, cover_image_id)
    return _enqueue_cover_image_ocr_after_validation(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        draft_import_id=cover.draft_import_id,
        requested_via="owner_replay_route",
        queued_message="Cover image OCR replay queued",
        replay_of_ocr_result_id=replay_of.id,
        replay_reason=replay_reason,
    )


def enqueue_cover_image_ocr_replay_for_ops(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
    replay_reason: str | None = None,
) -> CoverImageOcrEnqueueResponse:
    job_id = COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=cover_image_id)
    existing_before = fetch_job_by_id(job_id)
    cover = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    already_active = (
        existing_before is not None
        and existing_before.get_status(refresh=True) in {"queued", "started", "scheduled", "deferred"}
    )
    if already_active:
        return CoverImageOcrEnqueueResponse(
            job_id=existing_before.id,
            status="already_queued",
            cover_image_id=cover_image_id,
            ocr_result_id=None,
        )
    replay_of = get_latest_cover_image_ocr_result_for_cover_or_409(session, cover_image_id)
    return _enqueue_cover_image_ocr_after_validation(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        draft_import_id=cover.draft_import_id,
        requested_via="ops_replay_route",
        queued_message="Cover image OCR replay queued by ops",
        replay_of_ocr_result_id=replay_of.id,
        replay_reason=replay_reason,
    )


def get_gmail_sync_job_status_for_user(
    session: Session,
    current_user: User,
    job_id: str,
) -> ImportParseJobStatusResponse:
    try:
        job = fetch_job_by_id(job_id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if (
        job.meta.get("job_type") != GMAIL_SYNC_JOB_TYPE
        or job.meta.get("user_id") != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get_status(refresh=True)
    return ImportParseJobStatusResponse(
        job_id=job.id,
        job_type=job.meta["job_type"],
        status=status,
        import_id=None,
        import_record=None,
        error=_extract_job_error(job),
        enqueued_at=job.enqueued_at,
        started_at=job.started_at,
        ended_at=job.ended_at,
    )


def enqueue_metadata_reenrichment_for_draft_import(
    session: Session,
    *,
    current_user: User,
    import_id: int,
    reason: str | None = None,
) -> OpsMetadataReenrichmentEnqueueResponse:
    draft_import = get_draft_import_for_ops_or_404(session, import_id)
    if draft_import.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft imports can be re-enriched")
    try:
        job = enqueue_metadata_reenrich_job(
            entity_type="draft_item",
            entity_id=import_id,
            user_id=current_user.id,
            reason=reason,
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc
    enqueue_reenrichment_audit(
        session,
        entity_type="draft_item",
        entity_id=import_id,
        actor_user_id=current_user.id,
        reason=reason or "Queued deterministic re-enrichment for draft import.",
    )
    session.commit()
    return OpsMetadataReenrichmentEnqueueResponse(
        job_id=job.id,
        status="queued",
        entity_type="draft_item",
        entity_id=import_id,
    )


def enqueue_metadata_reenrichment_for_inventory_copy(
    session: Session,
    *,
    current_user: User,
    inventory_copy_id: int,
    reason: str | None = None,
) -> OpsMetadataReenrichmentEnqueueResponse:
    get_inventory_copy_for_ops_or_404(session, inventory_copy_id)
    try:
        job = enqueue_metadata_reenrich_job(
            entity_type="inventory_copy",
            entity_id=inventory_copy_id,
            user_id=current_user.id,
            reason=reason,
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Background queue is unavailable") from exc
    enqueue_reenrichment_audit(
        session,
        entity_type="inventory_copy",
        entity_id=inventory_copy_id,
        actor_user_id=current_user.id,
        reason=reason or "Queued deterministic re-enrichment for inventory copy.",
    )
    session.commit()
    return OpsMetadataReenrichmentEnqueueResponse(
        job_id=job.id,
        status="queued",
        entity_type="inventory_copy",
        entity_id=inventory_copy_id,
    )
