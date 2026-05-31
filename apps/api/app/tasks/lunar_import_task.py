from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.lunar_scheduler import LunarScheduleConfig
from app.services.lunar_scheduler import (
    TRIGGER_MANUAL,
    TRIGGER_SCHEDULED,
    list_due_schedule_configs,
    run_scheduled_lunar_import,
)

LUNAR_DAILY_IMPORT_JOB_TYPE = "scheduled_lunar_import"


def run_daily_lunar_import(*, moment: datetime | None = None) -> dict[str, int]:
    now = moment or datetime.now(timezone.utc)
    runs_started = 0
    runs_completed = 0
    runs_no_change = 0
    runs_failed = 0

    with Session(get_engine()) as session:
        due_configs = list_due_schedule_configs(session, moment=now)
        for config in due_configs:
            runs_started += 1
            run = run_scheduled_lunar_import(
                session,
                owner_user_id=int(config.owner_user_id),
                trigger_type=TRIGGER_SCHEDULED,
            )
            if run.status == "NO_CHANGE":
                runs_no_change += 1
            elif run.status == "COMPLETED":
                runs_completed += 1
            elif run.status == "FAILED":
                runs_failed += 1

    return {
        "due_configs": len(due_configs),
        "runs_started": runs_started,
        "runs_completed": runs_completed,
        "runs_no_change": runs_no_change,
        "runs_failed": runs_failed,
    }


def run_lunar_import_for_owner(owner_user_id: int) -> dict[str, str | int]:
    with Session(get_engine()) as session:
        run = run_scheduled_lunar_import(
            session,
            owner_user_id=owner_user_id,
            trigger_type=TRIGGER_MANUAL,
        )
        return {
            "run_id": int(run.id or 0),
            "run_uuid": run.run_uuid,
            "status": run.status,
            "records_processed": run.records_processed,
            "records_imported": run.records_imported,
        }
