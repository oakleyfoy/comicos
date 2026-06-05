"""P66 Variant & Market Intelligence feature flags."""

from __future__ import annotations

from app.core.config import get_settings


def p66_variant_intelligence_enabled() -> bool:
    return bool(get_settings().p66_variant_intelligence_enabled)


def p66_quantity_intelligence_enabled() -> bool:
    return bool(get_settings().p66_quantity_intelligence_enabled)


def p66_market_pricing_enabled() -> bool:
    return bool(get_settings().p66_market_pricing_enabled)


def p66_variant_decision_enabled() -> bool:
    return bool(get_settings().p66_variant_decision_enabled)
