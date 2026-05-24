import logging
from datetime import datetime, timezone

from rq import get_current_job
from sqlmodel import Session

from app.db.session import get_engine
from app.models import CoverImage, GmailAccount, User
from app.core.config import get_settings
from app.services.cover_images import (
    extract_ocr_candidates_for_ocr_result,
    ensure_cover_image_ocr_regions,
    ensure_cover_image_derivatives,
    get_cover_image_ocr_result_or_404,
    mark_cover_image_ocr_failed,
    evaluate_cover_image_matching_readiness,
    run_cover_image_ocr,
    mark_cover_image_processing_succeeded,
    refresh_cover_image_file_metadata,
    set_cover_image_processing_failed,
)
from app.services.ocr_batches import (
    mark_ocr_batch_items_completed,
    mark_ocr_batch_items_failed,
    mark_ocr_batch_items_running,
)
from app.schemas.imports import DraftImportCreate
from app.services.gmail_ingestion import (
    mark_gmail_sync_failed,
    mark_gmail_sync_started,
    mark_gmail_sync_success,
    sync_gmail_receipts_for_user,
)
from app.services.imports import create_import_for_user
from app.services.metadata_reenrichment import (
    build_metadata_reenrichment_job_result,
    re_enrich_draft_import,
    re_enrich_inventory_copy,
)
from app.services.ops_events import classify_failure_message, record_ops_event
from app.tasks.queue import (
    AI_PARSE_IMPORT_JOB_TYPE,
    COVER_IMAGE_OCR_JOB_TYPE,
    COVER_IMAGE_PROCESS_JOB_TYPE,
    GMAIL_SYNC_JOB_TYPE,
    METADATA_REENRICH_JOB_TYPE,
)
from app.services.processing_errors import (
    classify_exception,
    public_safe_message,
    structured_error_to_persistent,
    try_parse_structured_error,
)

LOGGER = logging.getLogger(__name__)


class StructuredPipelineFailure(Exception):
    """Raised when a pipeline step already persisted a structured error payload on-disk."""

    __slots__ = ("persisted",)

    def __init__(self, persisted: str) -> None:
        safe = public_safe_message(persisted) or "Cover pipeline step failed."
        super().__init__(safe)
        self.persisted = persisted


def run_ai_parse_import_job(user_id: int, raw_text: str) -> dict[str, int]:
    LOGGER.info("AI parse job starting for user_id=%s", user_id)
    current_job = get_current_job()
    job_id = current_job.id if current_job is not None else None
    with Session(get_engine()) as session:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            error_message = "Unable to run AI parse job for missing or inactive user"
            record_ops_event(
                event_type="ai_parse_job",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=AI_PARSE_IMPORT_JOB_TYPE,
                message=error_message,
                details={"error": error_message},
            )
            raise ValueError(error_message)

        try:
            draft_import = create_import_for_user(
                session=session,
                current_user=user,
                payload=DraftImportCreate(raw_text=raw_text),
            )
        except Exception as exc:
            failure_message = str(exc)
            record_ops_event(
                event_type="ai_parse_job",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=AI_PARSE_IMPORT_JOB_TYPE,
                message=failure_message,
                details={"error": failure_message},
            )
            record_ops_event(
                event_type="parser_failure",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=AI_PARSE_IMPORT_JOB_TYPE,
                message=failure_message,
                details={
                    "failure_type": classify_failure_message(failure_message),
                    "error": failure_message,
                },
            )
            raise

        LOGGER.info("AI parse job finished for user_id=%s import_id=%s", user_id, draft_import.id)
        record_ops_event(
            event_type="ai_parse_job",
            status="success",
            user_id=user_id,
            job_id=job_id,
            queue_name=AI_PARSE_IMPORT_JOB_TYPE,
            draft_import_id=draft_import.id,
            message="AI parse job created a draft import",
            details={"import_id": draft_import.id},
        )
        return {"import_id": draft_import.id}


def run_worker_heartbeat() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


def run_local_ai_parse_diagnostic_job(marker: str) -> dict[str, str]:
    LOGGER.info("Local AI parse diagnostic job started marker=%s", marker)
    result = {
        "status": "ok",
        "marker": marker,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_type": "ai_parse_diagnostic",
    }
    LOGGER.info("Local AI parse diagnostic job finished marker=%s", marker)
    return result


