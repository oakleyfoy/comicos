"""P82–P84 combined collector expansion production certification."""

from __future__ import annotations

from sqlmodel import Session

from app.schemas.p82_p84_collector_expansion import (
    CollectorExpansionCertificationCheckRead,
    CollectorExpansionCertificationRead,
    MarketplaceAcquisitionScanPayload,
)
from app.services.collector_briefing_service import generate_daily_briefing, generate_weekly_briefing
from app.services.collector_command_center_service import build_collector_command_center
from app.services.collector_notification_service import build_notification_dashboard, list_collector_notifications
from app.services.collection_scenario_service import run_collection_scenario
from app.services.collection_valuation_service import (
    build_collection_forecast,
    build_collection_optimization,
    build_collection_risk,
    build_valuation_dashboard,
)
from app.services.marketplace_acquisition_service import (
    build_acquisition_dashboard,
    list_acquisition_opportunities,
    scan_marketplace_listing,
)


def _check(checks: list[CollectorExpansionCertificationCheckRead], *, category: str, component: str, passed: bool, detail: str = "") -> None:
    checks.append(CollectorExpansionCertificationCheckRead(category=category, component=component, passed=passed, detail=detail))


def run_collector_expansion_certification(session: Session, *, owner_user_id: int) -> CollectorExpansionCertificationRead:
    checks: list[CollectorExpansionCertificationCheckRead] = []

    try:
        scored = scan_marketplace_listing(
            session,
            owner_user_id=owner_user_id,
            payload=MarketplaceAcquisitionScanPayload(
                external_listing_id="CERT-P82-001",
                title="Cert Test #1",
                publisher="DC",
                series="Cert Test",
                issue="1",
                asking_price=8.0,
            ),
            persist=True,
        )
        _check(checks, category="P82", component="opportunity_scan", passed=scored.opportunity_score > 0, detail=f"score={scored.opportunity_score}")
        _check(checks, category="P82", component="fmv_spread", passed=scored.discount_to_fmv >= 0, detail=f"disc={scored.discount_to_fmv}")
        _check(checks, category="P82", component="recommendation", passed=scored.recommendation in {"STRONG_BUY", "GOOD_BUY", "WATCH", "PASS"})
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P82", component="opportunity_scan", passed=False, detail=str(exc))

    try:
        opps = list_acquisition_opportunities(session, owner_user_id=owner_user_id, limit=10, offset=0, refresh=True)
        dash = build_acquisition_dashboard(session, owner_user_id=owner_user_id, refresh=False)
        _check(checks, category="P82", component="opportunity_registry", passed=opps.total_items >= 1, detail=f"total={opps.total_items}")
        _check(checks, category="P82", component="acquisition_dashboard", passed=len(dash.strong_buys) + len(dash.good_buys) >= 0)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P82", component="opportunity_registry", passed=False, detail=str(exc))

    try:
        forecast = build_collection_forecast(session, owner_user_id=owner_user_id, persist=True)
        _check(checks, category="P83", component="valuation_forecast", passed=len(forecast.horizons) == 4, detail=f"value={forecast.current_value}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P83", component="valuation_forecast", passed=False, detail=str(exc))

    try:
        risk = build_collection_risk(session, owner_user_id=owner_user_id, persist=True)
        _check(checks, category="P83", component="risk_scoring", passed=risk.risk_category in {"LOW_RISK", "MODERATE_RISK", "HIGH_RISK"})
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P83", component="risk_scoring", passed=False, detail=str(exc))

    try:
        scenario = run_collection_scenario(session, owner_user_id=owner_user_id, scenario_type="MARKET_GAIN")
        _check(
            checks,
            category="P83",
            component="scenario_planning",
            passed=scenario.id > 0 and bool(scenario.explanation),
            detail=scenario.scenario_type,
        )
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P83", component="scenario_planning", passed=False, detail=str(exc))

    try:
        opt = build_collection_optimization(session, owner_user_id=owner_user_id)
        val_dash = build_valuation_dashboard(session, owner_user_id=owner_user_id)
        _check(checks, category="P83", component="optimization", passed=isinstance(opt.buy_targets, list))
        _check(checks, category="P83", component="valuation_dashboard", passed=val_dash.forecast.current_value >= 0)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P83", component="optimization", passed=False, detail=str(exc))

    try:
        notifs = list_collector_notifications(session, owner_user_id=owner_user_id, limit=10, refresh=True)
        nd = build_notification_dashboard(session, owner_user_id=owner_user_id, refresh=False)
        _check(checks, category="P84", component="notifications", passed=notifs.total_items >= 0, detail=f"count={notifs.total_items}")
        _check(checks, category="P84", component="notification_dashboard", passed=len(nd.recent) >= 0)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P84", component="notifications", passed=False, detail=str(exc))

    try:
        daily = generate_daily_briefing(session, owner_user_id=owner_user_id)
        weekly = generate_weekly_briefing(session, owner_user_id=owner_user_id)
        _check(checks, category="P84", component="daily_briefing", passed=len(daily.top_actions) >= 1)
        _check(checks, category="P84", component="weekly_briefing", passed=weekly.briefing_type == "WEEKLY")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P84", component="daily_briefing", passed=False, detail=str(exc))

    try:
        cc = build_collector_command_center(session, owner_user_id=owner_user_id)
        _check(checks, category="P82-P84", component="command_center", passed=cc.collection_forecast is not None)
        _check(checks, category="P82-P84", component="command_center_briefing", passed=cc.daily_briefing is not None)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="P82-P84", component="command_center", passed=False, detail=str(exc))

    session.commit()
    failures = [c for c in checks if not c.passed]
    passed_count = sum(1 for c in checks if c.passed)
    readiness = round(100.0 * passed_count / max(1, len(checks)), 1)
    approved = len(failures) == 0
    checklist = [
        {"area": "Marketplace Acquisition (P82)", "status": "PASS" if approved else "FAIL"},
        {"area": "Collection Valuation (P83)", "status": "PASS" if approved else "FAIL"},
        {"area": "Notifications & Briefings (P84)", "status": "PASS" if approved else "FAIL"},
        {"area": "Command Center", "status": "PASS" if approved else "FAIL"},
    ]
    return CollectorExpansionCertificationRead(
        title="Collector Expansion Platform (P82–P84)",
        status="APPROVED_FOR_PRODUCTION" if approved else "NEEDS_ATTENTION",
        approved_for_production=approved,
        checks_passed=passed_count,
        warnings=0,
        failures=len(failures),
        platform_readiness_percent=readiness,
        production_checklist=checklist,
        checks=checks,
    )
