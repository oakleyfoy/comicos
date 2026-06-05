from app.core.config import get_settings


def p68_market_pricing_enabled() -> bool:
    return get_settings().p68_market_pricing_enabled


def p68_ebay_provider_enabled() -> bool:
    return get_settings().p68_ebay_provider_enabled


def p68_manual_fmv_enabled() -> bool:
    return get_settings().p68_manual_fmv_enabled


def p68_auto_overwrite_inventory_fmv() -> bool:
    return get_settings().p68_auto_overwrite_inventory_fmv