def run_local_worker_diagnostic_job(marker: str) -> dict[str, str]:
    return run_local_ai_parse_diagnostic_job(marker)


def run_local_gmail_sync_diagnostic_job(marker: str) -> dict[str, str]:
    LOGGER.info("Local Gmail sync diagnostic job started marker=%s", marker)
    result = {
        "status": "ok",
        "marker": marker,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_type": "gmail_sync_diagnostic",
    }
    LOGGER.info("Local Gmail sync diagnostic job finished marker=%s", marker)
    return result


def run_gmail_sync_job(user_id: int, gmail_account_id: int) -> dict[str, int]:
    LOGGER.info(
        "Gmail sync job starting for user_id=%s gmail_account_id=%s",
        user_id,
        gmail_account_id,
    )
    current_job = get_current_job()
    job_id = current_job.id if current_job is not None else None
    with Session(get_engine()) as session:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            error_message = "Unable to run Gmail sync job for missing or inactive user"
            record_ops_event(
                event_type="gmail_sync",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=GMAIL_SYNC_JOB_TYPE,
                gmail_account_id=gmail_account_id,
                message=error_message,
                details={"error": error_message},
            )
            raise ValueError(error_message)

        account = session.get(GmailAccount, gmail_account_id)
        if account is None or account.user_id != user.id:
            error_message = "Unable to run Gmail sync job for missing Gmail account"
            record_ops_event(
                event_type="gmail_sync",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=GMAIL_SYNC_JOB_TYPE,
                gmail_account_id=gmail_account_id,
                message=error_message,
                details={"error": error_message},
            )
            raise ValueError(error_message)

        mark_gmail_sync_started(session, account)
        try:
            result = sync_gmail_receipts_for_user(session=session, current_user=user)
        except Exception as exc:
            mark_gmail_sync_failed(session, account, str(exc))
            record_ops_event(
                event_type="gmail_sync",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=GMAIL_SYNC_JOB_TYPE,
                gmail_account_id=gmail_account_id,
                message=str(exc),
                details={"error": str(exc)},
            )
            raise

        mark_gmail_sync_success(session, account)
        LOGGER.info(
            "Gmail sync job finished for user_id=%s gmail_account_id=%s result=%s",
            user_id,
            gmail_account_id,
            result,
        )
        record_ops_event(
            event_type="gmail_sync",
            status="success",
            user_id=user_id,
            job_id=job_id,
            queue_name=GMAIL_SYNC_JOB_TYPE,
            gmail_account_id=gmail_account_id,
            message="Gmail sync completed",
            details=result,
        )
        return result


