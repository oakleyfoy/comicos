from sqlmodel import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.services.gmail_ingestion import (
    gmail_integration_is_configured,
    list_auto_sync_enabled_accounts,
)
from app.tasks.queue import (
    enqueue_gmail_sync_job,
    fetch_job_by_id,
    find_active_gmail_sync_job_for_account,
    schedule_job_in,
)

GMAIL_AUTO_SYNC_SCAN_JOB_TYPE = "scheduled_gmail_sync_scan"
GMAIL_AUTO_SYNC_INTERVAL_SECONDS = 900
GMAIL_AUTO_SYNC_SCAN_JOB_ID = "scheduled-gmail-auto-sync-scan"

LUNAR_IMPORT_SCAN_JOB_TYPE = "scheduled_lunar_import_scan"
LUNAR_IMPORT_SCAN_INTERVAL_SECONDS = 900
LUNAR_IMPORT_SCAN_JOB_ID = "scheduled-lunar-import-scan"

PULL_LIST_REFRESH_SCAN_JOB_TYPE = "scheduled_pull_list_refresh_scan"
PULL_LIST_REFRESH_SCAN_INTERVAL_SECONDS = 900
PULL_LIST_REFRESH_SCAN_JOB_ID = "scheduled-pull-list-refresh-scan"

MARKET_REFRESH_SCAN_JOB_TYPE = "scheduled_market_refresh_scan"
MARKET_REFRESH_SCAN_INTERVAL_SECONDS = 86400
MARKET_REFRESH_SCAN_JOB_ID = "scheduled-market-refresh-scan"


def schedule_worker_heartbeat(*, delay_seconds: int = 300):
    settings = get_settings()
    return schedule_job_in(
        queue_name=settings.rq_ai_parse_queue_name,
        delay_seconds=delay_seconds,
        func="app.tasks.jobs.run_worker_heartbeat",
        meta={"job_type": "scheduled_heartbeat"},
    )


def enqueue_due_gmail_auto_sync_jobs() -> dict[str, int]:
    if not gmail_integration_is_configured():
        return {
            "eligible_accounts": 0,
            "enqueued_jobs": 0,
            "skipped_disconnected": 0,
            "skipped_active": 0,
        }

    with Session(get_engine()) as session:
        accounts = list_auto_sync_enabled_accounts(session)
        eligible_accounts = len(accounts)
        enqueued_jobs = 0
        skipped_disconnected = 0
        skipped_active = 0

        for account in accounts:
            if account.access_token_encrypted is None:
                skipped_disconnected += 1
                continue

            if find_active_gmail_sync_job_for_account(account.id) is not None:
                skipped_active += 1
                continue

            enqueue_gmail_sync_job(
                user_id=account.user_id,
                gmail_account_id=account.id,
            )
            enqueued_jobs += 1

    return {
        "eligible_accounts": eligible_accounts,
        "enqueued_jobs": enqueued_jobs,
        "skipped_disconnected": skipped_disconnected,
        "skipped_active": skipped_active,
    }


def run_scheduled_gmail_sync_scan() -> dict[str, int]:
    result = enqueue_due_gmail_auto_sync_jobs()
    schedule_gmail_auto_sync_scan()
    return result


def schedule_gmail_auto_sync_scan(*, delay_seconds: int = GMAIL_AUTO_SYNC_INTERVAL_SECONDS):
    settings = get_settings()
    existing_job = fetch_job_by_id(GMAIL_AUTO_SYNC_SCAN_JOB_ID)
    if existing_job is not None and existing_job.get_status(refresh=True) in {
        "scheduled",
        "queued",
        "started",
        "deferred",
    }:
        return existing_job

    if existing_job is not None:
        existing_job.delete()

    return schedule_job_in(
        queue_name=settings.rq_ai_parse_queue_name,
        delay_seconds=delay_seconds,
        func="app.tasks.scheduled.run_scheduled_gmail_sync_scan",
        meta={"job_type": GMAIL_AUTO_SYNC_SCAN_JOB_TYPE},
        job_id=GMAIL_AUTO_SYNC_SCAN_JOB_ID,
    )


def run_scheduled_lunar_import_scan() -> dict[str, int]:
    from app.tasks.lunar_import_task import run_daily_lunar_import

    result = run_daily_lunar_import()
    schedule_lunar_daily_import_scan()
    schedule_pull_list_daily_refresh_scan()
    schedule_market_refresh_scan()
    return result


def run_scheduled_market_refresh_scan() -> dict[str, int]:
    from app.tasks.market_refresh_task import run_daily_market_refresh

    result = run_daily_market_refresh()
    schedule_market_refresh_scan()
    return result


def schedule_market_refresh_scan(*, delay_seconds: int = MARKET_REFRESH_SCAN_INTERVAL_SECONDS):
    settings = get_settings()
    existing_job = fetch_job_by_id(MARKET_REFRESH_SCAN_JOB_ID)
    if existing_job is not None and existing_job.get_status(refresh=True) in {
        "scheduled",
        "queued",
        "started",
        "deferred",
    }:
        return existing_job

    if existing_job is not None:
        existing_job.delete()

    return schedule_job_in(
        queue_name=settings.rq_ai_parse_queue_name,
        delay_seconds=delay_seconds,
        func="app.tasks.scheduled.run_scheduled_market_refresh_scan",
        meta={"job_type": MARKET_REFRESH_SCAN_JOB_TYPE},
        job_id=MARKET_REFRESH_SCAN_JOB_ID,
    )


def schedule_lunar_daily_import_scan(*, delay_seconds: int = LUNAR_IMPORT_SCAN_INTERVAL_SECONDS):
    settings = get_settings()
    existing_job = fetch_job_by_id(LUNAR_IMPORT_SCAN_JOB_ID)
    if existing_job is not None and existing_job.get_status(refresh=True) in {
        "scheduled",
        "queued",
        "started",
        "deferred",
    }:
        return existing_job

    if existing_job is not None:
        existing_job.delete()

    return schedule_job_in(
        queue_name=settings.rq_ai_parse_queue_name,
        delay_seconds=delay_seconds,
        func="app.tasks.scheduled.run_scheduled_lunar_import_scan",
        meta={"job_type": LUNAR_IMPORT_SCAN_JOB_TYPE},
        job_id=LUNAR_IMPORT_SCAN_JOB_ID,
    )


def run_scheduled_pull_list_refresh_scan() -> dict[str, int | str | bool]:
    from app.tasks.pull_list_refresh_task import run_daily_pull_list_refresh

    result = run_daily_pull_list_refresh()
    schedule_pull_list_daily_refresh_scan()
    return result


def schedule_pull_list_daily_refresh_scan(*, delay_seconds: int = PULL_LIST_REFRESH_SCAN_INTERVAL_SECONDS):
    settings = get_settings()
    existing_job = fetch_job_by_id(PULL_LIST_REFRESH_SCAN_JOB_ID)
    if existing_job is not None and existing_job.get_status(refresh=True) in {
        "scheduled",
        "queued",
        "started",
        "deferred",
    }:
        return existing_job

    if existing_job is not None:
        existing_job.delete()

    return schedule_job_in(
        queue_name=settings.rq_ai_parse_queue_name,
        delay_seconds=delay_seconds,
        func="app.tasks.scheduled.run_scheduled_pull_list_refresh_scan",
        meta={"job_type": PULL_LIST_REFRESH_SCAN_JOB_TYPE},
        job_id=PULL_LIST_REFRESH_SCAN_JOB_ID,
    )
