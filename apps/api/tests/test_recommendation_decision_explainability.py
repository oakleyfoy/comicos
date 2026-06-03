"""Decision explainability: cover plan, quantity reasoning, signals, deduped reasons."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.recommendation_decision_explainability import (
    _build_cover_candidates,
    build_cover_purchase_plan,
    build_quantity_reasoning,
    build_signal_matrix,
    normalize_top_reasons,
)
from app.services.recommendation_decision_engine import (
    RecommendationDecisionContext,
    _RecommendationInput,
    compute_recommendation_decision,
)


def test_buy_five_cover_plan_sums_to_five() -> None:
    candidates = _build_cover_candidates(
        variant_recs=[],
        release_variants=[
            SimpleNamespace(
                variant_name="Cover A",
                variant_type="COVER_A",
                ratio_value=None,
                is_incentive_variant=False,
            ),
            SimpleNamespace(
                variant_name="Cover B Card Stock Variant",
                variant_type="OPEN_ORDER",
                ratio_value=None,
                is_incentive_variant=False,
            ),
            SimpleNamespace(
                variant_name="Ratio",
                variant_type="RATIO",
                ratio_value=25,
                is_incentive_variant=False,
            ),
        ],
    )
    plan = build_cover_purchase_plan(
        total_quantity=5,
        action="BUY",
        candidates=candidates,
        signal_set={"RATIO_VARIANT"},
        reason_codes=["RATIO_OPPORTUNITY", "SPEC_HEAT"],
    )
    assert sum(row.recommended_quantity for row in plan) == 5
    assert any(row.recommended_quantity > 0 for row in plan)
    assert not any(row.recommended_quantity > 1 and "incentive" in row.cover_label.lower() for row in plan)


def test_watch_zero_quantities() -> None:
    candidates = _build_cover_candidates(variant_recs=[], release_variants=[])
    plan = build_cover_purchase_plan(
        total_quantity=0,
        action="WATCH",
        candidates=candidates,
        signal_set=set(),
        reason_codes=[],
    )
    assert all(row.recommended_quantity == 0 for row in plan)


def test_ratio_not_allocated_without_signal() -> None:
    candidates = _build_cover_candidates(
        variant_recs=[],
        release_variants=[
            SimpleNamespace(
                variant_name="Cover A",
                variant_type="COVER_A",
                ratio_value=None,
                is_incentive_variant=False,
            ),
            SimpleNamespace(
                variant_name="1:25",
                variant_type="RATIO",
                ratio_value=25,
                is_incentive_variant=False,
            ),
        ],
    )
    plan = build_cover_purchase_plan(
        total_quantity=2,
        action="BUY",
        candidates=candidates,
        signal_set=set(),
        reason_codes=["FRANCHISE_STRENGTH"],
    )
    labels = {row.cover_label: row.recommended_quantity for row in plan}
    assert labels.get("1:25", 0) == 0
    assert sum(labels.values()) == 2


def test_duplicate_reasons_removed() -> None:
    reasons = normalize_top_reasons(
        reason_codes=["FRANCHISE_STRENGTH", "FOC_URGENCY", "FRANCHISE_STRENGTH"],
        reason_summary=[
            "Franchise strength (Batman).",
            "Franchise strength (Batman).",
            "FOC window (47 days).",
            "FOC window active.",
        ],
        collector_intel=None,
        rationale="Franchise strength. FOC window. Not in inventory.",
    )
    assert len(reasons) <= 5
    lowered = [r.lower() for r in reasons]
    assert sum(1 for r in lowered if "franchise" in r) <= 1
    assert sum(1 for r in lowered if "foc" in r) <= 1


def test_signal_matrix_keys() -> None:
    matrix = build_signal_matrix(
        signal_set={"RATIO_VARIANT", "NEW_NUMBER_ONE"},
        reason_codes=["MILESTONE_ISSUE", "SPEC_HEAT"],
        collector_intel=None,
        rationale="Forward acquisition. FOC window.",
        source_systems=["P52_PULL_LIST"],
        owns_run=False,
        foc_active=True,
    )
    assert matrix.milestone_issue is True
    assert matrix.ratio_variant_opportunity is True
    assert matrix.issue_launch is True
    assert matrix.pull_list_relevance is True
    assert matrix.foc_window is True


def test_quantity_reasoning_above_two() -> None:
    qr = build_quantity_reasoning(
        final_quantity=5,
        action="BUY",
        priority=93.0,
        confidence=0.85,
        reason_codes=["SPEC_HEAT", "RATIO_OPPORTUNITY"],
        signal_set={"RATIO_VARIANT"},
    )
    assert qr is not None
    assert qr.final_quantity == 5
    assert qr.base_quantity >= 1
    if qr.final_quantity > 2:
        assert len(qr.adjustments) >= 1 or qr.base_quantity >= 2


def test_compute_decision_has_cover_plan_and_breakdown() -> None:
    ctx = RecommendationDecisionContext(
        release_index={},
        key_signals_by_issue={},
        quantity_by_release={},
        variant_recs_by_release={},
        variants_by_issue={},
        spec_by_issue={},
    )

    class _Session:
        pass

    decision = compute_recommendation_decision(
        _RecommendationInput(
            kind="PREORDER",
            title="Chronicle Prime #100",
            priority_score=91.0,
            confidence_score=0.86,
            rationale="Franchise strength. FOC window. Spec heat.",
            source_systems=["P57_UNIFIED", "P52_PULL_LIST"],
        ),
        ctx=ctx,
        session=_Session(),  # type: ignore[arg-type]
        owner_user_id=1,
    )
    if decision.action in {"BUY", "BUY_AGGRESSIVE"} and decision.quantity > 0:
        assert decision.cover_purchase_plan
        assert sum(r.recommended_quantity for r in decision.cover_purchase_plan) == decision.quantity
        assert "TOTAL" in decision.decision_headline
    assert decision.signal_matrix is not None
    assert decision.signal_abbreviations
    assert decision.top_reasons
    assert decision.score_breakdown
