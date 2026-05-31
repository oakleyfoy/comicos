from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.models.lunar_scheduler import LunarScheduleConfig, LunarScheduledRun, LunarScheduledRunError
from app.services.lunar_change_detection import (
    LunarFileSnapshot,
    calculate_file_checksum,
    evaluate_import_decision,
    persist_last_imported_file,
)
from app.services.lunar_credentials import get_credential_status
from app.services.lunar_feed_downloader import download_latest_monthly_products_csv
from app.services.lunar_feed_import import SOURCE_REMOTE, import_lunar_csv_bytes
from app.services.lunar_release_refresh import refresh_release_intelligence_after_lunar_import

SCHEDULE_TYPE_DAILY = "DAILY"
TRIGGER_SCHEDULED = "SCHEDULED"
TRIGGER_MANUAL = "MANUAL"

STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_NO_CHANGE = "NO_CHANGE"

DEFAULT_SCHEDULE_TIME = "06:00"
DEFAULT_TIMEZONE = "America/Chicago"


def compute_next_run_at(*, schedule_time: str, timezone_name: str, from_moment: datetime | None = None) -> datetime:
    tz = ZoneInfo(timezone_name)
    now_local = (from_moment or datetime.now(timezone.utc)).astimezone(tz)
    hour_str, minute_str = schedule_time.split(":", maxsplit=1)
    scheduled_local = now_local.replace(
        hour=int(hour_str),
        minute=int(minute_str),
        second=0,
        microsecond=0,
    )
    if scheduled_local <= now_local:
        scheduled_local += timedelta(days=1)
    return scheduled_local.astimezone(timezone.utc)


