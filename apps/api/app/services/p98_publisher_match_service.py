"""P98 — US-first publisher preference for core series matching."""

from __future__ import annotations

from typing import Any

from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p97_core_run_registry import publisher_matches_expected

MATCH_EXACT = "EXACT_MATCH"
MATCH_WRONG = "WRONG_PUBLISHER_MATCH"
MATCH_FOREIGN = "FOREIGN_EDITION_MATCH"
MATCH_COLLECTED = "COLLECTED_EDITION_MATCH"
MATCH_UNKNOWN = "UNKNOWN"

# Translated / foreign-market publishers — strong penalty vs US core targets.
FOREIGN_MARKET_PUBLISHERS: frozenset[str] = frozenset(
    {
        "ecc ediciones",
        "panini comics",
        "panini espana",
        "panini spain",
        "panini",
        "egmont",
        "egmont comics",
        "editoriale corno",
        "eura editoriale",
        "sergio bonelli editore",
        "williams forlag ab",
        "williams förlag ab",
        "1000voltemeglio publishing",
        "rebellion",
    }
)

US_CORE_PUBLISHERS: frozenset[str] = frozenset(
    {
        "dc comics",
        "dc",
        "marvel",
        "marvel comics",
        "image",
        "image comics",
        "dark horse comics",
        "dark horse",
        "boom studios",
        "boom! studios",
        "boom",
        "idw publishing",
        "idw",
        "dynamite entertainment",
        "dynamite",
        "valiant",
        "valiant comics",
    }
)

_COLLECTED_HINTS: tuple[str, ...] = (
    "annual",
    "omnibus",
    "collection",
    "collected",
    "tpb",
    "trade paperback",
    "hardcover",
    "gallery edition",
    "80-page giant",
    "giant",
    "special",
)


def _norm(text: str | None) -> str:
    return normalize_series_name(text or "")


def _publisher_matches_set(publisher: str | None, keys: frozenset[str]) -> bool:
    pub = _norm(publisher)
    if not pub:
        return False
    for key in keys:
        if pub == key or pub.startswith(f"{key} "):
            return True
        if key.startswith(f"{pub} "):
            return True
    return False


def is_foreign_market_publisher(publisher: str | None) -> bool:
    return _publisher_matches_set(publisher, FOREIGN_MARKET_PUBLISHERS)


def is_us_core_publisher(publisher: str | None) -> bool:
    return _publisher_matches_set(publisher, US_CORE_PUBLISHERS)


def is_collected_edition_name(name: str | None) -> bool:
    title = _norm(name)
    if not title:
        return False
    for hint in _COLLECTED_HINTS:
        if hint in title:
            return True
    return False


def publisher_preference_tier(publisher: str | None, expected: str | None) -> int:
    """Higher tier wins. US core targets must beat foreign editions."""
    if publisher_matches_expected(publisher, expected):
        return 5
    if is_us_core_publisher(publisher) and publisher_matches_expected(publisher, expected) is False:
        if expected and is_us_core_publisher(expected):
            return 4
        if is_us_core_publisher(publisher):
            return 4
    if is_us_core_publisher(publisher):
        return 3
    if is_foreign_market_publisher(publisher):
        return 1
    return 2


def publisher_match_type(
    *,
    expected_publisher: str | None,
    matched_publisher: str | None,
    volume_name: str | None,
) -> str:
    if is_collected_edition_name(volume_name):
        return MATCH_COLLECTED
    if publisher_matches_expected(matched_publisher, expected_publisher):
        return MATCH_EXACT
    if is_foreign_market_publisher(matched_publisher):
        return MATCH_FOREIGN
    if expected_publisher and matched_publisher:
        return MATCH_WRONG
    return MATCH_UNKNOWN


def universe_match_sort_key(
    *,
    publisher: str | None,
    expected_publisher: str | None,
    issue_count: int | None,
    start_year: int | None,
    name: str | None,
) -> tuple[int, int, int, int]:
    """Sort key for max(): tier, issues, -year, collected penalty."""
    tier = publisher_preference_tier(publisher, expected_publisher)
    issues = int(issue_count or 0)
    start = int(start_year) if start_year is not None else 9999
    collected_penalty = 0 if not is_collected_edition_name(name) else -1
    return (tier, issues, -start, collected_penalty)


def build_publisher_match_rule_analysis() -> dict[str, Any]:
    """Document current matching rules (analysis artifact; no DB)."""
    return {
        "version": "p98-18b",
        "selection": {
            "entry_point": "pick_best_universe_match (p97_core_run_registry)",
            "candidate_pool": "ComicVineVolumeUniverse rows where volume_title_matches_report_label",
            "sort_key": "publisher_preference_tier (p98), then issue_count desc, then start_year asc",
            "publisher_tiers": [
                "1 exact expected publisher",
                "2 same-language US publisher (US_CORE_PUBLISHERS)",
                "3 US core publisher family",
                "4 alternate non-foreign editions",
                "5 foreign / translated-market editions (penalized)",
            ],
        },
        "foreign_publishers": sorted(FOREIGN_MARKET_PUBLISHERS),
        "us_core_publishers": sorted(US_CORE_PUBLISHERS),
        "collected_edition_hints": list(_COLLECTED_HINTS),
        "alternate_editions": {
            "treatment": "Collected/annual/special names receive collected_penalty in sort key",
            "match_type": MATCH_COLLECTED,
        },
        "foreign_editions": {
            "treatment": "Tier 1 — cannot outrank US core publisher tier 3+ for same core label",
            "match_type": MATCH_FOREIGN,
        },
        "repair": {
            "non_canonical_core_volumes": "Excluded from P97 discovered-not-queued audit",
            "universe_volume_status": "foreign_superseded when --apply marks superseded P98 rows",
        },
    }
