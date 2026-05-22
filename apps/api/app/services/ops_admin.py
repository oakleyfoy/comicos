from collections.abc import Iterable
from datetime import datetime

from fastapi import HTTPException
from rq.job import Job
from rq.registry import (
    DeferredJobRegistry,
    FailedJobRegistry,
    FinishedJobRegistry,
    ScheduledJobRegistry,
    StartedJobRegistry,
)
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import DraftImport, GmailAccount, OpsEvent, User
from app.schemas.ops import (
    OpsDashboardResponse,
    OpsDraftImportRow,
    OpsEventRow,
    OpsGmailSyncRow,
    OpsJobRow,
    OpsQueueSnapshot,
)
from app.services.background_jobs import _extract_job_error
from app.tasks.queue import (
    AI_PARSE_IMPORT_JOB_TYPE,
    GMAIL_SYNC_JOB_TYPE,
    fetch_job_by_id,
    get_queue,
    get_worker_queue_names,
)

RECENT_LIMIT = 12


def ensure_ops_admin_access(current_user: User, settings: Settings) -> None:
    configured_emails = settings.ops_admin_emails
    if configured_emails:
        if current_user.email.lower() in configured_emails:
            return
        raise HTTPException(status_code=403, detail="Operations dashboard access denied")

    if settings.app_env.lower() != "production":
        return

    raise HTTPException(status_code=403, detail="Operations dashboard access denied")


def _job_sort_key(job: Job) -> datetime | None:
    return job.ended_at or job.started_at or job.enqueued_at


def _stringify_result(job: Job) -> str | None:
    if isinstance(job.result, dict):
        if {"processed_messages", "created_draft_imports", "skipped_duplicates"} <= set(job.result):
            return (
                "processed={processed_messages}, created={created_draft_imports}, "
                "duplicates={skipped_duplicates}"
            ).format(**job.result)
        if "import_id" in job.result:
            return f"import_id={job.result['import_id']}"
        return ", ".join(f"{key}={value}" for key, value in sorted(job.result.items()))
    if job.result is None:
        return None
    return str(job.result)


def _user_email_map(session: Session, user_ids: Iterable[int | None]) -> dict[int, str]:
    normalized_ids = sorted({user_id for user_id in user_ids if user_id is not None})
    if not normalized_ids:
        return {}
    users = session.exec(select(User).where(User.id.in_(normalized_ids))).all()
    return {user.id: user.email for user in users if user.id is not None}


def _collect_recent_jobs(job_type: str, limit: int = RECENT_LIMIT) -> list[Job]:
    queue_names = get_worker_queue_names()
    jobs_by_id: dict[str, Job] = {}
    for queue_name in queue_names:
        queue = get_queue(queue_name)
        candidate_ids = list(queue.job_ids)
        candidate_ids.extend(StartedJobRegistry(queue=queue).get_job_ids())
        candidate_ids.extend(FailedJobRegistry(queue=queue).get_job_ids())
        candidate_ids.extend(FinishedJobRegistry(queue=queue).get_job_ids())
        candidate_ids.extend(DeferredJobRegistry(queue=queue).get_job_ids())
        candidate_ids.extend(ScheduledJobRegistry(queue=queue).get_job_ids())
        for job_id in candidate_ids:
            if job_id in jobs_by_id:
                continue
            job = fetch_job_by_id(job_id)
            if job is None or job.meta.get("job_type") != job_type:
                continue
            jobs_by_id[job.id] = job

    return sorted(
        jobs_by_id.values(),
        key=lambda job: _job_sort_key(job) or datetime.min,
        reverse=True,
    )[:limit]


def _serialize_jobs(session: Session, jobs: list[Job]) -> list[OpsJobRow]:
    emails = _user_email_map(session, (job.meta.get("user_id") for job in jobs))
    rows: list[OpsJobRow] = []
    for job in jobs:
        user_id = job.meta.get("user_id")
        rows.append(
            OpsJobRow(
                job_id=job.id,
                job_type=str(job.meta.get("job_type") or "unknown"),
                queue_name=str(job.origin),
                status=job.get_status(refresh=True),
                user_id=user_id,
                user_email=emails.get(user_id) if user_id is not None else None,
                started_at=job.started_at,
                ended_at=job.ended_at,
                result_summary=_stringify_result(job),
                error=_extract_job_error(job),
            )
        )
    return rows


def _queue_snapshot(queue_name: str) -> OpsQueueSnapshot:
    queue = get_queue(queue_name)
    failed_registry = FailedJobRegistry(queue=queue)
    started_registry = StartedJobRegistry(queue=queue)
    candidate_ids = (
        list(queue.job_ids)
        + started_registry.get_job_ids()
        + failed_registry.get_job_ids()
        + FinishedJobRegistry(queue=queue).get_job_ids()
    )
    recent_jobs = [job for job_id in candidate_ids if (job := fetch_job_by_id(job_id)) is not None]
    most_recent_job = max(
        recent_jobs,
        key=lambda job: _job_sort_key(job) or datetime.min,
        default=None,
    )
    return OpsQueueSnapshot(
        queue_name=queue_name,
        queued_jobs=len(queue.job_ids),
        started_jobs=len(started_registry.get_job_ids()),
        failed_jobs=len(failed_registry.get_job_ids()),
        most_recent_job_result=_stringify_result(most_recent_job) if most_recent_job else None,
    )


def _serialize_events(session: Session, events: list[OpsEvent]) -> list[OpsEventRow]:
    emails = _user_email_map(session, (event.user_id for event in events))
    return [
        OpsEventRow(
            id=event.id,
            event_type=event.event_type,
            status=event.status,
            created_at=event.created_at,
            user_id=event.user_id,
            user_email=emails.get(event.user_id) if event.user_id is not None else None,
            draft_import_id=event.draft_import_id,
            order_id=event.order_id,
            external_message_id=event.external_message_id,
            message=event.message,
            details=event.details_json,
        )
        for event in events
        if event.id is not None
    ]


