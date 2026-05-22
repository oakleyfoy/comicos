import logging
from datetime import datetime, timezone

from rq import get_current_job
from sqlmodel import Session

from app.db.session import get_engine
from app.models import GmailAccount, User
from app.schemas.imports import DraftImportCreate
from app.services.gmail_ingestion import (
    mark_gmail_sync_failed,
    mark_gmail_sync_started,
    mark_gmail_sync_success,
    sync_gmail_receipts_for_user,
)
from app.services.imports import create_import_for_user
from app.services.ops_events import classify_failure_message, record_ops_event
from app.tasks.queue import AI_PARSE_IMPORT_JOB_TYPE, GMAIL_SYNC_JOB_TYPE

LOGGER = logging.getLogger(__name__)


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
