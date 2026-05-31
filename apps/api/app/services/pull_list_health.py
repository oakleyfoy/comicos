from __future__ import annotations

from sqlmodel import Session, select

from app.models.pull_list import PullListAutomationRun
from app.schemas.pull_list_automation import PullListAutomationHealthRead, PullListAutomationOpsPanelRead
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import utc_today
from app.services.pull_list_decisions import _latest_decision_rows


def get_pull_list_automation_health(session: Session, *, owner_user_id: int) -> PullListAutomationHealthRead:
    latest_run = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).first()
    decisions = _latest_decision_rows(session, owner_user_id=owner_user_id)
    dashboard = get_foc_dashboard(session, owner_user_id=owner_user_id, today=utc_today())
    action_count = dashboard.summary.action_required_count + dashboard.summary.upcoming_foc_count
    return PullListAutomationHealthRead(
        last_run=latest_run.started_at if latest_run else None,
        run_status=latest_run.status if latest_run else "NEVER_RUN",
        runtime_ms=int(latest_run.runtime_ms) if latest_run else 0,
        decision_count=len(decisions),
        action_count=action_count,
        last_run_decisions_created=int(latest_run.decisions_created) if latest_run else 0,
        last_run_actions_generated=int(latest_run.actions_generated) if latest_run else 0,
    )


def build_pull_list_automation_ops_panel(session: Session, *, owner_user_id: int) -> PullListAutomationOpsPanelRead:
    health = get_pull_list_automation_health(session, owner_user_id=owner_user_id)
    latest_run = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).first()
    return PullListAutomationOpsPanelRead(
        last_run=health.last_run,
        status=health.run_status,
        runtime_ms=health.runtime_ms,
        decisions_generated=int(latest_run.decisions_created) if latest_run else health.last_run_decisions_created,
        actions_generated=int(latest_run.actions_generated) if latest_run else health.last_run_actions_generated,
    )
