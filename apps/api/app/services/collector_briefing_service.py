"""P84 daily and weekly collector briefings."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import CollectorBriefing, utc_now
from app.schemas.p82_p84_collector_expansion import CollectorBriefingRead
from app.services.collector_notification_service import list_collector_notifications, refresh_collector_notifications
from app.services.collection_valuation_service import build_collection_forecast, build_collection_risk
from app.services.marketplace_acquisition_service import build_acquisition_dashboard, list_acquisition_opportunities
from app.services.p77_personalization_engine import load_personalization_context
from app.services.sell_candidate_service import build_sell_candidate_briefing_highlights
from app.services.listing_draft_service import build_listing_draft_briefing
from app.services.p89_market_pricing_service import build_market_pricing_briefing_summary
from app.services.marketplace_command_center_service import build_marketplace_command_center_briefing_section
from app.services.p81_discovery_personalization_service import list_future_pull_list, list_personalized_discovery


def _best_buy_notification_titles(session: Session, *, owner_user_id: int, limit: int = 5) -> list[str]:
    from app.models.p82_p84_collector_expansion import CollectorNotification

    rows = session.exec(
        select(CollectorNotification)
        .where(CollectorNotification.owner_user_id == owner_user_id)
        .where(CollectorNotification.notification_type == "BEST_BUY_FOUND")
        .where(CollectorNotification.status != "DISMISSED")
        .order_by(CollectorNotification.created_at.desc())
        .limit(limit)
    ).all()
    return [row.title for row in rows]


def _marketplace_alert_titles(session: Session, *, owner_user_id: int, limit: int = 5) -> list[str]:
    from app.models.p88_marketplace_monitoring import MarketplaceAlert

    rows = session.exec(
        select(MarketplaceAlert)
        .where(MarketplaceAlert.owner_user_id == owner_user_id)
        .where(MarketplaceAlert.status == "NEW")
        .order_by(MarketplaceAlert.created_at.desc())
        .limit(limit)
    ).all()
    return [row.title for row in rows]


def _to_read(row: CollectorBriefing) -> CollectorBriefingRead:
    return CollectorBriefingRead(
        id=int(row.id or 0),
        briefing_type=row.briefing_type,
        briefing_date=row.briefing_date,
        sections=dict(row.sections_json or {}),
        top_actions=list(row.top_actions_json or []),
        created_at=row.created_at,
    )


def _latest_briefing(session: Session, *, owner_user_id: int, briefing_type: str, briefing_date: date) -> CollectorBriefing | None:
    return session.exec(
        select(CollectorBriefing)
        .where(
            CollectorBriefing.owner_user_id == owner_user_id,
            CollectorBriefing.briefing_type == briefing_type,
            CollectorBriefing.briefing_date == briefing_date,
        )
        .order_by(CollectorBriefing.id.desc())
        .limit(1)
    ).first()


def generate_daily_briefing(session: Session, *, owner_user_id: int, briefing_date: date | None = None) -> CollectorBriefingRead:
    day = briefing_date or date.today()
    existing = _latest_briefing(session, owner_user_id=owner_user_id, briefing_type="DAILY", briefing_date=day)
    if existing:
        return _to_read(existing)
    refresh_collector_notifications(session, owner_user_id=owner_user_id)
    deals = list_acquisition_opportunities(session, owner_user_id=owner_user_id, limit=8, offset=0, refresh=False)
    discovery = list_personalized_discovery(session, owner_user_id=owner_user_id, limit=5, offset=0, refresh=False)
    foc = list_future_pull_list(session, owner_user_id=owner_user_id, limit=5, offset=0, refresh=False)
    forecast = build_collection_forecast(session, owner_user_id=owner_user_id, persist=False)
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    sell_highlights = build_sell_candidate_briefing_highlights(session, owner_user_id=owner_user_id)
    market_pricing_summary = build_market_pricing_briefing_summary(session, owner_user_id=owner_user_id)
    listing_drafts = build_listing_draft_briefing(session, owner_user_id=owner_user_id)
    sections = {
        "discovery_opportunities": [d.opportunity.title for d in discovery.items[:5]],
        "marketplace_deals": [d.title for d in deals.items if d.recommendation in {"STRONG_BUY", "GOOD_BUY"}][:5],
        "marketplace_alerts": _marketplace_alert_titles(session, owner_user_id=owner_user_id),
        "best_buy_found": _best_buy_notification_titles(session, owner_user_id=owner_user_id),
        "marketplace_command_center": build_marketplace_command_center_briefing_section(
            session, owner_user_id=owner_user_id
        ),
        "foc_reminders": [p.title for p in foc.items[:5]],
        "sell_opportunities": sell_highlights,
        "market_pricing_summary": market_pricing_summary,
        "listing_drafts": listing_drafts,
        "sell_alerts": [
            t
            for t in (
                sell_highlights.get("top_sell_candidate"),
                sell_highlights.get("highest_profit_candidate"),
                sell_highlights.get("highest_confidence_candidate"),
            )
            if t
        ],
        "portfolio_movement": {"current_value": forecast.current_value},
        "budget_warnings": [ctx.budget_state] if ctx.budget_state != "GREEN" else [],
    }
    actions = []
    if sections["marketplace_deals"] or sections["marketplace_alerts"] or sections["best_buy_found"]:
        actions.append("Open Marketplace Command Center for today's best buys")
        actions.append("Review marketplace alerts and buy opportunities")
    if sections["foc_reminders"]:
        actions.append("Confirm FOC / future pull items")
    if sections["sell_alerts"]:
        actions.append("Review Sell Candidates for exit opportunities")
    if not actions:
        actions.append("Scan discovery feed for new releases")
    row = CollectorBriefing(
        owner_user_id=owner_user_id,
        briefing_type="DAILY",
        briefing_date=day,
        sections_json=sections,
        top_actions_json=actions[:8],
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return _to_read(row)


def generate_weekly_briefing(session: Session, *, owner_user_id: int, briefing_date: date | None = None) -> CollectorBriefingRead:
    day = briefing_date or date.today()
    existing = _latest_briefing(session, owner_user_id=owner_user_id, briefing_type="WEEKLY", briefing_date=day)
    if existing:
        return _to_read(existing)
    forecast = build_collection_forecast(session, owner_user_id=owner_user_id, persist=True)
    risk = build_collection_risk(session, owner_user_id=owner_user_id, persist=True)
    acq = build_acquisition_dashboard(session, owner_user_id=owner_user_id, refresh=True)
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    sections = {
        "fmv_changes": {"current_value": forecast.current_value, "horizon_90": forecast.horizons[1].forecast_value if len(forecast.horizons) > 1 else forecast.current_value},
        "budget_usage": {"state": ctx.budget_state, "monthly_budget": ctx.monthly_budget},
        "missed_opportunities": [p.title for p in acq.pass_list[:3]],
        "upcoming_releases": [p.title for p in acq.watch[:5]],
        "risk_summary": {"category": risk.risk_category, "score": risk.risk_score},
        "roi_changes": {"note": "Weekly ROI tracked via sell queue and acquisition spread"},
        "best_buy_found": _best_buy_notification_titles(session, owner_user_id=owner_user_id),
        "marketplace_alerts": _marketplace_alert_titles(session, owner_user_id=owner_user_id),
        "marketplace_command_center": build_marketplace_command_center_briefing_section(
            session, owner_user_id=owner_user_id
        ),
    }
    actions = [
        "Rebalance portfolio using optimization view",
        "Run a MARKET_GAIN or MARKET_DROP scenario",
        "Update watchlists for upcoming releases",
    ]
    row = CollectorBriefing(
        owner_user_id=owner_user_id,
        briefing_type="WEEKLY",
        briefing_date=day,
        sections_json=sections,
        top_actions_json=actions,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return _to_read(row)


def get_daily_briefing(session: Session, *, owner_user_id: int, generate: bool = True) -> CollectorBriefingRead:
    day = date.today()
    row = _latest_briefing(session, owner_user_id=owner_user_id, briefing_type="DAILY", briefing_date=day)
    if row:
        return _to_read(row)
    if generate:
        return generate_daily_briefing(session, owner_user_id=owner_user_id, briefing_date=day)
    return CollectorBriefingRead(id=0, briefing_type="DAILY", briefing_date=day, sections={}, top_actions=[], created_at=utc_now())


def get_weekly_briefing(session: Session, *, owner_user_id: int, generate: bool = True) -> CollectorBriefingRead:
    day = date.today()
    row = _latest_briefing(session, owner_user_id=owner_user_id, briefing_type="WEEKLY", briefing_date=day)
    if row:
        return _to_read(row)
    if generate:
        return generate_weekly_briefing(session, owner_user_id=owner_user_id, briefing_date=day)
    week_start = day - timedelta(days=day.weekday())
    return CollectorBriefingRead(id=0, briefing_type="WEEKLY", briefing_date=week_start, sections={}, top_actions=[], created_at=utc_now())
