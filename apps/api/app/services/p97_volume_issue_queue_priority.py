"""US/direct-market launch priority for P97 volume issue import queue."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p97_queue_priority_config import compute_collector_queue_score

TIER_0_MANUAL = "tier_0_manual_request"
TIER_1_CORE = "tier_1_core"
TIER_2_LEGACY = "tier_2_legacy"
TIER_3_OTHER_US = "tier_3_other_us"
TIER_4_DEPRIORITIZED = "tier_4_deprioritized"

LAUNCH_PRIORITY_TIERS: tuple[str, ...] = (
    TIER_0_MANUAL,
    TIER_1_CORE,
    TIER_2_LEGACY,
    TIER_3_OTHER_US,
    TIER_4_DEPRIORITIZED,
)

MANUAL_REQUEST_PRIORITY_SCORE = 1_000_000.0
URGENT_MANUAL_REQUEST_PRIORITY_SCORE = 2_000_000.0

# Cap so enormous foreign runs cannot dominate via missing count alone.
MISSING_ISSUE_SCORE_CAP = 80
MISSING_ISSUE_SCORE_MULTIPLIER = 12.0

TIER_SCORE_BASE: dict[str, float] = {
    TIER_1_CORE: 100_000.0,
    TIER_2_LEGACY: 70_000.0,
    TIER_3_OTHER_US: 25_000.0,
    TIER_4_DEPRIORITIZED: 5_000.0,
}

TIER_1_PUBLISHERS: frozenset[str] = frozenset(
    {
        "marvel",
        "marvel comics",
        "dc",
        "dc comics",
        "image",
        "image comics",
        "dark horse comics",
        "idw publishing",
        "boom",
        "boom studios",
        "boom! studios",
        "archie",
        "archie comics",
        "dynamite",
        "dynamite entertainment",
        "valiant",
        "valiant comics",
    }
)

TIER_2_PUBLISHERS: frozenset[str] = frozenset(
    {
        "dell",
        "dell comics",
        "western publishing",
        "charlton",
        "charlton comics",
        "harvey",
        "harvey comics",
        "fawcett publications",
        "fawcett",
        "gold key",
        "gold key comics",
        "warren",
        "warren publishing",
    }
)

DEPRIORITIZED_PUBLISHERS: frozenset[str] = frozenset(
    {
        "panini comics",
        "panini",
        "egmont comics",
        "egmont",
        "eura editoriale",
        "sergio bonelli editore",
        "rebellion",
        "1000voltemeglio publishing",
        "editoriale corno",
    }
)

FOREIGN_ANTHOLOGY_TITLES: frozenset[str] = frozenset(
    {
        "topolino",
        "lanciostory",
        "skorpio",
        "fantomen",
        "91 an",
        "serie magasinet",
        "knasen",
        "kalle anka",
        "diabolik",
        "dylan dog",
        "bamse",
    }
)

_ANTHOLOGY_PHRASE_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _anthology_phrase_pattern(phrase: str) -> re.Pattern[str]:
    cached = _ANTHOLOGY_PHRASE_PATTERN_CACHE.get(phrase)
    if cached is not None:
        return cached
    escaped = re.escape(phrase)
    pattern = re.compile(rf"(?:^|\s){escaped}(?:\s|$)")
    _ANTHOLOGY_PHRASE_PATTERN_CACHE[phrase] = pattern
    return pattern


@dataclass(frozen=True)
class VolumeImportPriority:
    priority_score: float
    launch_priority_tier: str


def _normalized_publisher(publisher: str | None) -> str:
    return normalize_series_name(publisher or "")


def _normalized_title(name: str | None) -> str:
    return normalize_series_name(name or "")


def _matches_publisher_set(publisher_norm: str, candidates: frozenset[str]) -> bool:
    if not publisher_norm:
        return False
    if publisher_norm in candidates:
        return True
    for candidate in candidates:
        if publisher_norm.startswith(f"{candidate} "):
            return True
        if candidate.startswith(publisher_norm + " "):
            return True
    return False


def is_foreign_anthology_title(name: str | None) -> bool:
    title = _normalized_title(name)
    if not title:
        return False
    for phrase in FOREIGN_ANTHOLOGY_TITLES:
        if title == phrase:
            return True
        if _anthology_phrase_pattern(phrase).search(title):
            return True
    return False


def classify_launch_priority_tier(
    *,
    publisher: str | None,
    name: str | None,
) -> str:
    pub_norm = _normalized_publisher(publisher)
    if is_foreign_anthology_title(name):
        return TIER_4_DEPRIORITIZED
    if _matches_publisher_set(pub_norm, DEPRIORITIZED_PUBLISHERS):
        return TIER_4_DEPRIORITIZED
    if _matches_publisher_set(pub_norm, TIER_1_PUBLISHERS):
        return TIER_1_CORE
    if _matches_publisher_set(pub_norm, TIER_2_PUBLISHERS):
        return TIER_2_LEGACY
    return TIER_3_OTHER_US


def compute_volume_import_priority(
    *,
    missing_issue_count: int,
    count_of_issues: int,
    coverage_percent: float,
    publisher: str | None,
    name: str | None,
    start_year: int | None = None,
) -> VolumeImportPriority:
    del coverage_percent  # retained for API compatibility
    tier = classify_launch_priority_tier(publisher=publisher, name=name)
    score = compute_collector_queue_score(
        publisher=publisher,
        name=name,
        missing_issue_count=missing_issue_count,
        total_issue_count=count_of_issues,
        start_year=start_year,
        force_foreign_archive=is_foreign_anthology_title(name),
    )
    return VolumeImportPriority(priority_score=score, launch_priority_tier=tier)


# Backward-compatible alias for tests/callers.
def compute_priority_score(
    *,
    missing_issue_count: int,
    count_of_issues: int,
    coverage_percent: float,
    publisher: str | None,
    name: str | None = None,
) -> float:
    return compute_volume_import_priority(
        missing_issue_count=missing_issue_count,
        count_of_issues=count_of_issues,
        coverage_percent=coverage_percent,
        publisher=publisher,
        name=name,
    ).priority_score


def compute_manual_request_priority(*, urgent: bool = False) -> VolumeImportPriority:
    score = URGENT_MANUAL_REQUEST_PRIORITY_SCORE if urgent else MANUAL_REQUEST_PRIORITY_SCORE
    return VolumeImportPriority(priority_score=score, launch_priority_tier=TIER_0_MANUAL)
