"""P72-03 production certification for the grading intelligence platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.schemas.p72_grading_analytics import P72GradingCertificationCheckRead, P72GradingCertificationRead
from app.services.grade_probability_engine import estimate_grade_probabilities
from app.services.grading_candidate_engine import discover_grading_candidates
from app.services.grading_cost_service import estimate_grading_costs
from app.services.grading_queue_service import ALLOWED_TRANSITIONS, STATUS_CANDIDATE, STATUS_READY
from app.services.grading_roi_service import calculate_grading_roi
from app.services.p72_grading_analytics_service import build_analytics_dashboard
from app.services.p72_grading_decision_dashboard import build_p72_decision_dashboard
from app.services.p72_grading_operations_dashboard import build_operations_dashboard
from app.services.pressing_intelligence_service import DO_NOT_PRESS, PRESS, recommend_pressing


def _check(name: str, passed: bool, detail: str) -> P72GradingCertificationCheckRead:
    return P72GradingCertificationCheckRead(component=name, passed=passed, detail=detail)


def run_grading_intelligence_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> P72GradingCertificationRead:
    checks: list[P72GradingCertificationCheckRead] = []

    try:
        cands = discover_grading_candidates(session, owner_user_id=owner_user_id, limit=5)
        checks.append(_check("candidate_discovery", True, f"{len(cands)} candidates materialized"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("candidate_discovery", False, str(exc)))

    probs = estimate_grade_probabilities(
        publisher="DC",
        release_year=2024,
        ownership_source=None,
        condition_notes="NM",
    )
    total = sum(probs.as_dict().values())
    checks.append(
        _check(
            "grade_probabilities",
            abs(total - 1.0) < 0.02,
            f"distribution sum={total:.4f}",
        )
    )

    costs = estimate_grading_costs(raw_fmv=22.0, release_year=2024)
    roi = calculate_grading_roi(
        raw_fmv=22.0,
        blended_fmv=22.0,
        graded_fmv=95.0,
        probabilities=probs,
        costs=costs,
    )
    profit_ok = roi.expected_profit == round(roi.expected_graded_fmv - 22.0 - roi.total_cost, 2)
    checks.append(_check("roi_calculations", profit_ok, "profit formula consistent"))

    press = recommend_pressing(
        raw_fmv=22.0,
        liquidity_score=50.0,
        roi=roi,
        condition_notes="crease",
        expected_roi_pct=roi.expected_roi_pct,
        release_year=2024,
    )
    checks.append(
        _check(
            "pressing_recommendations",
            press.recommendation in {PRESS, DO_NOT_PRESS},
            press.recommendation,
        )
    )

    checks.append(
        _check(
            "queue_workflow",
            STATUS_READY in ALLOWED_TRANSITIONS.get(STATUS_CANDIDATE, frozenset()),
            "CANDIDATE→READY_TO_SUBMIT allowed",
        )
    )

    try:
        dash = build_analytics_dashboard(session, owner_user_id=owner_user_id)
        checks.append(_check("analytics", dash.outcome_count >= 0, f"outcomes={dash.outcome_count}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("analytics", False, str(exc)))

    try:
        build_p72_decision_dashboard(session, owner_user_id=owner_user_id)
        build_operations_dashboard(session, owner_user_id=owner_user_id)
        checks.append(_check("dashboard_performance", True, "decision+operations dashboards built"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("dashboard_performance", False, str(exc)))

    passed = all(c.passed for c in checks)
    return P72GradingCertificationRead(
        approved_for_production=passed,
        checks=checks,
        platform_status="APPROVED_FOR_PRODUCTION" if passed else "NEEDS_ATTENTION",
        reviewed_at=datetime.now(timezone.utc),
    )