def _derived_confirm_success_events(
    session: Session, existing_draft_ids: set[int], limit: int
) -> list[OpsEventRow]:
    rows = session.exec(
        select(DraftImport, User)
        .join(User, User.id == DraftImport.user_id)
        .where(DraftImport.status == "confirmed", DraftImport.linked_order_id.is_not(None))
        .order_by(DraftImport.updated_at.desc(), DraftImport.id.desc())
        .limit(limit)
    ).all()
    derived_rows: list[OpsEventRow] = []
    for draft, user in rows:
        if draft.id is None or draft.id in existing_draft_ids:
            continue
        derived_rows.append(
            OpsEventRow(
                id=-(draft.id),
                event_type="confirm_success",
                status="derived",
                created_at=draft.updated_at,
                user_id=user.id,
                user_email=user.email,
                draft_import_id=draft.id,
                order_id=draft.linked_order_id,
                external_message_id=None,
                message="Derived from confirmed draft import state",
                details={"source": "draft_import_state"},
            )
        )
    return derived_rows


def build_ops_dashboard(session: Session) -> OpsDashboardResponse:
    recent_gmail_sync_jobs = _serialize_jobs(session, _collect_recent_jobs(GMAIL_SYNC_JOB_TYPE))
    recent_ai_parse_jobs = _serialize_jobs(
        session, _collect_recent_jobs(AI_PARSE_IMPORT_JOB_TYPE)
    )

    accounts = session.exec(
        select(GmailAccount, User).join(User, User.id == GmailAccount.user_id)
    ).all()
    gmail_sync_statuses: list[OpsGmailSyncRow] = []
    for account, user in accounts:
        latest_event = session.exec(
            select(OpsEvent)
            .where(
                OpsEvent.event_type == "gmail_sync",
                OpsEvent.gmail_account_id == account.id,
            )
            .order_by(OpsEvent.created_at.desc(), OpsEvent.id.desc())
        ).first()
        details = latest_event.details_json if latest_event is not None else {}
        gmail_sync_statuses.append(
            OpsGmailSyncRow(
                gmail_account_id=account.id,
                user_id=user.id,
                user_email=user.email,
                gmail_email=account.gmail_email,
                auto_sync_enabled=account.auto_sync_enabled,
                last_sync_status=account.last_sync_status,
                last_sync_started_at=account.last_sync_started_at,
                last_sync_completed_at=account.last_sync_completed_at,
                processed_messages=details.get("processed_messages"),
                created_draft_imports=details.get("created_draft_imports"),
                skipped_duplicates=details.get("skipped_duplicates"),
                last_error_message=account.last_sync_error or details.get("error"),
            )
        )

    draft_rows = session.exec(
        select(DraftImport, User)
        .join(User, User.id == DraftImport.user_id)
        .order_by(DraftImport.created_at.desc(), DraftImport.id.desc())
        .limit(RECENT_LIMIT)
    ).all()
    recent_draft_imports = [
        OpsDraftImportRow(
            draft_id=draft.id,
            user_id=user.id,
            user_email=user.email,
            retailer=(draft.parsed_payload_json or {}).get("retailer"),
            status=draft.status,
            confidence=str(draft.confidence_score),
            warning_count=len((draft.parsed_payload_json or {}).get("warnings") or []),
            created_at=draft.created_at,
            linked_order_id=draft.linked_order_id,
        )
        for draft, user in draft_rows
        if draft.id is not None and user.id is not None
    ]

    parser_failures = session.exec(
        select(OpsEvent)
        .where(OpsEvent.event_type.in_(["parser_failure", "unsupported_provider_skip"]))
        .order_by(OpsEvent.created_at.desc(), OpsEvent.id.desc())
        .limit(RECENT_LIMIT)
    ).all()
    duplicate_skip_events = session.exec(
        select(OpsEvent)
        .where(OpsEvent.event_type == "duplicate_skip")
        .order_by(OpsEvent.created_at.desc(), OpsEvent.id.desc())
        .limit(RECENT_LIMIT)
    ).all()
    confirm_events = session.exec(
        select(OpsEvent)
        .where(OpsEvent.event_type.in_(["confirm_success", "confirm_failure"]))
        .order_by(OpsEvent.created_at.desc(), OpsEvent.id.desc())
        .limit(RECENT_LIMIT)
    ).all()
    serialized_confirm_events = _serialize_events(session, confirm_events)
    serialized_confirm_events.extend(
        _derived_confirm_success_events(
            session,
            existing_draft_ids={
                row.draft_import_id
                for row in serialized_confirm_events
                if row.draft_import_id is not None
            },
            limit=RECENT_LIMIT,
        )
    )
    serialized_confirm_events = sorted(
        serialized_confirm_events,
        key=lambda row: row.created_at,
        reverse=True,
    )[:RECENT_LIMIT]

    return OpsDashboardResponse(
        recent_gmail_sync_jobs=recent_gmail_sync_jobs,
        recent_ai_parse_jobs=recent_ai_parse_jobs,
        gmail_sync_statuses=gmail_sync_statuses,
        recent_draft_imports=recent_draft_imports,
        parser_failures=_serialize_events(session, parser_failures),
        duplicate_skip_events=_serialize_events(session, duplicate_skip_events),
        confirm_events=serialized_confirm_events,
        queue_health=[_queue_snapshot(queue_name) for queue_name in get_worker_queue_names()],
    )
