from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.db.session import get_engine
from app.services.pull_list_automation import run_pull_list_refresh
from app.services.pull_list_scheduler import (
    advance_schedule_after_run,
    is_schedule_due,
    verify_upstream_refresh_order,
)

PULL_LIST_REFRESH_JOB_TYPE = "scheduled_pull_list_refresh"


def run_daily_pull_list_refresh(*, moment: datetime | None = None) -> dict[str, int | str | bool]:
    now = moment or datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        if not is_schedule_due(session, moment=now):
            return {"due": False, "runs_started": 0}
        order_ok, order_message = verify_upstream_refresh_order(session, moment=now)
        run = run_pull_list_refresh(session)
        advance_schedule_after_run(session, moment=now)
        return {
            "due": True,
            "runs_started": 1,
            "run_id": int(run.id or 0),
            "status": run.status,
            "upstream_order_ok": order_ok,
            "upstream_order_message": order_message,
        }


def run_manual_pull_list_refresh_for_ops() -> dict[str, int | str]:
    with Session(get_engine()) as session:
        run = run_pull_list_refresh(session)
        return {"run_id": int(run.id or 0), "status": run.status}
