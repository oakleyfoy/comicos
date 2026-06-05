"""P67 Portfolio Analytics feature flags."""

from app.core.config import get_settings


def p67_portfolio_analytics_enabled() -> bool:
    return get_settings().p67_portfolio_analytics_enabled


def p67_collection_analytics_enabled() -> bool:
    return get_settings().p67_collection_analytics_enabled


def p67_recommendation_performance_enabled() -> bool:
    return get_settings().p67_recommendation_performance_enabled


def p67_grading_analytics_enabled() -> bool:
    return get_settings().p67_grading_analytics_enabled


def p67_investor_dashboard_enabled() -> bool:
    return get_settings().p67_investor_dashboard_enabled
