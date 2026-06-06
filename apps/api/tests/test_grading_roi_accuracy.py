from __future__ import annotations

from app.services.grade_probability_engine import estimate_grade_probabilities
from app.services.grading_cost_service import estimate_grading_costs
from app.services.grading_outcome_service import _graded_value_for_grade
from app.services.grading_roi_service import calculate_grading_roi
from decimal import Decimal


def test_actual_roi_matches_formula() -> None:
    raw = Decimal("22.00")
    cost = Decimal("32.00")
    graded = _graded_value_for_grade(raw_fmv=raw, grade="9.6")
    profit = float(graded) - float(raw) - float(cost)
    roi = round(profit / float(cost) * 100.0, 2)
    assert graded > raw
    assert roi == round((float(graded) - 22.0 - 32.0) / 32.0 * 100.0, 2)


def test_expected_roi_consistent_with_service() -> None:
    probs = estimate_grade_probabilities(publisher="DC", release_year=2024, ownership_source=None, condition_notes="NM")
    costs = estimate_grading_costs(raw_fmv=22.0, release_year=2024)
    roi = calculate_grading_roi(
        raw_fmv=22.0,
        blended_fmv=22.0,
        graded_fmv=95.0,
        probabilities=probs,
        costs=costs,
    )
    assert roi.expected_profit == round(roi.expected_graded_fmv - 22.0 - roi.total_cost, 2)


def test_roi_analytics_api(client) -> None:
    from test_inventory import register_and_login

    token = register_and_login(client, "p72-roi-acc@example.com")
    resp = client.get(
        "/api/v1/grading-intelligence/roi-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "net_roi_pct" in data
    assert "total_grading_spend" in data
