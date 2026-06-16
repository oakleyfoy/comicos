"""P98 — gap priority scoring + major publisher registry.

Pure, side-effect-free scoring used by the gap service, report, and action
queue generator. No DB writes, no ComicVine calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.catalog_ingestion_service import normalize_series_name

# ---------------------------------------------------------------------------
# Major publisher registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MajorPublisher:
    canonical: str
    weight: int
    aliases: tuple[str, ...]  # normalized aliases


MAJOR_PUBLISHERS: tuple[MajorPublisher, ...] = (
    MajorPublisher("Marvel", 10000, ("marvel",)),
    MajorPublisher("DC Comics", 10000, ("dc comics", "dc")),
    MajorPublisher("Image", 8000, ("image", "image comics")),
    MajorPublisher("Dark Horse Comics", 7000, ("dark horse comics", "dark horse")),
    MajorPublisher("IDW Publishing", 7000, ("idw publishing", "idw")),
    MajorPublisher("Boom! Studios", 7000, ("boom studios", "boom")),
    MajorPublisher("Archie Comics", 6000, ("archie comics", "archie")),
    MajorPublisher("Valiant", 6000, ("valiant",)),
    MajorPublisher("Dynamite", 6000, ("dynamite", "dynamite entertainment")),
)

# Core title bonus value (spec lists the titles; this is the weight applied).
CORE_TITLE_BONUS = 5000

CORE_TITLES: frozenset[str] = frozenset(
    normalize_series_name(t)
    for t in (
        "Batman",
        "Detective Comics",
        "Action Comics",
        "Superman",
        "Amazing Spider-Man",
        "Uncanny X-Men",
        "X-Men",
        "Fantastic Four",
        "Avengers",
        "Venom",
        "Spawn",
        "Invincible",
        "Teenage Mutant Ninja Turtles",
        "Walking Dead",
        "Flash",
    )
)


def _alias_matches(publisher_normalized: str, alias: str) -> bool:
    return publisher_normalized == alias or publisher_normalized.startswith(alias + " ")


def major_publisher_for(publisher_normalized: str) -> MajorPublisher | None:
    """Return the registry entry for a normalized publisher name, if major."""
    norm = (publisher_normalized or "").strip()
    if not norm:
        return None
    for entry in MAJOR_PUBLISHERS:
        if any(_alias_matches(norm, alias) for alias in entry.aliases):
            return entry
    return None


def resolve_requested_publisher(requested: str) -> MajorPublisher | None:
    """Resolve a user-supplied publisher string (e.g. 'Marvel', 'DC Comics')."""
    norm = normalize_series_name(requested or "")
    if not norm:
        return None
    for entry in MAJOR_PUBLISHERS:
        if norm == normalize_series_name(entry.canonical) or any(
            norm == alias or _alias_matches(norm, alias) for alias in entry.aliases
        ):
            return entry
    return None


def publisher_weight(publisher_normalized: str) -> int:
    entry = major_publisher_for(publisher_normalized)
    return entry.weight if entry else 0


def is_core_title(volume_name: str) -> bool:
    return normalize_series_name(volume_name) in CORE_TITLES


def recent_year_bonus(start_year: int | None) -> int:
    if start_year is None:
        return 0
    if start_year >= 2020:
        return 3000
    if start_year >= 2010:
        return 2000
    if start_year >= 2000:
        return 1000
    return 0


def volume_size_bonus(issue_count: int | None) -> int:
    return min(int(issue_count or 0), 1000)


def score_volume(
    *,
    publisher_normalized: str,
    volume_name: str,
    start_year: int | None,
    missing_issue_count: int,
    issue_count: int | None,
) -> int:
    """priority = publisher_weight + missing*100 + core_bonus + year_bonus + size_bonus."""
    score = publisher_weight(publisher_normalized)
    score += max(int(missing_issue_count or 0), 0) * 100
    score += CORE_TITLE_BONUS if is_core_title(volume_name) else 0
    score += recent_year_bonus(start_year)
    score += volume_size_bonus(issue_count)
    return int(score)
