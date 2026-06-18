"""P98 collector value gap service tests."""

from __future__ import annotations

import sys
from pathlib import Path

from app.services.p98_collector_value_gap_service import (  # noqa: E402
    GROUP_A,
    TAG_KEY_ISSUE,
    TAG_NUMBER_ONE,
    classify_volume_tags,
    compute_collector_value_score,
    _execution_group,
)

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def test_ec_tales_from_the_crypt_scores_high() -> None:
    tags = classify_volume_tags(
        publisher="EC",
        volume_name="Tales from the Crypt",
        start_year=1950,
        issue_count=46,
        missing_shells=46,
        tier_label="TIER_3_ENGLISH_LONG_TAIL",
        includes_issue_one=True,
    )
    assert TAG_KEY_ISSUE in tags
    assert TAG_NUMBER_ONE in tags
    score = compute_collector_value_score(
        publisher="EC",
        volume_name="Tales from the Crypt",
        start_year=1950,
        issue_count=46,
        missing_shells=46,
        tier_label="TIER_3_ENGLISH_LONG_TAIL",
        tags=tags,
        includes_issue_one=True,
    )
    assert score >= 90


def test_execution_group_a_threshold() -> None:
    assert _execution_group(90.0, [TAG_KEY_ISSUE]) == GROUP_A
