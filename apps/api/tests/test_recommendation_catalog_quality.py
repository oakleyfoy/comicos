from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_catalog_quality import (
    RECOMMENDATION_PRICE_CAP,
    apply_price_discipline,
    classify_catalog_text,
    classify_forward_release,
    should_include_in_top_recommendations,
)


def test_dead_head_tp_excluded() -> None:
    quality = classify_catalog_text(
        series_name="Dead Head",
        issue_number="TP",
        title="Dead Head TP",
        publisher="Image",
    )
    assert quality.is_book_or_trade
    assert not quality.is_single_issue
    assert not quality.spec_eligible
    assert quality.recommendation_exclusion_reason in {"trade_paperback", "not_single_issue"}
    assert not should_include_in_top_recommendations(quality)


def test_pictorial_history_paperback_excluded() -> None:
    quality = classify_catalog_text(
        series_name="Pictorial History of Classic Nurse Paperback Covers",
        issue_number=None,
        title="Pictorial History of Classic Nurse Paperback Covers",
    )
    assert quality.is_book_or_trade
    assert not should_include_in_top_recommendations(quality)
    assert quality.recommendation_exclusion_reason in {"prose_or_art_book", "paperback_book", "trade_paperback"}


def test_marvel_single_issue_eligible() -> None:
    issue = ReleaseIssue(
        owner_user_id=1,
        release_uuid="q-marvel-1",
        series_id=1,
        issue_number="1",
        title="Amazing Spider-Man 1",
        release_status="SCHEDULED",
        foc_date=date.today() + timedelta(days=30),
    )
    series = ReleaseSeries(
        owner_user_id=1,
        publisher="Marvel",
        series_name="Amazing Spider-Man",
        series_type="ONGOING",
        status="ACTIVE",
    )
    quality = classify_forward_release(issue, series, key_signals=["FIRST_APPEARANCE"])
    assert quality.is_single_issue
    assert quality.spec_eligible
    assert quality.recommendation_exclusion_reason is None
    assert should_include_in_top_recommendations(quality)
    assert quality.publisher_boost >= 3.0


def test_omnibus_excluded_without_key_override() -> None:
    quality = classify_catalog_text(
        series_name="Batman",
        issue_number="1",
        title="Batman Omnibus Vol 1",
    )
    assert not should_include_in_top_recommendations(quality)
    assert quality.recommendation_exclusion_reason == "collected_edition"


def test_reprint_allowed_with_key_signal_override() -> None:
    quality = classify_forward_release(
        ReleaseIssue(
            owner_user_id=1,
            release_uuid="q-fac",
            series_id=1,
            issue_number="1",
            title="Facsimile Edition",
            release_status="SCHEDULED",
            cover_price=4.99,
        ),
        ReleaseSeries(
            owner_user_id=1,
            publisher="Marvel",
            series_name="X-Men",
            series_type="ONGOING",
            status="ACTIVE",
        ),
        key_signals=["FIRST_APPEARANCE"],
    )
    assert quality.spec_eligible
    assert should_include_in_top_recommendations(quality)


def test_expensive_paperback_excluded_by_price() -> None:
    quality = classify_catalog_text(
        series_name="Pictorial History of Classic Nurse Paperback Covers",
        issue_number=None,
        title="Pictorial History of Classic Nurse Paperback Covers",
    )
    quality = apply_price_discipline(
        quality,
        cover_price=29.99,
        title="Pictorial History of Classic Nurse Paperback Covers",
    )
    assert quality.is_over_price_cap
    assert not should_include_in_top_recommendations(quality)


def test_under_cap_single_issue_preferred() -> None:
    quality = classify_forward_release(
        ReleaseIssue(
            owner_user_id=1,
            release_uuid="cheap-1",
            series_id=1,
            issue_number="12",
            title="Street Fighters 12",
            release_status="SCHEDULED",
            cover_price=4.99,
        ),
        ReleaseSeries(
            owner_user_id=1,
            publisher="Image",
            series_name="Street Fighters",
            series_type="ONGOING",
            status="ACTIVE",
        ),
    )
    assert not quality.is_over_price_cap
    assert quality.price_discipline_score >= 0.98
    assert should_include_in_top_recommendations(quality)


