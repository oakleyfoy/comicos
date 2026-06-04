"""Conservative ratio discipline and exceptional variant gating."""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.recommendation_decision import SignalMatrixRead
from app.services.collector_ratio_strategy import (
    CollectorRatioStrategySettings,
    has_exceptional_variant_signal,
)
from app.services.recommendation_decision_explainability import (
    _build_cover_candidates,
    build_cover_purchase_plan,
    build_quantity_reasoning,
)


def _variants() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            variant_name="Cover A",
            variant_type="COVER_A",
            ratio_value=None,
            is_incentive_variant=False,
        ),
        SimpleNamespace(
            variant_name="Cover B",
            variant_type="OPEN_ORDER",
            ratio_value=None,
            is_incentive_variant=False,
        ),
        SimpleNamespace(variant_name="1:25", variant_type="RATIO", ratio_value=25, is_incentive_variant=False),
        SimpleNamespace(variant_name="1:50", variant_type="RATIO", ratio_value=50, is_incentive_variant=False),
        SimpleNamespace(variant_name="1:100", variant_type="RATIO", ratio_value=100, is_incentive_variant=False),
    ]


def test_conservative_never_recommends_100_x3() -> None:
    candidates = _build_cover_candidates(variant_recs=[], release_variants=_variants())
    plan, _ = build_cover_purchase_plan(
        total_quantity=5,
        action="BUY",
        candidates=candidates,
        signal_set={"RATIO_VARIANT", "VARIANT_HOT"},
        reason_codes=["RATIO_OPPORTUNITY", "SPEC_HEAT"],
        exceptional_variant_signal=True,
    )
    for row in plan:
        if "1:100" in row.cover_label:
            assert row.recommended_quantity <= 1
    assert not any(r.cover_label == "1:100" and r.recommended_quantity >= 3 for r in plan)


def test_high_ratio_suppressed_without_exceptional() -> None:
    candidates = _build_cover_candidates(variant_recs=[], release_variants=_variants())
    plan, suppressed = build_cover_purchase_plan(
        total_quantity=5,
        action="BUY",
        candidates=candidates,
        signal_set={"RATIO_VARIANT"},
        reason_codes=["RATIO_OPPORTUNITY"],
        exceptional_variant_signal=False,
    )
    assert not any("1:50" in row.cover_label and row.recommended_quantity > 0 for row in plan)
    assert not any("1:100" in row.cover_label and row.recommended_quantity > 0 for row in plan)
    assert any(s.cover_label == "1:100" for s in suppressed)


def test_generic_variant_opportunity_not_exceptional() -> None:
    matrix = SignalMatrixRead(ratio_variant_opportunity=True, market_heat=False)
    assert (
        has_exceptional_variant_signal(
            signal_matrix=matrix,
            score_breakdown=None,
            collector_intel=None,
            confidence=0.85,
            rationale="Variant opportunity in forward window.",
            owns_run=False,
            pull_list_relevance=False,
        )
        is False
    )


def test_buy_five_mostly_cover_a() -> None:
    candidates = _build_cover_candidates(variant_recs=[], release_variants=_variants())
    plan, _ = build_cover_purchase_plan(
        total_quantity=5,
        action="BUY",
        candidates=candidates,
        signal_set={"RATIO_VARIANT"},
        reason_codes=["RATIO_OPPORTUNITY"],
        exceptional_variant_signal=False,
    )
    cover_a = next((r for r in plan if r.cover_label.lower().startswith("cover a")), None)
    assert cover_a is not None
    assert cover_a.recommended_quantity >= 3


def test_ratio_qty_never_exceeds_cover_a_conservative() -> None:
    candidates = _build_cover_candidates(variant_recs=[], release_variants=_variants())
    plan, _ = build_cover_purchase_plan(
        total_quantity=5,
        action="BUY",
        candidates=candidates,
        signal_set={"RATIO_VARIANT"},
        reason_codes=["RATIO_OPPORTUNITY", "KEY_ISSUE", "FIRST_APPEARANCE"],
        exceptional_variant_signal=True,
    )
    cover_a_qty = max(
        (r.recommended_quantity for r in plan if r.cover_label.lower().startswith("cover a")),
        default=0,
    )
    for row in plan:
        if row.cover_label.lower().startswith("cover a"):
            continue
        if "1:" in row.cover_label:
            assert row.recommended_quantity <= cover_a_qty


def test_quantity_reasoning_no_variant_without_allocation() -> None:
    from app.schemas.recommendation_decision import CoverPurchasePlanRow

    plan = [
        CoverPurchasePlanRow(
            cover_label="Cover A",
            recommended_quantity=5,
            reason_codes=["PRIMARY_COVER_LIQUIDITY"],
            reason_summary="",
        )
    ]
    qr = build_quantity_reasoning(
        final_quantity=5,
        action="BUY",
        priority=90.0,
        confidence=0.85,
        reason_codes=["RATIO_OPPORTUNITY"],
        signal_set={"RATIO_VARIANT"},
        cover_plan=plan,
    )
    assert qr is not None
    assert not any(adj.reason_code == "RATIO_OPPORTUNITY" for adj in qr.adjustments)


def test_quantity_reasoning_variant_when_plan_includes_ratio() -> None:
    from app.schemas.recommendation_decision import CoverPurchasePlanRow

    plan = [
        CoverPurchasePlanRow(
            cover_label="Cover A",
            recommended_quantity=4,
            reason_codes=["PRIMARY_COVER_LIQUIDITY"],
            reason_summary="",
        ),
        CoverPurchasePlanRow(
            cover_label="1:25",
            recommended_quantity=1,
            reason_codes=["RATIO_OPPORTUNITY"],
            reason_summary="",
        ),
    ]
    qr = build_quantity_reasoning(
        final_quantity=5,
        action="BUY",
        priority=92.0,
        confidence=0.88,
        reason_codes=["RATIO_OPPORTUNITY", "SPEC_HEAT"],
        signal_set={"RATIO_VARIANT"},
        cover_plan=plan,
    )
    assert qr is not None
    assert any(adj.reason_code == "RATIO_OPPORTUNITY" for adj in qr.adjustments)
