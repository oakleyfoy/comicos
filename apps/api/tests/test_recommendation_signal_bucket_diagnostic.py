"""Signal bucket classification (A/B/C) unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.recommendation_signal_bucket_diagnostic import (
    BUCKET_A,
    BUCKET_B,
    BUCKET_C,
    _classify_creator_bucket,
    _classify_homage_bucket,
    _classify_market_bucket,
    _classify_milestone_bucket,
    diagnose_title_signal_buckets,
)


def test_creator_bucket_source_missing() -> None:
    assert (
        _classify_creator_bucket(
            release_matched=True,
            enrichment_attempted=True,
            creator_score_value=0.0,
            names_in_catalog=False,
            names_in_variants=False,
            matched_profiles=[],
        )
        == BUCKET_A
    )


def test_creator_bucket_match_failed() -> None:
    assert (
        _classify_creator_bucket(
            release_matched=False,
            enrichment_attempted=False,
            creator_score_value=0.0,
            names_in_catalog=True,
            names_in_variants=True,
            matched_profiles=[{"meets_threshold": True}],
        )
        == BUCKET_B
    )


def test_creator_bucket_scoring_strict() -> None:
    assert (
        _classify_creator_bucket(
            release_matched=True,
            enrichment_attempted=True,
            creator_score_value=0.0,
            names_in_catalog=True,
            names_in_variants=False,
            matched_profiles=[{"creator_name": "Alex", "meets_threshold": False}],
        )
        == BUCKET_C
    )


def test_milestone_bucket_match_failed() -> None:
    assert (
        _classify_milestone_bucket(
            release_matched=False,
            enrichment_attempted=False,
            milestone_score=0.0,
            parsed_milestone_num=None,
            anniversary_wording=False,
            legacy_wording=False,
            key_signal_milestone=False,
        )
        == BUCKET_B
    )


def test_milestone_bucket_strict_key_signal_without_numeric() -> None:
    assert (
        _classify_milestone_bucket(
            release_matched=True,
            enrichment_attempted=True,
            milestone_score=0.0,
            parsed_milestone_num=None,
            anniversary_wording=False,
            legacy_wording=False,
            key_signal_milestone=True,
        )
        == BUCKET_C
    )


def test_homage_bucket_source_missing() -> None:
    assert (
        _classify_homage_bucket(
            release_matched=True,
            enrichment_attempted=True,
            homage_score=0.0,
            homage_in_catalog=False,
            homage_in_variants=False,
        )
        == BUCKET_A
    )


def test_market_bucket_source_missing() -> None:
    assert (
        _classify_market_bucket(
            release_matched=True,
            enrichment_attempted=True,
            market_demand_score=0.0,
            market_profiles_matched=False,
            owner_continuity=False,
            pull_list_match=False,
            fmv_present=False,
            market_user_available=False,
        )
        == BUCKET_A
    )


def test_diagnose_title_index_miss_is_bucket_b() -> None:
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    session.exec.return_value.first.return_value = None

    issue = SimpleNamespace(
        id=1,
        issue_number="7",
        title="Zephyr Chronicles #7",
        foc_date=None,
        release_date=None,
    )
    series = SimpleNamespace(
        publisher="Indie",
        series_name="Zephyr Chronicles",
        series_type="ongoing",
    )
    index: dict = {}

    with patch(
        "app.services.recommendation_signal_bucket_diagnostic._search_release_catalog",
        return_value=[],
    ):
        with patch(
            "app.services.recommendation_signal_bucket_diagnostic.resolve_release_pair",
            return_value=None,
        ):
            with patch(
                "app.services.recommendation_signal_bucket_diagnostic._select_catalog_pair",
                return_value=(None, [], "no_usable_single_issue_in_catalog", None, True),
            ):
                with patch(
                    "app.services.recommendation_signal_bucket_diagnostic.build_owned_series_inventory_stats",
                    return_value=SimpleNamespace(copies_by_series={}, avg_fmv_by_series={}),
                ):
                    report = diagnose_title_signal_buckets(
                        session,
                        owner_user_id=1,
                        title_query="Zephyr Chronicles #7",
                        release_index=index,
                    )

    assert report["bucket_summary"]["creator"] == BUCKET_B
    assert report["bucket_summary"]["milestone"] == BUCKET_B
