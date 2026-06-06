"""P85 workflow health — surfaces gaps and stale areas without new intelligence."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.schemas.p85_production_hardening import P85WorkflowHealthRead, P85WorkflowIssueRead
from app.services.collector_home_service import build_collector_home
from app.services.daily_action_engine import list_latest_daily_actions
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p81_discovery_service import list_opportunities


def build_workflow_health(session: Session, *, owner_user_id: int) -> P85WorkflowHealthRead:
    issues: list[P85WorkflowIssueRead] = []
    empty_workflows: list[str] = []

    copies = list(
        session.exec(
            select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).where(InventoryCopy.hold_status != "sold").limit(500)
        ).all()
    )
    if not copies:
        empty_workflows.append("inventory")
        issues.append(
            P85WorkflowIssueRead(
                workflow="inventory",
                severity="MEDIUM",
                issue_type="NO_DATA",
                message="No inventory copies yet.",
                recommended_fix="Import an order or add inventory from the dashboard.",
                action_url="/dashboard",
            )
        )

    sell = build_sell_queue(session, owner_user_id=owner_user_id, limit=5, offset=0, refresh_upstream=False)
    if copies and not sell.items:
        empty_workflows.append("sell_queue")
        issues.append(
            P85WorkflowIssueRead(
                workflow="sell",
                severity="LOW",
                issue_type="NO_DATA",
                message="Sell queue is empty.",
                recommended_fix="Refresh sell candidates or set FMV on copies.",
                action_url="/sell-queue",
            )
        )

    try:
        disc = list_opportunities(session, owner_user_id=owner_user_id, limit=5, offset=0, refresh=False)
        if disc.total_items == 0:
            empty_workflows.append("discovery")
            issues.append(
                P85WorkflowIssueRead(
                    workflow="discovery",
                    severity="LOW",
                    issue_type="NO_DATA",
                    message="Discovery registry has no opportunities.",
                    recommended_fix="Refresh discovery feed ingestion.",
                    action_url="/discovery-feed",
                )
            )
    except Exception as exc:  # pragma: no cover
        issues.append(
            P85WorkflowIssueRead(
                workflow="discovery",
                severity="HIGH",
                issue_type="BROKEN",
                message=str(exc)[:200],
                recommended_fix="Check discovery API and migrations.",
                action_url="/discovery-dashboard",
            )
        )

    daily, _ = list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=1, offset=0)
    if not daily:
        empty_workflows.append("daily_actions")
        issues.append(
            P85WorkflowIssueRead(
                workflow="daily_actions",
                severity="LOW",
                issue_type="NO_DATA",
                message="No daily actions generated yet.",
                recommended_fix="Open daily actions to refresh recommendations.",
                action_url="/daily-actions",
            )
        )

    try:
        build_collector_home(session, owner_user_id=owner_user_id)
    except Exception as exc:  # pragma: no cover
        issues.append(
            P85WorkflowIssueRead(
                workflow="collector_home",
                severity="CRITICAL",
                issue_type="BROKEN",
                message=str(exc)[:200],
                recommended_fix="Review collector home aggregation services.",
                action_url="/collector-home",
            )
        )

    broken = [i for i in issues if i.issue_type == "BROKEN"]
    score = max(0.0, 100.0 - len(broken) * 25.0 - len(empty_workflows) * 5.0)
    status = "HEALTHY" if not broken else "DEGRADED"
    if score < 50:
        status = "NEEDS_ATTENTION"

    return P85WorkflowHealthRead(
        health_score=round(score, 1),
        status=status,
        issues=issues[:30],
        stale_jobs=[],
        empty_workflows=empty_workflows,
    )
