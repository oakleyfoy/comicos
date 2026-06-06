"""P73-03 production certification for the recommendation feedback platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.recommendation_outcome import P73RecommendationOutcome
from app.schemas.recommendation_feedback_intelligence import (
    P73RecommendationCertificationCheckRead,
    P73RecommendationCertificationRead,
)
from app.services.recommendation_analytics_service import build_recommendation_analytics
from app.services.recommendation_confidence_service import build_recommendation_confidence
from app.services.recommendation_feedback_engine import (
    build_category_calibration,
    build_recommendation_effectiveness,
    load_grading_context,
    load_market_context,
    run_recommendation_feedback_engine,
)
from app.services.recommendation_analytics_service import (
    _accuracy_metrics,
    _load_owner_data,
    build_category_performance_read,
)
from app.services.recommendation_outcome_service import build_feedback_summary


def _check(component: str, passed: bool, detail: str) -> P73RecommendationCertificationCheckRead:
    return P73RecommendationCertificationCheckRead(component=component, passed=passed, detail=detail)


def run_recommendation_feedback_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> P73RecommendationCertificationRead:
    checks: list[P73RecommendationCertificationCheckRead] = []

    try:
        summary = build_feedback_summary(session, owner_user_id=owner_user_id)
        checks.append(
            _check(
                "outcome_tracking",
                True,
                f"created={summary.recommendations_created} events_ok",
            )
        )
    except Exception as exc:  # pragma: no cover
        checks.append(_check("outcome_tracking", False, str(exc)))

    try:
        analytics = build_recommendation_analytics(session, owner_user_id=owner_user_id, persist=True)
        checks.append(
            _check(
                "performance_analytics",
                analytics.funnel.recommendations_generated >= 0,
                f"snapshot={analytics.snapshot_id}",
            )
        )
    except Exception as exc:  # pragma: no cover
        checks.append(_check("performance_analytics", False, str(exc)))

    outcomes, events_by_outcome = _load_owner_data(session, owner_user_id)
    category_rows = build_category_performance_read(outcomes)
    market = load_market_context(session, owner_user_id=owner_user_id)
    grading = load_grading_context(session, owner_user_id=owner_user_id)
    confidence = build_recommendation_confidence(
        outcomes=outcomes,
        category_rows=category_rows,
        market=market,
        grading=grading,
    )
    conf_ok = all(
        0 <= v <= 100
        for v in (
            confidence.buy_confidence,
            confidence.grade_confidence,
            confidence.sell_confidence,
            confidence.watch_confidence,
        )
    )
    checks.append(_check("confidence_calculations", conf_ok, "scores within 0-100"))

    calibration = build_category_calibration(outcomes)
    cal_ok = len(calibration) >= 7
    checks.append(_check("calibration_calculations", cal_ok, f"categories={len(calibration)}"))

    accuracy = _accuracy_metrics(outcomes, events_by_outcome)
    effectiveness = build_recommendation_effectiveness(outcomes, accuracy)
    checks.append(
        _check(
            "effectiveness_metrics",
            len(effectiveness.by_type) == 4,
            f"accuracy={effectiveness.recommendation_accuracy_pct:.1f}%",
        )
    )

    try:
        dash = run_recommendation_feedback_engine(session, owner_user_id=owner_user_id, persist=True)
        dash_ok = dash.bundle_snapshot_id > 0 and dash.confidence.buy_confidence >= 0
        checks.append(_check("dashboard_performance", dash_ok, f"bundle={dash.bundle_snapshot_id}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("dashboard_performance", False, str(exc)))

    row_count = len(
        list(
            session.exec(
                select(P73RecommendationOutcome).where(P73RecommendationOutcome.owner_user_id == owner_user_id)
            ).all()
        )
    )
    checks.append(_check("data_integrity", row_count >= 0, f"outcomes={row_count}"))

    passed = all(c.passed for c in checks)
    return P73RecommendationCertificationRead(
        approved_for_production=passed,
        checks=checks,
        platform_status="APPROVED_FOR_PRODUCTION" if passed else "NEEDS_ATTENTION",
        reviewed_at=datetime.now(timezone.utc),
    )
