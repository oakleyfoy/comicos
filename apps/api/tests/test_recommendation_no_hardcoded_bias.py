"""No hardcoded franchise/publisher names required for recommendation strength."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.recommendation_data_driven_signals import franchise_demand_bonus
from app.services.recommendation_intelligence_enrichment import (
    CollectorSignificanceScoreBreakdown,
    build_collector_significance_with_breakdown,
    collector_ranking_boost,
)
from app.services.recommendation_priority_enrichment import (
    OwnedSeriesInventoryStats,
    RecommendationPriorityEnrichment,
    publisher_strength_bonus,
)


def _series(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id=10,
        publisher="Independent Press",
        series_name="Zephyr Chronicles",
        series_type="ongoing",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _issue(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id=100,
        issue_number="50",
        title="Zephyr Chronicles #50",
        foc_date=None,
        release_date=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_franchise_bonus_without_named_franchise_uses_key_signals() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    bonus, hits = franchise_demand_bonus(
        session,
        series_name="Zephyr Chronicles",
        issue_title="First appearance arc",
        key_signals=["FIRST_APPEARANCE", "MILESTONE_NUMBERING"],
    )
    assert bonus >= 4.0
    assert "Batman" not in hits
    assert "Marvel" not in hits


def test_publisher_strength_without_owner_inventory_is_zero() -> None:
    assert publisher_strength_bonus("Marvel Comics", owned_stats=None) == 0.0
    assert publisher_strength_bonus("Boom Studios", owned_stats=None) == 0.0


def test_publisher_strength_from_owner_engagement_only() -> None:
    stats = OwnedSeriesInventoryStats(
        copies_by_series={("boom studios", "unknown series"): 4},
        avg_fmv_by_series={},
    )
    assert publisher_strength_bonus("Boom Studios", owned_stats=stats) > 0.0
    assert publisher_strength_bonus("Marvel", owned_stats=stats) == 0.0


def test_generic_series_high_collector_boost_without_batman() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    priority = RecommendationPriorityEnrichment(
        franchise_bonus=0.0,
        publisher_bonus=0.0,
        historical_demand_bonus=5.0,
        continuity_bonus=3.0,
        confidence_score=0.8,
    )
    intel, breakdown = build_collector_significance_with_breakdown(
        session,
        series=_series(),
        issue=_issue(issue_number="50"),
        variants=[],
        rationale="Milestone issue with market demand.",
        key_signals=["MILESTONE_NUMBERING", "FIRST_APPEARANCE"],
        priority_enrichment=priority,
        owned_stats=None,
        base_score=60.0,
    )
    assert breakdown.milestone_score > 0
    assert collector_ranking_boost(breakdown) >= 7.0
    assert "Batman" not in " ".join(intel.investment_thesis).lower()


def test_major_franchise_name_alone_does_not_beat_strong_collector_opportunity() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    name_only, _ = franchise_demand_bonus(
        session,
        series_name="Legacy Hero",
        issue_title="Legacy Hero #7",
        key_signals=[],
    )
    strong, _ = franchise_demand_bonus(
        session,
        series_name="Zephyr Chronicles",
        issue_title="Zephyr Chronicles #50",
        key_signals=["FIRST_APPEARANCE", "MILESTONE_NUMBERING", "ORIGIN"],
    )
    assert strong > name_only

    bat_breakdown = CollectorSignificanceScoreBreakdown(
        franchise_score=name_only,
        milestone_score=0.0,
        creator_score=0.0,
        homage_score=0.0,
        audience_score=0.0,
        publisher_score=0.0,
        historical_demand_score=0.0,
        continuity_score=0.0,
    )
    opp_breakdown = CollectorSignificanceScoreBreakdown(
        franchise_score=0.0,
        milestone_score=3.5,
        creator_score=0.0,
        homage_score=0.0,
        audience_score=2.0,
        publisher_score=0.0,
        historical_demand_score=5.0,
        continuity_score=3.0,
    )
    assert collector_ranking_boost(opp_breakdown) > collector_ranking_boost(bat_breakdown)