def run_cover_image_process_job(cover_image_id: int, user_id: int) -> dict[str, object]:
    LOGGER.info("Cover image processing job starting cover_image_id=%s user_id=%s", cover_image_id, user_id)
    current_job = get_current_job()
    job_id = current_job.id if current_job is not None else None
    settings = get_settings()
    with Session(get_engine()) as session:
        cover = session.get(CoverImage, cover_image_id)
        if cover is None:
            error_message = "Unable to process missing cover image"
            record_ops_event(
                event_type="cover_image_process",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                message=error_message,
                details={"error": error_message, "cover_image_id": cover_image_id},
            )
            raise ValueError(error_message)

        try:
            refreshed = refresh_cover_image_file_metadata(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
            )
            if refreshed.processing_status == "failed":
                persisted = refreshed.processing_error or "Cover image metadata refresh failed"
                raise StructuredPipelineFailure(str(persisted))
            ensure_cover_image_derivatives(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
            )
            ensure_cover_image_ocr_regions(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
            )
            refreshed = mark_cover_image_processing_succeeded(
                session,
                cover_image_id=cover_image_id,
            )
            refreshed = evaluate_cover_image_matching_readiness(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
            )
        except StructuredPipelineFailure as exc:
            cover = session.get(CoverImage, cover_image_id)
            refreshed_cover = (
                evaluate_cover_image_matching_readiness(
                    session,
                    settings=settings,
                    cover_image_id=cover_image_id,
                )
                if cover is not None
                else None
            )
            persisted = exc.persisted
            parsed = try_parse_structured_error(persisted)
            details = (
                {"cover_image_id": cover_image_id, "persisted": True}
                if parsed is None
                else {
                    "cover_image_id": cover_image_id,
                    "error_code": parsed.error_code,
                    "retryable": parsed.retryable,
                    "persisted": True,
                }
            )
            if parsed is not None and parsed.error_type == "processing_timeout":
                record_ops_event(
                    event_type="processing_timeout",
                    status="failed",
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                    message=parsed.safe_message,
                    details=details | {"subsystem": "cover_metadata"},
                )
            if parsed is not None and parsed.error_code == "cover_image_corrupt":
                record_ops_event(
                    event_type="corrupt_image_detected",
                    status="failed",
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                    message=parsed.safe_message,
                    details=details,
                )
            record_ops_event(
                event_type="cover_image_process",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                draft_import_id=refreshed_cover.draft_import_id if refreshed_cover is not None else None,
                message=public_safe_message(persisted) or "Cover image processing failed",
                details=details,
            )
            raise ValueError(exc.args[0]) from exc
        except Exception as exc:
            classified = classify_exception(exc, stage="cover_image_process_job")
            persisted = structured_error_to_persistent(classified)
            cover = session.get(CoverImage, cover_image_id)
            if cover is not None and cover.processing_status != "failed":
                refreshed = set_cover_image_processing_failed(
                    session,
                    cover=cover,
                    error_message=persisted,
                )
            else:
                refreshed = cover
            if refreshed is not None:
                refreshed = evaluate_cover_image_matching_readiness(
                    session,
                    settings=settings,
                    cover_image_id=cover_image_id,
                )
            details = {
                "cover_image_id": cover_image_id,
                "error_code": classified.error_code,
                "retryable": classified.retryable,
            }
            if classified.error_type == "processing_timeout":
                record_ops_event(
                    event_type="processing_timeout",
                    status="failed",
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                    message=classified.safe_message,
                    details=details | {"subsystem": "cover_process"},
                )
            if classified.error_code == "cover_image_corrupt":
                record_ops_event(
                    event_type="corrupt_image_detected",
                    status="failed",
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                    message=classified.safe_message,
                    details=details,
                )
            record_ops_event(
                event_type="cover_image_process",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
                draft_import_id=refreshed.draft_import_id if refreshed is not None else None,
                message=classified.safe_message,
                details=details,
            )
            raise ValueError(classified.safe_message) from exc

        result = {
            "cover_image_id": cover_image_id,
            "processing_status": refreshed.processing_status,
            "mime_type": refreshed.mime_type,
            "file_size": refreshed.file_size,
            "image_width": refreshed.image_width,
            "image_height": refreshed.image_height,
        }
        record_ops_event(
            event_type="cover_image_process",
            status="success",
            user_id=user_id,
            job_id=job_id,
            queue_name=COVER_IMAGE_PROCESS_JOB_TYPE,
            draft_import_id=refreshed.draft_import_id,
            message="Cover image metadata processing completed",
            details=result,
        )
        return result


