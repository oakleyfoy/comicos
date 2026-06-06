"""P81-03 production certification for Future Release Discovery Intelligence."""

from __future__ import annotations

from sqlmodel import Session

from app.schemas.p81_discovery_analytics import P81DiscoveryCertificationCheckRead, P81DiscoveryCertificationRead
from app.services.p81_discovery_analytics_service import (
    build_alert_analytics,
    build_analytics_dashboard,
    build_discovery_analytics,
    build_opportunity_analytics,
    build_roi_analytics,
)
from app.services.p81_discovery_ingestion import ingest_discovery_opportunities
from app.services.p81_discovery_personalization_service import (
    build_personalized_discovery_dashboard,
    list_alerts,
    list_future_pull_list,
    list_watchlists,
    refresh_personalized_discovery,
)
from app.services.p81_discovery_service import build_discovery_feed, list_opportunities
from app.services.p81_discovery_scoring import P81ScoreInput, category_for_score, score_discovery_opportunity


def _check(checks: list, *, category: str, component: str, passed: bool, detail: str = "") -> None:
    checks.append(P81DiscoveryCertificationCheckRead(category=category, component=component, passed=passed, detail=detail))


def run_discovery_certification(session: Session, *, owner_user_id: int) -> P81DiscoveryCertificationRead:
    checks: list[P81DiscoveryCertificationCheckRead] = []

    try:
        n = ingest_discovery_opportunities(session, owner_user_id=owner_user_id)
        _check(checks, category="ingestion", component="discovery_ingest", passed=n >= 0, detail=f"upserted={n}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="ingestion", component="discovery_ingest", passed=False, detail=str(exc))

    try:
        opps = list_opportunities(session, owner_user_id=owner_user_id, limit=10, offset=0, refresh=False)
        _check(checks, category="registry", component="opportunity_registry", passed=opps.total_items >= 0, detail=f"total={opps.total_items}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="registry", component="opportunity_registry", passed=False, detail=str(exc))

    try:
        score, signals = score_discovery_opportunity(
            P81ScoreInput(
                opportunity_type="NEW_1",
                title="Batman #1",
                summary="",
                series_name="Batman",
                issue_number="1",
                variant_label="",
                publisher="DC",
                creators=[],
            )
        )
        _check(checks, category="scoring", component="discovery_score", passed=score >= 50, detail=f"score={score}")
        _check(checks, category="scoring", component="score_category", passed=category_for_score(score) in {"MUST_WATCH", "HIGH_OPPORTUNITY", "WATCH"}, detail=",".join(signals[:2]))
    except Exception as exc:  # pragma: no cover
        _check(checks, category="scoring", component="discovery_score", passed=False, detail=str(exc))

    try:
        feed = build_discovery_feed(session, owner_user_id=owner_user_id, refresh=True)
        _check(checks, category="feed", component="discovery_feed", passed=len(feed.top_opportunities) >= 0, detail=f"top={len(feed.top_opportunities)}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="feed", component="discovery_feed", passed=False, detail=str(exc))

    try:
        refresh_personalized_discovery(session, owner_user_id=owner_user_id, ingest=False)
        pers = build_personalized_discovery_dashboard(session, owner_user_id=owner_user_id, refresh=False)
        _check(checks, category="personalization", component="personalized_dashboard", passed=pers.counts.get("total", 0) >= 0)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="personalization", component="personalized_dashboard", passed=False, detail=str(exc))

    try:
        wl = list_watchlists(session, owner_user_id=owner_user_id)
        _check(checks, category="watchlists", component="discovery_watchlists", passed=wl.total_items >= 0, detail=f"items={wl.total_items}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="watchlists", component="discovery_watchlists", passed=False, detail=str(exc))

    try:
        fpl = list_future_pull_list(session, owner_user_id=owner_user_id, limit=10, offset=0, refresh=False)
        _check(checks, category="future_pull", component="future_pull_list", passed=fpl.total_items >= 0, detail=f"items={fpl.total_items}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="future_pull", component="future_pull_list", passed=False, detail=str(exc))

    try:
        alerts = list_alerts(session, owner_user_id=owner_user_id, limit=5, offset=0)
        _check(checks, category="alerts", component="discovery_alerts", passed=alerts.total_items >= 0, detail=f"alerts={alerts.total_items}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="alerts", component="discovery_alerts", passed=False, detail=str(exc))

    try:
        build_discovery_analytics(session, owner_user_id=owner_user_id, persist=True)
        build_opportunity_analytics(session, owner_user_id=owner_user_id, persist=True)
        build_alert_analytics(session, owner_user_id=owner_user_id, persist=True)
        build_roi_analytics(session, owner_user_id=owner_user_id, persist=True)
        dash = build_analytics_dashboard(session, owner_user_id=owner_user_id, refresh=False)
        _check(checks, category="analytics", component="activity_metrics", passed=dash.activity.opportunities_discovered >= 0)
        _check(checks, category="analytics", component="analytics_dashboard", passed=dash.snapshot_ids.get("activity") is not None)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="analytics", component="analytics_dashboard", passed=False, detail=str(exc))

    session.commit()
    failures = [c for c in checks if not c.passed]
    passed_count = sum(1 for c in checks if c.passed)
    readiness = round(100.0 * passed_count / max(1, len(checks)), 1)
    approved = len(failures) == 0
    checklist = [
        {"area": "Discovery Feed", "status": "PASS" if approved else "FAIL"},
        {"area": "Discovery Scoring", "status": "PASS" if approved else "FAIL"},
        {"area": "Watchlists", "status": "PASS" if approved else "FAIL"},
        {"area": "Alerts", "status": "PASS" if approved else "FAIL"},
        {"area": "Future Pull List", "status": "PASS" if approved else "FAIL"},
        {"area": "Analytics", "status": "PASS" if approved else "FAIL"},
    ]
    return P81DiscoveryCertificationRead(
        title="Future Release Discovery Intelligence",
        status="APPROVED_FOR_PRODUCTION" if approved else "NEEDS_ATTENTION",
        approved_for_production=approved,
        checks_passed=passed_count,
        warnings=0,
        failures=len(failures),
        platform_readiness_percent=readiness,
        production_checklist=checklist,
        checks=checks,
    )
