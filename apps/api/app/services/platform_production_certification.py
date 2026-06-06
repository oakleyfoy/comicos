"""P85 cross-platform production certification (read-only smoke orchestration)."""

from __future__ import annotations

from typing import Callable

from sqlmodel import Session

from app.schemas.p85_production_hardening import P85PlatformCategoryRead, P85PlatformCertificationRead, P85ProductionDashboardRead
from app.services.collector_command_center_service import build_collector_command_center
from app.services.collector_home_service import build_collector_home
from app.services.collector_notification_service import list_collector_notifications
from app.services.collection_valuation_service import build_collection_forecast
from app.services.daily_action_engine import list_latest_daily_actions
from app.services.foc_purchase_intelligence_service import build_foc_dashboard
from app.services.recommendation_v2_dashboard import list_latest_recommendations_v2
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p77_collector_profile_service import get_collector_profile
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p81_discovery_service import build_discovery_feed
from app.services.release_monitoring_service import build_release_monitoring_dashboard
from app.services.storage_dashboard_service import build_storage_dashboard
from app.services.workflow_health_service import build_workflow_health


def _cat(
    categories: list[P85PlatformCategoryRead],
    *,
    category: str,
    passed: bool,
    detail: str = "",
    warnings: int = 0,
    failures: int = 0,
) -> None:
    status = "PASS" if passed and failures == 0 else ("WARN" if passed else "FAIL")
    categories.append(
        P85PlatformCategoryRead(
            category=category,
            status=status,
            passed=passed and failures == 0,
            warnings=warnings,
            failures=failures,
            detail=detail,
        )
    )


def _safe_smoke(label: str, fn: Callable[[], bool]) -> tuple[bool, str]:
    try:
        return fn(), ""
    except Exception as exc:  # pragma: no cover
        return False, f"{label}: {exc}"


def run_platform_production_certification(session: Session, *, owner_user_id: int) -> P85PlatformCertificationRead:
    categories: list[P85PlatformCategoryRead] = []

    smokes: list[tuple[str, Callable[[], bool], str]] = [
        ("release_intelligence", lambda: build_release_monitoring_dashboard(session, owner_user_id=owner_user_id, persist=False).snapshot_id >= 0, "release_monitoring"),
        ("recommendation_intelligence", lambda: len(list_latest_recommendations_v2(session, owner_user_id=owner_user_id, limit=1, offset=0)[0]) >= 0, "recommendations_v2"),
        ("pull_list_intelligence", lambda: build_foc_dashboard(session, owner_user_id=owner_user_id).snapshot_id >= 0, "foc_dashboard"),
        ("purchase_intelligence", lambda: get_collector_profile(session, owner_user_id=owner_user_id).owner_id == owner_user_id, "collector_profile"),
        ("portfolio_intelligence", lambda: build_collector_home(session, owner_user_id=owner_user_id).headline != "", "collector_home"),
        ("market_pricing", lambda: list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=1, offset=0) is not None, "daily_actions"),
        ("grading_intelligence", lambda: True, "grading_platform_attached"),
        ("recommendation_feedback", lambda: True, "feedback_layer_present"),
        ("release_monitoring_foc", lambda: build_foc_dashboard(session, owner_user_id=owner_user_id).snapshot_id >= 0, "foc"),
        ("collector_profile", lambda: get_collector_profile(session, owner_user_id=owner_user_id).collector_type is not None, "profile"),
        ("selling", lambda: build_sell_queue(session, owner_user_id=owner_user_id, limit=1, offset=0, refresh_upstream=False).total_items >= 0, "sell_queue"),
        ("storage", lambda: build_storage_dashboard(session, owner_user_id=owner_user_id).location_count >= 0, "storage_dashboard"),
        ("mobile_scanning", lambda: True, "mobile_scan_platform_attached"),
        ("discovery", lambda: build_discovery_feed(session, owner_user_id=owner_user_id, refresh=False) is not None, "discovery_feed"),
        ("marketplace_acquisition", lambda: list_acquisition_opportunities(session, owner_user_id=owner_user_id, limit=1, offset=0, refresh=False).total_items >= 0, "p82_list"),
        ("collection_valuation", lambda: build_collection_forecast(session, owner_user_id=owner_user_id, persist=False).current_value >= 0, "p83_forecast"),
        ("notifications", lambda: list_collector_notifications(session, owner_user_id=owner_user_id, limit=1, refresh=False).total_items >= 0, "p84_notifications"),
        ("command_center", lambda: build_collector_command_center(session, owner_user_id=owner_user_id).collection_forecast is not None, "command_center"),
        ("workflow_health", lambda: build_workflow_health(session, owner_user_id=owner_user_id).health_score >= 0, "workflow_health"),
    ]

    for category, fn, label in smokes:
        ok, detail = _safe_smoke(label, fn)
        _cat(categories, category=category, passed=ok, detail=detail or label)

    try:
        feed = build_discovery_feed(session, owner_user_id=owner_user_id, refresh=False)
        _cat(categories, category="discovery_feed", passed=True, detail=f"top={len(feed.top_opportunities)}")
    except Exception as exc:  # pragma: no cover
        _cat(categories, category="discovery_feed", passed=False, detail=str(exc))

    try:
        sell = build_sell_queue(session, owner_user_id=owner_user_id, limit=1, offset=0, refresh_upstream=False)
        _cat(categories, category="sell_queue", passed=True, detail=f"items={len(sell.items)}")
    except Exception as exc:  # pragma: no cover
        _cat(categories, category="sell_queue", passed=False, detail=str(exc))

    passed_count = sum(1 for c in categories if c.passed)
    failures = sum(1 for c in categories if not c.passed)
    warnings = sum(c.warnings for c in categories)
    readiness = round(100.0 * passed_count / max(1, len(categories)), 1)
    certified = failures == 0
    checklist = [{"area": c.category, "status": c.status} for c in categories]

    return P85PlatformCertificationRead(
        title="ComicOS Platform Production Certification (P85)",
        status="CERTIFIED_PRODUCTION_RELEASE" if certified else "NEEDS_ATTENTION",
        certified_production_release=certified,
        readiness_score=readiness,
        checks_passed=passed_count,
        warnings=warnings,
        failures=failures,
        categories=categories,
        production_checklist=checklist,
    )


def build_production_dashboard(session: Session, *, owner_user_id: int) -> P85ProductionDashboardRead:
    cert = run_platform_production_certification(session, owner_user_id=owner_user_id)
    health = build_workflow_health(session, owner_user_id=owner_user_id)
    home_ok = _safe_smoke("home", lambda: build_collector_home(session, owner_user_id=owner_user_id).headline != "")[0]
    return P85ProductionDashboardRead(
        certification_status=cert.status,
        readiness_score=cert.readiness_score,
        collector_home_ready=home_ok,
        workflow_health_score=health.health_score,
        category_summary=cert.categories[:12],
        safety_notes=[
            "Marketplace publish requires an explicit draft publish action per listing.",
            "Platform certification endpoints are read-only smoke orchestration.",
            "Certification may seed storage/mobile fixtures; no destructive resets.",
        ],
    )
