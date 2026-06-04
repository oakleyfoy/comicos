from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_forward_window import compute_forward_catalog_priority
from app.services.recommendation_priority_enrichment import (
    OwnedSeriesInventoryStats,
    RecommendationPriorityEnrichment,
    generic_number_one_bonus,
    publisher_strength_bonus,
)


def _issue_series(
    *,
    series_name: str,
    publisher: str = "Independent Press",
    issue_number: str = "1",
    foc_days: int = 14,
) -> tuple[ReleaseIssue, ReleaseSeries]:
    today = date.today()
    foc = today + timedelta(days=foc_days)
    series = ReleaseSeries(
        owner_user_id=1,
        publisher=publisher,
        series_name=series_name,
        series_type="ONGOING",
        status="ACTIVE",
    )
    issue = ReleaseIssue(
        owner_user_id=1,
        release_uuid=f"prio-{series_name}-{issue_number}",
        series_id=1,
        issue_number=issue_number,
        title=f"{series_name} {issue_number}",
        release_status="SCHEDULED",
        foc_date=foc,
        release_date=foc + timedelta(days=21),
        cover_price=4.99,
    )
    return issue, series


def test_franchise_strength_without_registry_match_is_signal_driven() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    from app.services.recommendation_priority_enrichment import franchise_strength_bonus

    bonus, hits = franchise_strength_bonus(
        session,
        series_name="Obscure Indie",
        issue_title="Obscure Indie #1",
        key_signals=["FIRST_APPEARANCE"],
    )
    assert bonus >= 4.0
    assert "Batman" not in hits


def test_forward_priority_not_dominated_by_publisher_brand() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    indie_issue, indie_series = _issue_series(
        series_name="Obscure Indie",
        publisher="Small Press",
        issue_number="50",
        foc_days=75,
    )
    enrichment = RecommendationPriorityEnrichment(
        franchise_bonus=0.0,
        publisher_bonus=0.0,
        historical_demand_bonus=6.0,
        continuity_bonus=4.0,
        confidence_score=0.82,
        rationale_bits=("Historical series/market demand.", "Active run in your collection."),
    )
    score, _, _ = compute_forward_catalog_priority(
        issue=indie_issue,
        series=indie_series,
        owned=False,
        key_signals=["FIRST_APPEARANCE", "MILESTONE_NUMBERING"],
        v2_total_score=78.0,
        spec_type="BUY",
        has_ratio_variant=True,
        enrichment=enrichment,
    )
    assert score >= 70.0


def test_generic_number_one_bonus_reduced_without_franchise() -> None:
    assert generic_number_one_bonus(issue_number="1", key_signals=[], franchise_bonus=0.0) == 1.0
    assert generic_number_one_bonus(issue_number="1", key_signals=["NEW_NUMBER_ONE"], franchise_bonus=0.0) == 3.25
    assert generic_number_one_bonus(issue_number="1", key_signals=["KEY_ISSUE"], franchise_bonus=0.0) == 2.0


def test_publisher_strength_requires_owner_engagement() -> None:
    assert publisher_strength_bonus("Marvel") == 0.0
    stats = OwnedSeriesInventoryStats(
        copies_by_series={("marvel", "x series"): 5},
        avg_fmv_by_series={},
    )
    assert publisher_strength_bonus("Marvel", owned_stats=stats) > 0.0
