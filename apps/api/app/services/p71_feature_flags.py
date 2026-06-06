from app.core.config import get_settings


def p71_exit_recommendations_enabled() -> bool:
    return get_settings().p71_exit_recommendations_enabled


def p71_listing_intelligence_enabled() -> bool:
    return get_settings().p71_listing_intelligence_enabled


def p71_liquidity_enabled() -> bool:
    return get_settings().p71_liquidity_enabled


def p71_exit_queue_enabled() -> bool:
    return get_settings().p71_exit_queue_enabled


def p71_sell_dashboard_enabled() -> bool:
    return get_settings().p71_sell_dashboard_enabled
