"""P63 Market Intelligence feature flags."""

from __future__ import annotations

from app.core.config import get_settings


def p63_market_intelligence_enabled() -> bool:
    return bool(get_settings().p63_market_intelligence_enabled)


def p63_portfolio_performance_enabled() -> bool:
    return bool(get_settings().p63_portfolio_performance_enabled)


def p63_sell_signals_enabled() -> bool:
    return bool(get_settings().p63_sell_signals_enabled)


def p63_acquisition_opportunities_enabled() -> bool:
    return bool(get_settings().p63_acquisition_opportunities_enabled)


def p63_market_signals_enabled() -> bool:
    return bool(get_settings().p63_market_signals_enabled)
