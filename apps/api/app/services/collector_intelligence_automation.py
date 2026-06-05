"""P62 weekly collector intelligence pipeline."""

from __future__ import annotations

from sqlmodel import Session

from app.services.auto_watchlist_service import refresh_auto_watchlists
from app.services.buy_queue_service import rebuild_buy_queue
from app.services.collector_intelligence_certification import get_collector_platform_certification
from app.services.demand_velocity_service import compute_demand_velocity
from app.services.foc_intelligence_service import generate_foc_alerts
from app.services.future_pull_forecast_service import generate_future_pull_forecast
from app.services.p62_feature_flags import (
    p62_auto_watchlist_enabled,
    p62_foc_enabled,
    p62_pull_forecast_enabled,
)
from app.services.spec_opportunity_service import build_spec_opportunities


def run_collector_intelligence_pipeline(
    session: Session,
    *,
    owner_user_id: int,
) -> dict:
    steps: dict[str, str] = {}
    if p62_foc_enabled():
        generate_foc_alerts(session, owner_user_id=owner_user_id)
        steps["foc_alerts"] = "OK"
    build_spec_opportunities(session, owner_user_id=owner_user_id, limit=50)
    steps["spec_opportunities"] = "OK"
    for window in (7, 14, 28):
        compute_demand_velocity(session, window_days=window)
    steps["velocity"] = "OK"
    rebuild_buy_queue(session, owner_user_id=owner_user_id)
    steps["buy_queue"] = "OK"
    if p62_pull_forecast_enabled():
        generate_future_pull_forecast(session, owner_user_id=owner_user_id)
        steps["pull_forecast"] = "OK"
    if p62_auto_watchlist_enabled():
        refresh_auto_watchlists(session, owner_user_id=owner_user_id)
        steps["auto_watchlists"] = "OK"
    cert = get_collector_platform_certification(session, owner_user_id=owner_user_id)
    return {"steps": steps, "certification": cert}
