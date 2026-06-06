"""P82–P84 unified collector command center."""

from __future__ import annotations

from sqlmodel import Session

from app.schemas.p82_p84_collector_expansion import CollectorCommandCenterRead
from app.services.collector_briefing_service import get_daily_briefing
from app.services.collector_notification_service import build_notification_dashboard, list_collector_notifications
from app.services.collection_valuation_service import build_collection_forecast, build_collection_optimization, build_collection_risk
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p77_personalization_engine import load_personalization_context
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p81_discovery_personalization_service import list_alerts, list_future_pull_list


def build_collector_command_center(session: Session, *, owner_user_id: int) -> CollectorCommandCenterRead:
    deals = list_acquisition_opportunities(session, owner_user_id=owner_user_id, limit=12, offset=0, refresh=True)
    buys = list_acquisition_opportunities(session, owner_user_id=owner_user_id, recommendation="STRONG_BUY", limit=8, offset=0, refresh=False)
    forecast = build_collection_forecast(session, owner_user_id=owner_user_id, persist=False)
    risk = build_collection_risk(session, owner_user_id=owner_user_id, persist=False)
    notif_dash = build_notification_dashboard(session, owner_user_id=owner_user_id, refresh=True)
    daily = get_daily_briefing(session, owner_user_id=owner_user_id, generate=True)
    sell = build_sell_queue(session, owner_user_id=owner_user_id, limit=10, offset=0, refresh_upstream=False)
    foc = list_future_pull_list(session, owner_user_id=owner_user_id, limit=8, offset=0, refresh=False)
    discovery_alerts = list_alerts(session, owner_user_id=owner_user_id, limit=8, offset=0)
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    opt = build_collection_optimization(session, owner_user_id=owner_user_id)
    risk_alerts = [n for n in notif_dash.critical if n.notification_type == "PORTFOLIO_RISK_ALERT"]
    if not risk_alerts and risk.risk_category == "HIGH_RISK":
        risk_alerts = list_collector_notifications(session, owner_user_id=owner_user_id, limit=5, refresh=False).items[:1]

    return CollectorCommandCenterRead(
        marketplace_deals=[d for d in deals.items if d.recommendation in {"STRONG_BUY", "GOOD_BUY"}][:10],
        collection_forecast=forecast,
        risk_alerts=risk_alerts,
        daily_briefing=daily,
        top_buy_opportunities=buys.items[:8],
        top_sell_opportunities=[{"title": s.title, "fmv": s.fmv, "priority": s.priority} for s in sell.items[:8]],
        upcoming_foc=[{"title": p.title, "status": p.pipeline_status} for p in foc.items[:8]],
        discovery_alerts=[{"title": a.title, "priority": a.priority} for a in discovery_alerts.items[:8]],
        budget_status={"state": ctx.budget_state, "monthly_budget": ctx.monthly_budget, "monthly_spend": ctx.monthly_spend},
        portfolio_movement={"current_value": forecast.current_value, "risk_category": risk.risk_category},
        storage_warnings=[],
        grading_candidates=opt.grade_candidates[:8],
    )
