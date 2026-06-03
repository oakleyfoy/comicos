"""Ranking path: collector significance must affect order (synthetic only)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.services.cross_system_recommendation_engine import _Candidate
from app.services.recommendation_intelligence_enrichment import (
    CollectorSignificanceScoreBreakdown,
    collector_ranking_boost,
    replace,
)
from app.services.recommendation_intelligence_ranking import (
    rank_order_changed_by_collector_boost,
    raw_priority_without_collector_boost,
)


def _breakdown(**kwargs) -> CollectorSignificanceScoreBreakdown:
    defaults = dict(
        base_score=70.0,
        franchise_score=0.0,
        publisher_score=0.0,
        historical_demand_score=0.0,
        continuity_score=0.0,
        creator_score=0.0,
        milestone_score=0.0,
        homage_score=0.0,
        audience_score=0.0,
        combo_bonus=0.0,
        ranking_boost=0.0,
        final_score=70.0,
    )
    defaults.update(kwargs)
    bd = CollectorSignificanceScoreBreakdown(**defaults)
    boost = collector_ranking_boost(bd)
    return replace(bd, ranking_boost=boost, final_score=round(bd.base_score + boost, 2))


def test_milestone_creator_homage_combo_beats_franchise_continuation() -> None:
    """PASS: high collector significance outranks generic continuation via ranking boost."""
    franchise_continuation = _breakdown(
        base_score=72.0,
        franchise_score=14.0,
        publisher_score=8.5,
        historical_demand_score=3.0,
        continuity_score=4.0,
    )
    significance_combo = _breakdown(
        base_score=68.0,
        franchise_score=4.0,
        publisher_score=5.0,
        milestone_score=6.5,
        creator_score=7.0,
        homage_score=3.5,
        audience_score=2.5,
        combo_bonus=4.0,
    )
    assert significance_combo.ranking_boost > franchise_continuation.ranking_boost
    assert significance_combo.final_score > franchise_continuation.final_score


def test_rank_order_changes_with_collector_boost() -> None:
    low_base = _Candidate(
        recommendation_type="PREORDER",
        title="Archive Saga #100",
        priority_score=65.0,
        confidence_score=0.6,
        estimated_value=None,
        raw_priority_score=65.0,
    )
    low_base.collector_score_breakdown = _breakdown(
        base_score=65.0,
        milestone_score=6.0,
        creator_score=7.0,
        homage_score=3.5,
        combo_bonus=4.0,
    )
    low_base.raw_priority_score = low_base.collector_score_breakdown.final_score
    low_base.priority_score = low_base.raw_priority_score

    high_base = _Candidate(
        recommendation_type="PREORDER",
        title="Toy Line Monthly #12",
        priority_score=78.0,
        confidence_score=0.62,
        estimated_value=None,
        raw_priority_score=78.0,
    )
    high_base.collector_score_breakdown = _breakdown(
        base_score=78.0,
        franchise_score=12.0,
        publisher_score=7.0,
        continuity_score=3.0,
    )
    high_base.raw_priority_score = high_base.collector_score_breakdown.final_score
    high_base.priority_score = high_base.raw_priority_score

    assert raw_priority_without_collector_boost(high_base) > raw_priority_without_collector_boost(low_base)
    assert rank_order_changed_by_collector_boost([high_base, low_base])
