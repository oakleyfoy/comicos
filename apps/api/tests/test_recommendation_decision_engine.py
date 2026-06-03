from __future__ import annotations

from app.services.recommendation_decision_engine import (
    RecommendationDecisionContext,
    _RecommendationInput,
    _action_for,
    _headline,
    _pick_quantity,
    compute_recommendation_decision,
)


def test_action_for_aggressive_buy_on_strong_preorder() -> None:
    assert _action_for(kind="PREORDER", priority=90.0, confidence=0.85) == "BUY_AGGRESSIVE"
    assert _action_for(kind="ACQUIRE", priority=70.0, confidence=0.6) == "BUY"
    assert _action_for(kind="SELL", priority=95.0, confidence=0.9) == "PASS"
    assert _action_for(kind="GRADE", priority=80.0, confidence=0.7) == "WATCH"


def test_headline_formats_quantity() -> None:
    assert _headline("BUY", 2) == "BUY 2 COPIES"
    assert _headline("BUY", 1) == "BUY 1 COPY"
    assert _headline("WATCH", 0) == "WATCH"


def test_pick_quantity_uses_priority_bands() -> None:
    ctx = RecommendationDecisionContext(
        release_index={},
        key_signals_by_issue={},
        quantity_by_release={},
        variant_recs_by_release={},
        variants_by_issue={},
        spec_by_issue={},
    )
    q = _pick_quantity(
        priority=93.0,
        confidence=0.84,
        action="BUY",
        release_id=None,
        ctx=ctx,
    )
    assert q == 5


def test_compute_decision_includes_reason_codes_without_release() -> None:
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
            title="Batman #1",
            priority_score=88.0,
            confidence_score=0.81,
            rationale="Franchise strength. FOC window.",
            source_systems=["P57_UNIFIED", "P57_DAILY"],
        ),
        ctx=ctx,
        session=_Session(),  # type: ignore[arg-type]
        owner_user_id=1,
    )
    assert decision.action in {"BUY", "BUY_AGGRESSIVE"}
    assert decision.quantity >= 1
    assert "MULTI_SOURCE" in decision.reason_codes
    assert decision.decision_headline.startswith("BUY")
