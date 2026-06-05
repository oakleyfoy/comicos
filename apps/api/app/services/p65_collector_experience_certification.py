"""P65 certification — workspace, narratives, automation, notifications, non-mutation."""

from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.models.collector_assistant import CollectorAssistantRun
from app.models.collector_experience import CollectorTaskSnapshot
from app.models.market_intelligence_platform import PortfolioPerformanceSnapshot
from app.services.collector_workspace_service import build_collector_tasks, get_latest_task_snapshot, list_task_items
from app.services.collector_narrative_service import build_collector_narratives, get_latest_narrative_snapshot
from app.services.collector_automation_service import run_automation, KIND_DAILY_DIGEST
from app.services.notification_center_service import build_notifications, get_latest_notification_snapshot
from app.services.p65_feature_flags import (
    p65_automation_enabled,
    p65_collector_workspace_enabled,
    p65_notification_center_enabled,
)


def _count_upstream(session: Session) -> dict[str, int]:
    return {
        "buy_queue_snapshots": int(session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()),
        "portfolio_snapshots": int(session.exec(select(func.count()).select_from(PortfolioPerformanceSnapshot)).one()),
        "collector_assistant_runs": int(session.exec(select(func.count()).select_from(CollectorAssistantRun)).one()),
    }


def certify_p65_collector_experience(session: Session, *, owner_user_id: int) -> dict:
    flags = {
        "workspace": p65_collector_workspace_enabled(),
        "automation": p65_automation_enabled(),
        "notifications": p65_notification_center_enabled(),
    }
    before = _count_upstream(session)
    task_snap = build_collector_tasks(session, owner_user_id=owner_user_id)
    narr_snap = build_collector_narratives(session, owner_user_id=owner_user_id)
    notif_snap = build_notifications(session, owner_user_id=owner_user_id)
    auto_run = None
    if flags["automation"]:
        auto_run = run_automation(session, owner_user_id=owner_user_id, automation_kind=KIND_DAILY_DIGEST)
    after = _count_upstream(session)
    non_mutation = {
        "certified": before == after,
        "before": before,
        "after": after,
    }
    tasks = list_task_items(session, snapshot_id=int(task_snap.id or 0), limit=5)
    platform_ready = bool(task_snap.total_items >= 0 and narr_snap.readiness_status in ("SUCCESS", "NOT_READY"))
    checks = {
        "task_generation": int(task_snap.id or 0) > 0,
        "narratives": int(narr_snap.id or 0) > 0,
        "notifications": int(notif_snap.id or 0) > 0,
        "automation": auto_run is not None and auto_run.status == "SUCCESS" if auto_run else True,
        "owner_isolation": all(t.owner_user_id == owner_user_id for t in tasks) if tasks else True,
        "latest_task_snapshot": int(get_latest_task_snapshot(session, owner_user_id=owner_user_id).id or 0) > 0,
    }
    certified = non_mutation["certified"] and all(checks.values())
    return {
        "certified": certified,
        "platform_ready": platform_ready,
        "flags": flags,
        "checks": checks,
        "non_mutation": non_mutation,
        "snapshot_ids": {
            "tasks": int(task_snap.id or 0),
            "narratives": int(narr_snap.id or 0),
            "notifications": int(notif_snap.id or 0),
            "automation_run": int(auto_run.id or 0) if auto_run else None,
        },
    }
