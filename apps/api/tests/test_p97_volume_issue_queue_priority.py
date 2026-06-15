from __future__ import annotations

import pytest

from app.services.p97_volume_issue_queue_priority import (
    TIER_1_CORE,
    TIER_2_LEGACY,
    TIER_3_OTHER_US,
    TIER_4_DEPRIORITIZED,
    classify_launch_priority_tier,
    compute_volume_import_priority,
    is_foreign_anthology_title,
)


@pytest.mark.parametrize(
    "title",
    [
        "Topolino",
        "Lanciostory",
        "Skorpio",
        "Fantomen",
        "91:an",
        "Serie-Magasinet",
        "Knasen",
        "Kalle Anka",
        "Diabolik",
        "Dylan Dog",
        "Bamse",
    ],
)
def test_foreign_anthology_titles_classify_tier_4(title: str) -> None:
    assert is_foreign_anthology_title(title)
    assert (
        classify_launch_priority_tier(publisher="Unknown Publisher", name=title)
        == TIER_4_DEPRIORITIZED
    )


def test_foreign_anthology_title_variants_with_suffixes() -> None:
    assert is_foreign_anthology_title("Topolino Almanacco")
    assert is_foreign_anthology_title("Il Dylan Dog")
    assert is_foreign_anthology_title("Kalle Anka & Co")
    assert not is_foreign_anthology_title("Detective Comics")


def test_core_us_publishers_tier_1() -> None:
    assert (
        classify_launch_priority_tier(publisher="DC Comics", name="Detective Comics")
        == TIER_1_CORE
    )
    assert (
        classify_launch_priority_tier(publisher="Marvel", name="The Amazing Spider-Man")
        == TIER_1_CORE
    )
    assert classify_launch_priority_tier(publisher="Archie Comics", name="Archie") == TIER_1_CORE


def test_rebellion_2000_ad_never_above_core_us() -> None:
    rebellion = compute_volume_import_priority(
        missing_issue_count=500,
        count_of_issues=500,
        coverage_percent=0.0,
        publisher="Rebellion",
        name="2000 AD",
    )
    core = compute_volume_import_priority(
        missing_issue_count=25,
        count_of_issues=900,
        coverage_percent=10.0,
        publisher="DC Comics",
        name="Detective Comics",
    )
    assert rebellion.launch_priority_tier in (TIER_3_OTHER_US, TIER_4_DEPRIORITIZED)
    assert core.launch_priority_tier == TIER_1_CORE
    assert core.priority_score > rebellion.priority_score


def test_2000_ad_non_rebellion_publisher_tier_3_or_4() -> None:
    tier = classify_launch_priority_tier(publisher="IPC Media", name="2000 AD")
    assert tier in (TIER_3_OTHER_US, TIER_4_DEPRIORITIZED)
    assert tier != TIER_1_CORE
    assert tier != TIER_2_LEGACY


def test_missing_issue_cap_limits_foreign_domination() -> None:
    low_missing_core = compute_volume_import_priority(
        missing_issue_count=25,
        count_of_issues=900,
        coverage_percent=10.0,
        publisher="DC Comics",
        name="Detective Comics",
    )
    high_missing_foreign = compute_volume_import_priority(
        missing_issue_count=5000,
        count_of_issues=5000,
        coverage_percent=0.0,
        publisher="Panini Comics",
        name="Topolino",
    )
    assert low_missing_core.launch_priority_tier == TIER_1_CORE
    assert high_missing_foreign.launch_priority_tier == TIER_4_DEPRIORITIZED
    assert low_missing_core.priority_score > high_missing_foreign.priority_score