def run_cover_image_ocr_job(
    cover_image_id: int,
    user_id: int,
    ocr_result_id: int,
) -> dict[str, object]:
    LOGGER.info(
        "Cover image OCR job starting cover_image_id=%s user_id=%s ocr_result_id=%s",
        cover_image_id,
        user_id,
        ocr_result_id,
    )
    current_job = get_current_job()
    job_id = current_job.id if current_job is not None else None
    settings = get_settings()
    with Session(get_engine()) as session:
        cover = session.get(CoverImage, cover_image_id)
        if cover is None:
            error_message = "Unable to OCR missing cover image"
            record_ops_event(
                event_type="cover_image_ocr",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=COVER_IMAGE_OCR_JOB_TYPE,
                message=error_message,
                details={"error": error_message, "cover_image_id": cover_image_id, "ocr_result_id": ocr_result_id},
            )
            raise ValueError(error_message)

        try:
            mark_ocr_batch_items_running(session, cover_image_id=cover_image_id, job_id=job_id)
            ocr_row = run_cover_image_ocr(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
                ocr_result_id=ocr_result_id,
            )
            extract_ocr_candidates_for_ocr_result(
                session,
                cover_image_id=cover_image_id,
                ocr_result_id=ocr_result_id,
            )
        except Exception as exc:
            classified = classify_exception(exc, stage="cover_image_ocr_job")
            persisted_err = structured_error_to_persistent(classified)
            details = {
                "cover_image_id": cover_image_id,
                "ocr_result_id": ocr_result_id,
                "error_code": classified.error_code,
                "retryable": classified.retryable,
            }
            if classified.error_type == "processing_timeout":
                record_ops_event(
                    event_type="processing_timeout",
                    status="failed",
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=COVER_IMAGE_OCR_JOB_TYPE,
                    message=classified.safe_message,
                    details=details | {"subsystem": "cover_ocr"},
                )
            if classified.error_code == "cover_image_corrupt":
                record_ops_event(
                    event_type="corrupt_image_detected",
                    status="failed",
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=COVER_IMAGE_OCR_JOB_TYPE,
                    message=classified.safe_message,
                    details=details,
                )
            try:
                ocr_row = mark_cover_image_ocr_failed(
                    session,
                    ocr_result_id=ocr_result_id,
                    error_message=persisted_err,
                )
            except Exception:
                ocr_row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
            record_ops_event(
                event_type="cover_image_ocr",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=COVER_IMAGE_OCR_JOB_TYPE,
                draft_import_id=cover.draft_import_id,
                message=classified.safe_message,
                details=details,
            )
            mark_ocr_batch_items_failed(
                session,
                cover_image_id=cover_image_id,
                job_id=job_id,
                error_message=persisted_err,
            )
            raise ValueError(classified.safe_message) from exc

        result = {
            "cover_image_id": cover_image_id,
            "ocr_result_id": ocr_row.id,
            "processing_status": ocr_row.processing_status,
            "ocr_engine": ocr_row.ocr_engine,
            "raw_text_length": len(ocr_row.raw_text),
        }
        record_ops_event(
            event_type="cover_image_ocr",
            status="success",
            user_id=user_id,
            job_id=job_id,
            queue_name=COVER_IMAGE_OCR_JOB_TYPE,
            draft_import_id=cover.draft_import_id,
            message="Cover image OCR completed",
            details=result,
        )
        mark_ocr_batch_items_completed(session, cover_image_id=cover_image_id, job_id=job_id)
        return result


def run_metadata_reenrich_job(
    entity_type: str,
    entity_id: int,
    user_id: int,
    reason: str | None = None,
) -> dict[str, object]:
    LOGGER.info(
        "Metadata re-enrichment job starting user_id=%s entity_type=%s entity_id=%s",
        user_id,
        entity_type,
        entity_id,
    )
    current_job = get_current_job()
    job_id = current_job.id if current_job is not None else None
    with Session(get_engine()) as session:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            error_message = "Unable to run metadata re-enrichment for missing or inactive user"
            record_ops_event(
                event_type="metadata_reenrich",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=METADATA_REENRICH_JOB_TYPE,
                message=error_message,
                details={
                    "error": error_message,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )
            raise ValueError(error_message)

        try:
            if entity_type == "draft_item":
                re_enrich_draft_import(
                    session,
                    draft_import_id=entity_id,
                    actor_user_id=user.id,
                    reason=reason,
                )
            elif entity_type == "inventory_copy":
                re_enrich_inventory_copy(
                    session,
                    inventory_copy_id=entity_id,
                    actor_user_id=user.id,
                    reason=reason,
                )
            else:
                raise ValueError(f"Unsupported metadata re-enrichment entity_type: {entity_type}")
        except Exception as exc:
            record_ops_event(
                event_type="metadata_reenrich",
                status="failed",
                user_id=user_id,
                job_id=job_id,
                queue_name=METADATA_REENRICH_JOB_TYPE,
                message=str(exc),
                details={
                    "error": str(exc),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )
            raise

        result = build_metadata_reenrichment_job_result(
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
        )
        record_ops_event(
            event_type="metadata_reenrich",
            status="success",
            user_id=user_id,
            job_id=job_id,
            queue_name=METADATA_REENRICH_JOB_TYPE,
            message="Metadata re-enrichment completed",
            details=result,
        )
        return result
