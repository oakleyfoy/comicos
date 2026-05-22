from fastapi import HTTPException
from redis.exceptions import RedisError
from rq.job import Job
from sqlmodel import Session

from app.db.session import get_engine
from app.models import DraftImport, User
from app.schemas.gmail import GmailSyncEnqueueResponse
from app.schemas.imports import DraftImportCreate
from app.schemas.jobs import ImportParseJobEnqueueResponse, ImportParseJobStatusResponse
from app.services.ai_order_parser import ensure_ai_parser_configured
from app.services.gmail_ingestion import (
    GmailNotConnectedError,
    ensure_gmail_integration_configured,
    get_gmail_account_for_user,
)
from app.services.imports import serialize_import
from app.tasks.queue import (
    AI_PARSE_IMPORT_JOB_TYPE,
    GMAIL_SYNC_JOB_TYPE,
    enqueue_ai_parse_import_job,
    enqueue_gmail_sync_job,
    fetch_job_by_id,
)


def _extract_job_error(job: Job) -> str | None:
    if not job.exc_info:
        return None

    lines = [line.strip() for line in job.exc_info.splitlines() if line.strip()]
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
            import_record = serialize_import(draft_import)

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
