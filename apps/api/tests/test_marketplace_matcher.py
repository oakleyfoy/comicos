"""Tests for marketplace opportunity search matcher."""

from __future__ import annotations

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.services.marketplace.marketplace_opportunity_matcher import candidate_searches_for_opportunity


def _opp(**kwargs: object) -> MarketplaceAcquisitionOpportunity:
    base = dict(
        owner_user_id=1,
        marketplace="EBAY",
        external_listing_id="SIM-1",
        title="",
        publisher="DC",
        series="Absolute Batman",
        issue="20",
        variant="",
        asking_price=3.0,
        estimated_fmv=10.0,
    )
    base.update(kwargs)
    return MarketplaceAcquisitionOpportunity(**base)  # type: ignore[arg-type]


def test_matcher_includes_series_issue() -> None:
    queries = candidate_searches_for_opportunity(_opp())
    assert any("Absolute Batman" in q and "#20" in q for q in queries)


def test_matcher_deduplicates() -> None:
    queries = candidate_searches_for_opportunity(_opp(title="Absolute Batman #20"))
    lowered = [q.lower() for q in queries]
    assert len(lowered) == len(set(lowered))


def test_matcher_special_issue_notation() -> None:
    queries = candidate_searches_for_opportunity(
        _opp(series="Energon Universe", issue="2026SPECIAL1", title="Energon Universe 2026 Special")
    )
    assert len(queries) >= 1
