from __future__ import annotations

from typing import Literal

CatalogSourceName = Literal[
    "COMICVINE",
    "LEAGUE_OF_COMIC_GEEKS",
    "LUNAR",
    "PRH",
    "DIAMOND",
    "GCD",
    "MANUAL",
    "INTERNAL",
]

# Lower number = higher priority when merging field values.
CATALOG_SOURCE_PRIORITY: dict[str, int] = {
    "MANUAL": 1,
    "INTERNAL": 2,
    "UPC_CONFIRMED": 3,
    "LEAGUE_OF_COMIC_GEEKS": 4,
    "LUNAR": 5,
    "PRH": 5,
    "DIAMOND": 5,
    "COMICVINE": 6,
    "GCD": 7,
}

KEY_ISSUE_RELATIONSHIP_TYPES = frozenset(
    {
        "first_appearance",
        "origin",
        "death",
        "cameo",
        "major_event",
        "first_team_appearance",
        "ratio_variant",
        "low_print_signal",
        "creator_significance",
    }
)

HIGH_CONFIDENCE_SCAN_THRESHOLD = 0.90