def get_or_create_schedule_config(session: Session, *, owner_user_id: int) -> LunarScheduleConfig:
    row = session.exec(select(LunarScheduleConfig).where(LunarScheduleConfig.owner_user_id == owner_user_id)).first()
    if row is not None:
        return row
    row = LunarScheduleConfig(
        owner_user_id=owner_user_id,
        enabled=False,
        schedule_type=SCHEDULE_TYPE_DAILY,
        schedule_time=DEFAULT_SCHEDULE_TIME,
        timezone=DEFAULT_TIMEZONE,
        next_run_at=compute_next_run_at(schedule_time=DEFAULT_SCHEDULE_TIME, timezone_name=DEFAULT_TIMEZONE),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def enable_schedule(
    session: Session,
    *,
    owner_user_id: int,
    schedule_time: str | None = None,
    timezone_name: str | None = None,
) -> LunarScheduleConfig:
    config = get_or_create_schedule_config(session, owner_user_id=owner_user_id)
    config.enabled = True
    if schedule_time is not None:
        config.schedule_time = schedule_time
    if timezone_name is not None:
        config.timezone = timezone_name
    config.next_run_at = compute_next_run_at(schedule_time=config.schedule_time, timezone_name=config.timezone)
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def disable_schedule(session: Session, *, owner_user_id: int) -> LunarScheduleConfig:
    config = get_or_create_schedule_config(session, owner_user_id=owner_user_id)
    config.enabled = False
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def set_schedule_time(
    session: Session,
    *,
    owner_user_id: int,
    schedule_time: str,
    timezone_name: str | None = None,
) -> LunarScheduleConfig:
    config = get_or_create_schedule_config(session, owner_user_id=owner_user_id)
    config.schedule_time = schedule_time
    if timezone_name is not None:
        config.timezone = timezone_name
    config.next_run_at = compute_next_run_at(schedule_time=config.schedule_time, timezone_name=config.timezone)
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def _begin_scheduled_run(
    session: Session,
    *,
    owner_user_id: int,
    trigger_type: str,
) -> LunarScheduledRun:
    run = LunarScheduledRun(
        owner_user_id=owner_user_id,
        trigger_type=trigger_type,
        status=STATUS_RUNNING,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _finalize_scheduled_run(
    session: Session,
    *,
    run: LunarScheduledRun,
    status: str,
    file_name: str | None = None,
    file_period: str | None = None,
    records_processed: int = 0,
    records_imported: int = 0,
    records_updated: int = 0,
    records_failed: int = 0,
) -> LunarScheduledRun:
    run.status = status
    run.file_name = file_name
    run.file_period = file_period
    run.records_processed = records_processed
    run.records_imported = records_imported
    run.records_updated = records_updated
    run.records_failed = records_failed
    run.completed_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _record_run_error(
    session: Session,
    *,
    scheduled_run_id: int,
    error_code: str,
    error_message: str,
) -> None:
    session.add(
        LunarScheduledRunError(
            scheduled_run_id=scheduled_run_id,
            error_code=error_code,
            error_message=error_message,
        )
    )
    session.commit()


def run_scheduled_lunar_import(
    session: Session,
    *,
    owner_user_id: int,
    trigger_type: str = TRIGGER_SCHEDULED,
    download_latest=None,
) -> LunarScheduledRun:
    config = get_or_create_schedule_config(session, owner_user_id=owner_user_id)
    run = _begin_scheduled_run(session, owner_user_id=owner_user_id, trigger_type=trigger_type)
    try:
        if not get_credential_status().credential_available:
            raise ValueError("Lunar credentials are not configured")
        download_fn = download_latest or download_latest_monthly_products_csv
        downloaded = download_fn()
        snapshot = LunarFileSnapshot(
            file_name=downloaded.file_name,
            file_period=downloaded.file_period,
            checksum=calculate_file_checksum(downloaded.content_bytes),
            content_bytes=downloaded.content_bytes,
            source_url=downloaded.source_url,
        )
        decision = evaluate_import_decision(session, owner_user_id=owner_user_id, snapshot=snapshot, config=config)
        if not decision.should_import:
            run = _finalize_scheduled_run(
                session,
                run=run,
                status=STATUS_NO_CHANGE,
                file_name=snapshot.file_name,
                file_period=snapshot.file_period,
            )
            config.last_success_at = datetime.now(timezone.utc)
            if config.enabled:
                config.next_run_at = compute_next_run_at(
                    schedule_time=config.schedule_time,
                    timezone_name=config.timezone,
                )
            config.updated_at = datetime.now(timezone.utc)
            session.add(config)
            session.commit()
            return run

        import_summary = import_lunar_csv_bytes(
            session,
            owner_user_id=owner_user_id,
            file_name=snapshot.file_name,
            content_bytes=snapshot.content_bytes,
            file_period=snapshot.file_period,
            source_type=SOURCE_REMOTE,
            source_url=snapshot.source_url,
        )
        refresh_release_intelligence_after_lunar_import(session, owner_user_id=owner_user_id)
        persist_last_imported_file(session, config=config, snapshot=snapshot)
        status = STATUS_COMPLETED if import_summary.status != "FAILED" else STATUS_FAILED
        run = _finalize_scheduled_run(
            session,
            run=run,
            status=status,
            file_name=import_summary.file_name,
            file_period=import_summary.file_period,
            records_processed=import_summary.records_processed,
            records_imported=import_summary.records_created,
            records_updated=import_summary.records_updated,
            records_failed=import_summary.records_failed,
        )
        if status == STATUS_COMPLETED:
            config.last_success_at = datetime.now(timezone.utc)
        else:
            config.last_failure_at = datetime.now(timezone.utc)
            for error in import_summary.errors:
                _record_run_error(
                    session,
                    scheduled_run_id=int(run.id or 0),
                    error_code=error.get("error_code", "IMPORT_ERROR"),
                    error_message=error.get("message", "Import failed"),
                )
        if config.enabled:
            config.next_run_at = compute_next_run_at(
                schedule_time=config.schedule_time,
                timezone_name=config.timezone,
            )
        config.updated_at = datetime.now(timezone.utc)
        session.add(config)
        session.commit()
        return run
    except Exception as exc:  # noqa: BLE001
        config.last_failure_at = datetime.now(timezone.utc)
        config.updated_at = datetime.now(timezone.utc)
        session.add(config)
        session.commit()
        run = _finalize_scheduled_run(session, run=run, status=STATUS_FAILED)
        _record_run_error(
            session,
            scheduled_run_id=int(run.id or 0),
            error_code="SCHEDULED_IMPORT_ERROR",
            error_message=str(exc),
        )
        if config.enabled:
            config.next_run_at = compute_next_run_at(
                schedule_time=config.schedule_time,
                timezone_name=config.timezone,
            )
            session.add(config)
            session.commit()
        return run


def list_due_schedule_configs(session: Session, *, moment: datetime | None = None) -> list[LunarScheduleConfig]:
    now = moment or datetime.now(timezone.utc)
    rows = session.exec(
        select(LunarScheduleConfig)
        .where(LunarScheduleConfig.enabled.is_(True))
        .where(LunarScheduleConfig.next_run_at.is_not(None))
        .where(LunarScheduleConfig.next_run_at <= now)
        .order_by(LunarScheduleConfig.next_run_at.asc(), LunarScheduleConfig.id.asc())
    ).all()
    return list(rows)


def list_scheduled_runs_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[LunarScheduledRun], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(LunarScheduledRun)
        .where(LunarScheduledRun.owner_user_id == owner_user_id)
        .order_by(LunarScheduledRun.created_at.desc(), LunarScheduledRun.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return page, len(rows)
