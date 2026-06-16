"""Configurable weights for P97 volume issue import queue collector-first scoring."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.catalog_ingestion_service import normalize_series_name

PUBLISHER_WEIGHT_MULTIPLIER = 100_000
COLLECTOR_POPULARITY_MULTIPLIER = 1_000
MISSING_ISSUE_BONUS_MULTIPLIER = 500
RUN_SIZE_CAP = 1_000
RUN_SIZE_BONUS_MULTIPLIER = 10

CORE_RUN_BONUS = 50_000

FOREIGN_ARCHIVE_PUBLISHER_WEIGHT = 10
DEFAULT_PUBLISHER_WEIGHT = 40

CORE_RUNS: frozenset[str] = frozenset(
    {
        "Batman",
        "Detective Comics",
        "Action Comics",
        "Superman",
        "The Amazing Spider-Man",
        "Amazing Spider-Man",
        "Uncanny X-Men",
        "X-Men",
        "Fantastic Four",
        "Avengers",
        "Venom",
        "Spawn",
        "Invincible",
        "Teenage Mutant Ninja Turtles",
        "TMNT",
        "The Walking Dead",
        "Archie",
        "Daredevil",
        "Captain America",
        "Thor",
        "Iron Man",
        "Hulk",
        "Justice League",
        "Green Lantern",
        "Flash",
        "Wonder Woman",
        "Nightwing",
        "Robin",
    }
)

PUBLISHER_WEIGHTS: dict[str, int] = {
    "dc comics": 100,
    "dc": 100,
    "marvel comics": 100,
    "marvel": 100,
    "image comics": 90,
    "image": 90,
    "dark horse comics": 85,
    "idw publishing": 80,
    "idw": 80,
    "boom studios": 80,
    "boom! studios": 80,
    "boom": 80,
    "archie comics": 75,
    "archie": 75,
    "valiant comics": 75,
    "valiant": 75,
    "dynamite entertainment": 70,
    "dynamite": 70,
    "awa studios": 65,
    "awa": 65,
    "mad cave studios": 65,
    "mad cave": 65,
    "vault comics": 65,
    "vault": 65,
    "aftershock comics": 65,
    "aftershock": 65,
    "titan comics": 65,
    "titan": 65,
    "dell comics": 50,
    "dell": 50,
    "charlton comics": 50,
    "charlton": 50,
    "harvey comics": 50,
    "harvey": 50,
}

FOREIGN_ARCHIVE_PUBLISHERS: frozenset[str] = frozenset(
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

COLLECTOR_POPULARITY_TITLE_BOOSTS: tuple[tuple[str, int], ...] = (
    ("the amazing spider man", 500),
    ("amazing spider man", 500),
    ("uncanny x men", 500),
    ("fantastic four", 500),
    ("detective comics", 500),
    ("action comics", 500),
    ("teenage mutant ninja turtles", 450),
    ("walking dead", 450),
    ("invincible", 450),
    ("spawn", 450),
    ("batman", 500),
    ("venom", 500),
    ("archie", 400),
    ("tmnt", 450),
    ("superman", 500),
    ("avengers", 500),
    ("daredevil", 450),
    ("captain america", 450),
    ("x men", 500),
)

YEAR_BONUS_2020_PLUS = 1_000
YEAR_BONUS_2010_2019 = 500
YEAR_BONUS_2000_2009 = 250


def _normalized_title_static(name: str) -> str:
    return normalize_series_name(name or "")


_CORE_RUNS_NORMALIZED: tuple[str, ...] = tuple(
    sorted((_normalized_title_static(name) for name in CORE_RUNS), key=len, reverse=True)
)


def _normalized_publisher(publisher: str | None) -> str:
    return normalize_series_name(publisher or "")


def _normalized_title(name: str | None) -> str:
    return normalize_series_name(name or "")


def _publisher_matches_key(publisher_norm: str, key: str) -> bool:
    if not publisher_norm:
        return False
    if publisher_norm == key:
        return True
    if publisher_norm.startswith(f"{key} "):
        return True
    if key.startswith(f"{publisher_norm} "):
        return True
    return False


def _title_matches_core_run(title_norm: str, core_norm: str) -> bool:
    """Exact core title, or core title plus a single 4-digit year suffix only."""
    if not title_norm or not core_norm:
        return False
    if title_norm == core_norm:
        return True
    prefix = f"{core_norm} "
    if not title_norm.startswith(prefix):
        return False
    suffix = title_norm[len(prefix) :].strip()
    return bool(suffix.isdigit() and len(suffix) == 4)


def is_core_run(volume_name: str | None, start_year: int | None = None) -> bool:
    title = _normalized_title(volume_name)
    if not title:
        return False
    candidates = [title]
    if start_year is not None:
        year = int(start_year)
        if 1000 <= year <= 9999:
            candidates.append(f"{title} {year}")
    for candidate in candidates:
        for core_norm in _CORE_RUNS_NORMALIZED:
            if _title_matches_core_run(candidate, core_norm):
                return True
    return False


def is_flagship_run(name: str | None) -> bool:
    """Backward-compatible alias for reporting callers without start_year."""
    return is_core_run(name, None)


def resolve_publisher_weight(
    publisher: str | None,
    *,
    force_foreign_archive: bool = False,
) -> int:
    if force_foreign_archive:
        return FOREIGN_ARCHIVE_PUBLISHER_WEIGHT
    pub_norm = _normalized_publisher(publisher)
    if pub_norm and any(
        _publisher_matches_key(pub_norm, foreign) for foreign in FOREIGN_ARCHIVE_PUBLISHERS
    ):
        return FOREIGN_ARCHIVE_PUBLISHER_WEIGHT
    best_weight = DEFAULT_PUBLISHER_WEIGHT
    best_key_len = -1
    for key, weight in PUBLISHER_WEIGHTS.items():
        if _publisher_matches_key(pub_norm, key) and len(key) > best_key_len:
            best_weight = weight
            best_key_len = len(key)
    return best_weight


def resolve_collector_popularity_weight(
    name: str | None,
    *,
    start_year: int | None = None,
) -> int:
    if not is_core_run(name, start_year):
        return 0
    title = _normalized_title(name)
    if not title:
        return 0
    for phrase, boost in COLLECTOR_POPULARITY_TITLE_BOOSTS:
        if title == phrase or _title_matches_core_run(title, phrase):
            return boost
        if phrase in title and title.startswith(phrase):
            remainder = title[len(phrase) :].strip()
            if not remainder or (remainder.isdigit() and len(remainder) == 4):
                return boost
    return 0


def resolve_core_run_bonus(name: str | None, *, start_year: int | None = None) -> int:
    return CORE_RUN_BONUS if is_core_run(name, start_year) else 0


def resolve_run_size_bonus(total_issue_count: int) -> int:
    capped = min(max(int(total_issue_count), 0), RUN_SIZE_CAP)
    return capped * RUN_SIZE_BONUS_MULTIPLIER


def resolve_missing_issue_bonus(missing_issue_count: int) -> int:
    return max(int(missing_issue_count), 0) * MISSING_ISSUE_BONUS_MULTIPLIER


def resolve_recent_year_bonus(start_year: int | None) -> int:
    if start_year is None:
        return 0
    year = int(start_year)
    if year >= 2020:
        return YEAR_BONUS_2020_PLUS
    if year >= 2010:
        return YEAR_BONUS_2010_2019
    if year >= 2000:
        return YEAR_BONUS_2000_2009
    return 0


@dataclass(frozen=True)
class CollectorQueueScoreBreakdown:
    publisher_weight: int
    collector_popularity_weight: int
    core_run_bonus: int
    run_size_bonus: int
    missing_issue_bonus: int
    year_bonus: int
    priority_score: float
    is_core_run: bool
    run_size: int
    missing_issues: int


def build_collector_queue_score_breakdown(
    *,
    publisher: str | None,
    name: str | None,
    missing_issue_count: int,
    total_issue_count: int,
    start_year: int | None = None,
    force_foreign_archive: bool = False,
) -> CollectorQueueScoreBreakdown:
    publisher_weight = resolve_publisher_weight(
        publisher, force_foreign_archive=force_foreign_archive
    )
    popularity = resolve_collector_popularity_weight(name, start_year=start_year)
    core_bonus = resolve_core_run_bonus(name, start_year=start_year)
    run_size_bonus = resolve_run_size_bonus(total_issue_count)
    missing_bonus = resolve_missing_issue_bonus(missing_issue_count)
    year_bonus = resolve_recent_year_bonus(start_year)
    score = (
        publisher_weight * PUBLISHER_WEIGHT_MULTIPLIER
        + popularity * COLLECTOR_POPULARITY_MULTIPLIER
        + core_bonus
        + missing_bonus
        + run_size_bonus
        + year_bonus
    )
    missing = max(int(missing_issue_count), 0)
    return CollectorQueueScoreBreakdown(
        publisher_weight=publisher_weight,
        collector_popularity_weight=popularity,
        core_run_bonus=core_bonus,
        run_size_bonus=run_size_bonus,
        missing_issue_bonus=missing_bonus,
        year_bonus=year_bonus,
        priority_score=round(float(score), 2),
        is_core_run=is_core_run(name, start_year),
        run_size=int(total_issue_count or 0),
        missing_issues=missing,
    )


def compute_collector_queue_score(
    *,
    publisher: str | None,
    name: str | None,
    missing_issue_count: int,
    total_issue_count: int = 0,
    start_year: int | None = None,
    force_foreign_archive: bool = False,
) -> float:
    """Collector-first queue score (higher = sooner import)."""
    return build_collector_queue_score_breakdown(
        publisher=publisher,
        name=name,
        missing_issue_count=missing_issue_count,
        total_issue_count=total_issue_count,
        start_year=start_year,
        force_foreign_archive=force_foreign_archive,
    ).priority_score
