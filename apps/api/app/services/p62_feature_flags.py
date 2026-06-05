"""P62 Recommendation Intelligence feature flags."""

from __future__ import annotations

from app.core.config import get_settings


def p62_v3_preview_enabled() -> bool:
    return bool(get_settings().p62_v3_preview_enabled)


def p62_v3_persist_enabled() -> bool:
    return bool(get_settings().p62_v3_persist_enabled)


def p62_read_only_get_enabled() -> bool:
    return bool(get_settings().p62_read_only_get_enabled)


def p62_foc_enabled() -> bool:
    return bool(get_settings().p62_foc_enabled)


def p62_pull_forecast_enabled() -> bool:
    return bool(get_settings().p62_pull_forecast_enabled)


def p62_auto_watchlist_enabled() -> bool:
    return bool(get_settings().p62_auto_watchlist_enabled)
