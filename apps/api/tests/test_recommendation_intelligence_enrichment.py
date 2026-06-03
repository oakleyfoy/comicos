"""Collector-significance enrichment (synthetic fixtures only)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.recommendation_decision_engine import (
    RecommendationDecisionContext,
    _RecommendationInput,
    compute_recommendation_decision,
)
from app.services.recommendation_intelligence_enrichment import (
    CollectorSignificanceEnrichment,
    build_collector_significance_enrichment,
    parse_issue_number_milestone,
)
from app.services.recommendation_priority_enrichment import RecommendationPriorityEnrichment


def _series(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id=10,
        publisher="Generic Comics",
        series_name="Chronicle Prime",
        series_type="ongoing",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _issue(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id=100,
        issue_number="100",
        title="Century Mark",
        foc_date=None,
        release_date=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_parse_milestone_numbers() -> None:
    assert parse_issue_number_milestone("100") == 100
    assert parse_issue_number_milestone("#25") == 25
    assert parse_issue_number_milestone("7") is None


def test_generic_milestone_alone_is_modest_boost() -> None:
    intel = build_collector_significance_enrichment(
        MagicMock(),
        series=_series(),
        issue=_issue(issue_number="100", title="Volume centennial"),
        variants=[],
        rationale="Standard preorder window.",
        key_signals=[],
        priority_enrichment=None,
        owned_stats=None,
    )
    assert intel.milestone_issue_number == 100
    assert intel.decision_boost <= 6.0
    assert "MILESTONE_ISSUE" in intel.reason_codes


def test_milestone_creator_homage_combo_stronger() -> None:
    session = MagicMock()
    profile = SimpleNamespace(id=5, creator_name="Alex Rivera", creator_role="writer", status="ACTIVE")
    session.exec.return_value.all.return_value = [profile]

    with patch(
        "app.services.recommendation_intelligence_enrichment.creator_score",
        return_value=82.0,
    ):
        intel = build_collector_significance_enrichment(
            session,
            series=_series(series_name="Saga Archive"),
            issue=_issue(
                issue_number="100",
                title="100th anniversary homage to classic era",
            ),
            variants=[
                SimpleNamespace(
                    variant_name="Retro homage variant",
                    variant_type="variant",
                    cover_artist="Alex Rivera",
                    ratio_value=None,
                )
            ],
            rationale="Anniversary tribute variant.",
            key_signals=["MILESTONE_NUMBERING"],
            priority_enrichment=RecommendationPriorityEnrichment(
                franchise_bonus=8.0,
                historical_demand_bonus=4.0,
                continuity_bonus=2.0,
                rationale_bits=("Historical series/market demand.",),
            ),
            owned_stats=None,
        )

    assert intel.decision_boost >= 8.0
    assert "CREATOR_SIGNIFICANCE" in intel.reason_codes
    assert "HOMAGE_TRIBUTE" in intel.reason_codes
    assert any("Why this matters" in t for t in intel.investment_thesis)


def test_weak_indie_number_one_low_boost() -> None:
    intel = build_collector_significance_enrichment(
        MagicMock(),
        series=_series(publisher="Vault Press", series_name="Obscure Tales"),
        issue=_issue(issue_number="1", title="First issue"),
        variants=[],
        rationale="New indie launch.",
        key_signals=[],
        priority_enrichment=None,
        owned_stats=None,
    )
    assert intel.milestone_issue_number is None
    assert intel.decision_boost < 4.0


def test_decision_engine_applies_enrichment_boost() -> None:
    issue = _issue()
    series = _series()
    ctx = RecommendationDecisionContext(
        release_index={"chronicle prime #100": (issue, series)},
        key_signals_by_issue={100: ["MILESTONE_NUMBERING"]},
        quantity_by_release={},
        variant_recs_by_release={},
        variants_by_issue={100: []},
        spec_by_issue={},
    )
    session = MagicMock()
    stub_intel = CollectorSignificanceEnrichment(
        milestone_issue_number=100,
        milestone_bonus=3.5,
        creator_bonus=4.0,
        homage_bonus=3.5,
        decision_boost=9.0,
        confidence_boost=0.05,
        reason_codes=("MILESTONE_ISSUE", "HOMAGE_TRIBUTE"),
        investment_thesis=("Why this matters:", "Milestone issue #100.", "Homage/tribute signal (homage cover)."),
    )

    with (
        patch(
            "app.services.recommendation_decision_engine.build_recommendation_priority_enrichment",
            return_value=RecommendationPriorityEnrichment(),
        ),
        patch(
            "app.services.recommendation_decision_engine.build_collector_significance_enrichment",
            return_value=stub_intel,
        ),
    ):
        decision = compute_recommendation_decision(
            _RecommendationInput(
                kind="PREORDER",
                title="Chronicle Prime #100",
                priority_score=72.0,
                confidence_score=0.62,
                rationale="Forward window.",
                source_systems=["P57_UNIFIED"],
            ),
            ctx=ctx,
            session=session,
            owner_user_id=1,
        )

    assert decision.action in {"BUY", "BUY_AGGRESSIVE"}
    assert "MILESTONE_ISSUE" in decision.reason_codes
    assert any("Why this matters" in line for line in decision.reason_summary)
