from __future__ import annotations

from datetime import date, timedelta

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_forward_window import compute_forward_catalog_priority
from app.services.recommendation_priority_enrichment import (
    RecommendationPriorityEnrichment,
    franchise_strength_bonus,
    generic_number_one_bonus,
    publisher_strength_bonus,
)


def _issue_series(
    *,
    series_name: str,
    publisher: str = "Marvel",
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


def test_franchise_strength_batman_beats_generic_indie() -> None:
    batman_bonus, batman_hits = franchise_strength_bonus(series_name="Batman", issue_title="")
    indie_bonus, _ = franchise_strength_bonus(series_name="Random Indie Launch", issue_title="")
    assert batman_bonus > indie_bonus
    assert "Batman" in batman_hits

    bat_issue, bat_series = _issue_series(series_name="Batman", publisher="DC", issue_number="1", foc_days=75)
    indie_issue, indie_series = _issue_series(
        series_name="Obscure Indie", publisher="Small Press", issue_number="1", foc_days=75
    )

    bat_enrichment = RecommendationPriorityEnrichment(
        franchise_bonus=batman_bonus,
        publisher_bonus=publisher_strength_bonus("DC"),
        historical_demand_bonus=2.0,
        continuity_bonus=0.0,
        confidence_score=0.72,
    )
    indie_enrichment = RecommendationPriorityEnrichment(
        franchise_bonus=indie_bonus,
        publisher_bonus=publisher_strength_bonus("Small Press"),
        historical_demand_bonus=0.0,
        continuity_bonus=0.0,
        confidence_score=0.55,
    )

    bat_score, _, _ = compute_forward_catalog_priority(
        issue=bat_issue,
        series=bat_series,
        owned=False,
        key_signals=[],
        v2_total_score=None,
        spec_type=None,
        has_ratio_variant=False,
        enrichment=bat_enrichment,
    )
    indie_score, _, _ = compute_forward_catalog_priority(
        issue=indie_issue,
        series=indie_series,
        owned=False,
        key_signals=[],
        v2_total_score=None,
        spec_type=None,
        has_ratio_variant=False,
        enrichment=indie_enrichment,
    )
    assert bat_score - indie_score >= 12.0


def test_battle_beast_and_transformers_tier_high() -> None:
    bb, hits = franchise_strength_bonus(series_name="Battle Beast", issue_title="")
    tf, _ = franchise_strength_bonus(series_name="Transformers", issue_title="")
    assert bb >= 10.0
    assert tf >= 11.0
    assert "Battle Beast" in hits


def test_generic_number_one_bonus_reduced_without_franchise() -> None:
    assert generic_number_one_bonus(issue_number="1", key_signals=[], franchise_bonus=0.0) == 1.0
    assert generic_number_one_bonus(issue_number="1", key_signals=["NEW_NUMBER_ONE"], franchise_bonus=0.0) == 3.25
    assert generic_number_one_bonus(issue_number="1", key_signals=[], franchise_bonus=12.0) == 2.5


def test_publisher_strength_marvel_dc_image() -> None:
    assert publisher_strength_bonus("Marvel") >= publisher_strength_bonus("Boom Studios")
    assert publisher_strength_bonus("DC Comics") >= publisher_strength_bonus("Image Comics") - 1.0
