"""P63 integrated platform build."""

from __future__ import annotations

from sqlmodel import Session

from app.services.market_intelligence_certification import get_market_platform_certification
from app.services.market_signal_service import build_market_signals
from app.services.p63_acquisition_opportunity_service import build_acquisition_opportunities
from app.services.p63_feature_flags import (
    p63_acquisition_opportunities_enabled,
    p63_market_intelligence_enabled,
    p63_market_signals_enabled,
    p63_portfolio_performance_enabled,
    p63_sell_signals_enabled,
)
from app.services.portfolio_performance_service import build_portfolio_performance_snapshot
from app.services.sell_signal_service import build_sell_signals


def run_market_intelligence_platform_build(session: Session, *, owner_user_id: int) -> dict:
    if not p63_market_intelligence_enabled():
        return {"steps": {"platform": "DISABLED"}, "certification": {"platform_ready": False}}

    steps: dict[str, str] = {}
    if p63_portfolio_performance_enabled():
        build_portfolio_performance_snapshot(session, owner_user_id=owner_user_id)
        steps["portfolio"] = "OK"
    if p63_sell_signals_enabled():
        build_sell_signals(session, owner_user_id=owner_user_id)
        steps["sell_signals"] = "OK"
    if p63_acquisition_opportunities_enabled():
        build_acquisition_opportunities(session, owner_user_id=owner_user_id)
        steps["acquisition"] = "OK"
    if p63_market_signals_enabled():
        build_market_signals(session, owner_user_id=owner_user_id)
        steps["market_signals"] = "OK"
    cert = get_market_platform_certification(session, owner_user_id=owner_user_id)
    return {"steps": steps, "certification": cert}