def test_over_cap_single_excluded_without_signal() -> None:
    quality = classify_forward_release(
        ReleaseIssue(
            owner_user_id=1,
            release_uuid="expensive-1",
            series_id=1,
            issue_number="12",
            title="Street Fighters 12",
            release_status="SCHEDULED",
            cover_price=15.99,
        ),
        ReleaseSeries(
            owner_user_id=1,
            publisher="Small Press",
            series_name="Street Fighters",
            series_type="ONGOING",
            status="ACTIVE",
        ),
    )
    assert quality.is_over_price_cap
    assert quality.price_exception_reason is None
    assert not should_include_in_top_recommendations(quality)


def test_over_cap_number_one_with_key_allowed() -> None:
    quality = classify_forward_release(
        ReleaseIssue(
            owner_user_id=1,
            release_uuid="expensive-one",
            series_id=1,
            issue_number="1",
            title="Amazing Launch 1",
            release_status="SCHEDULED",
            cover_price=15.99,
        ),
        ReleaseSeries(
            owner_user_id=1,
            publisher="Marvel",
            series_name="Amazing Launch",
            series_type="ONGOING",
            status="ACTIVE",
        ),
        key_signals=["NEW_NUMBER_ONE", "FIRST_APPEARANCE"],
    )
    assert quality.is_over_price_cap
    assert quality.price_exception_reason in {"number_one_franchise", "major_key_issue", "ratio_incentive_variant"}
    assert should_include_in_top_recommendations(quality)


BAD_PRODUCTION_EXAMPLES = [
    ("Kick-Ass Compendium TP", "TP", "Kick-Ass Compendium TP"),
    ("A Pictorial History of Classic Nurse TP", "TP", "A Pictorial History of Classic Nurse TP"),
    ("All The Feels Emotional Sticker Book TP", "TP", "All The Feels Emotional Sticker Book TP"),
    ("Alphabet of Oddities HC", "HC", "Alphabet of Oddities HC"),
    ("Alter Bridge HC Tour of Horrors", "HC", "Alter Bridge HC Tour of Horrors"),
]


@pytest.mark.parametrize("series_name,issue_number,title", BAD_PRODUCTION_EXAMPLES)
def test_production_bad_examples_excluded_even_with_key_signal(
    series_name: str,
    issue_number: str,
    title: str,
) -> None:
    quality = classify_catalog_text(
        series_name=series_name,
        issue_number=issue_number,
        title=title,
        key_signals=["FIRST_APPEARANCE", "KEY_ISSUE"],
        spec_type="STRONG_BUY",
    )
    assert not should_include_in_top_recommendations(quality)


@pytest.mark.parametrize("series_name,issue_number,title", BAD_PRODUCTION_EXAMPLES)
def test_production_bad_display_titles_excluded(series_name: str, issue_number: str, title: str) -> None:
    display = f"{series_name} #{issue_number}" if issue_number else series_name
    quality = classify_catalog_text(
        series_name=series_name,
        issue_number=issue_number,
        title=display,
        key_signals=["NEW_NUMBER_ONE"],
    )
    assert not should_include_in_top_recommendations(quality)


def test_foc_single_issue_still_included() -> None:
    issue = ReleaseIssue(
        owner_user_id=1,
        release_uuid="foc-good",
        series_id=1,
        issue_number="1",
        title="New Hero 1",
        release_status="SCHEDULED",
        foc_date=date.today() + timedelta(days=5),
        cover_price=4.99,
    )
    series = ReleaseSeries(
        owner_user_id=1,
        publisher="Image",
        series_name="New Hero",
        series_type="ONGOING",
        status="ACTIVE",
    )
    quality = classify_forward_release(issue, series, key_signals=["NEW_NUMBER_ONE"])
    assert should_include_in_top_recommendations(quality)
