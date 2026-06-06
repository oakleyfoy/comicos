"""P85 unified collector home — aggregates P77–P84 without duplicating engines."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.schemas.p85_production_hardening import (
    P85CollectorHomeActionRead,
    P85CollectorHomeRead,
    P85CollectorHomeSectionRead,
)
from app.services.collection_valuation_service import build_collection_forecast, build_collection_risk
from app.services.daily_action_engine import list_latest_daily_actions
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p77_personalization_engine import load_personalization_context
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p81_discovery_personalization_service import list_alerts, list_future_pull_list
from app.services.storage_dashboard_service import build_storage_dashboard


_HOME_LIMIT = 10


def _section(key: str, title: str, items: list[dict], *, empty_hint: str) -> P85CollectorHomeSectionRead:
    return P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=items[:_HOME_LIMIT],
        empty_hint=empty_hint if not items else "",
        count=len(items),
    )


def build_collector_home(session: Session, *, owner_user_id: int) -> P85CollectorHomeRead:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    daily_items, _ = list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0)
    todays: list[P85CollectorHomeActionRead] = []
    for row in daily_items:
        todays.append(
            P85CollectorHomeActionRead(
                title=row.title,
                action_type=row.action_type,
                priority_score=float(row.priority_score),
                source="daily_actions",
                action_url="/daily-actions",
            )
        )

    buys = list_acquisition_opportunities(
        session,
        owner_user_id=owner_user_id,
        recommendation="STRONG_BUY",
        limit=_HOME_LIMIT,
        offset=0,
        refresh=False,
    )
    sell = build_sell_queue(session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0, refresh_upstream=False)
    grade_items = [s for s in sell.items if s.fmv >= 20][: _HOME_LIMIT]
    foc = list_future_pull_list(session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0, refresh=False)
    alerts = list_alerts(session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0)
    forecast = build_collection_forecast(session, owner_user_id=owner_user_id, persist=False)
    risk = build_collection_risk(session, owner_user_id=owner_user_id, persist=False)

    storage_issues: list[dict] = []
    try:
        dash = build_storage_dashboard(session, owner_user_id=owner_user_id)
        if dash.unassigned_books > 0:
            storage_issues.append({"type": "UNASSIGNED", "count": dash.unassigned_books, "label": "Unassigned copies"})
    except Exception:  # pragma: no cover
        storage_issues = []

    inv_count = len(
        list(
            session.exec(
                select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).where(InventoryCopy.hold_status != "sold").limit(1)
            ).all()
        )
    )
    headline = "What should I do today?"
    if inv_count == 0:
        headline = "Start by adding inventory or importing an order."

    sections = [
        _section(
            "buy_alerts",
            "Buy alerts",
            [{"title": i.title, "score": i.opportunity_score, "url": f"/marketplace-opportunity/{i.id}"} for i in buys.items],
            empty_hint="Scan marketplace opportunities or check discovery feed.",
        ),
        _section(
            "sell_alerts",
            "Sell alerts",
            [{"title": s.title, "fmv": s.fmv, "priority": s.priority} for s in sell.items if s.priority in {"HIGH", "MEDIUM"}],
            empty_hint="Review sell queue after FMV is set on your copies.",
        ),
        _section(
            "grade_alerts",
            "Grade alerts",
            [{"title": g.title, "fmv": g.fmv} for g in grade_items],
            empty_hint="High-FMV raw copies will appear here from the sell queue.",
        ),
        _section(
            "foc_alerts",
            "FOC alerts",
            [{"title": p.title, "status": p.pipeline_status} for p in foc.items],
            empty_hint="Add future releases or watchlists to see FOC reminders.",
        ),
        _section(
            "storage_issues",
            "Storage issues",
            storage_issues,
            empty_hint="Assign storage locations as you add inventory.",
        ),
        _section(
            "marketplace_deals",
            "Marketplace deals",
            [{"title": i.title, "recommendation": i.recommendation} for i in buys.items],
            empty_hint="Run marketplace acquisition scan or refresh deals.",
        ),
        _section(
            "future_pull_list",
            "Future pull list",
            [{"title": p.title, "action": p.recommendation_action} for p in foc.items],
            empty_hint="Personalize discovery to build your future pull list.",
        ),
        _section(
            "discovery_alerts",
            "Discovery alerts",
            [{"title": a.title, "priority": a.priority} for a in alerts.items],
            empty_hint="No active discovery alerts — check the discovery dashboard.",
        ),
    ]

    return P85CollectorHomeRead(
        headline=headline,
        todays_actions=todays[:_HOME_LIMIT],
        sections=sections,
        budget_status={
            "state": ctx.budget_state,
            "monthly_budget": ctx.monthly_budget,
            "monthly_spend": ctx.monthly_spend,
        },
        portfolio_movement={
            "current_value": forecast.current_value,
            "risk_category": risk.risk_category,
            "risk_score": risk.risk_score,
        },
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
