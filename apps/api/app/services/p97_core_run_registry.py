"""Canonical core runs with expected publishers for P97 discovery and audit."""

from __future__ import annotations

from typing import Callable, TypeVar

from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p97_queue_priority_config import is_core_run

T = TypeVar("T")

CORE_RUNS: dict[str, dict[str, str]] = {
    "Batman": {"publisher": "DC Comics"},
    "Detective Comics": {"publisher": "DC Comics"},
    "Action Comics": {"publisher": "DC Comics"},
    "Superman": {"publisher": "DC Comics"},
    "Flash": {"publisher": "DC Comics"},
    "Wonder Woman": {"publisher": "DC Comics"},
    "Green Lantern": {"publisher": "DC Comics"},
    "Justice League": {"publisher": "DC Comics"},
    "Amazing Spider-Man": {"publisher": "Marvel"},
    "The Amazing Spider-Man": {"publisher": "Marvel"},
    "Uncanny X-Men": {"publisher": "Marvel"},
    "X-Men": {"publisher": "Marvel"},
    "Fantastic Four": {"publisher": "Marvel"},
    "Avengers": {"publisher": "Marvel"},
    "Venom": {"publisher": "Marvel"},
    "Daredevil": {"publisher": "Marvel"},
    "Thor": {"publisher": "Marvel"},
    "Captain America": {"publisher": "Marvel"},
    "Iron Man": {"publisher": "Marvel"},
    "Hulk": {"publisher": "Marvel"},
    "Spawn": {"publisher": "Image"},
    "Invincible": {"publisher": "Image"},
    "The Walking Dead": {"publisher": "Image"},
    "Teenage Mutant Ninja Turtles": {"publisher": "IDW Publishing"},
    "Archie": {"publisher": "Archie Comics"},
}

# One report row per canonical collector run (aliases merged).
CORE_RUN_REPORT_LABELS: tuple[str, ...] = (
    "Batman",
    "Detective Comics",
    "Action Comics",
    "Superman",
    "Flash",
    "Wonder Woman",
    "Green Lantern",
    "Justice League",
    "Amazing Spider-Man",
    "Uncanny X-Men",
    "X-Men",
    "Fantastic Four",
    "Avengers",
    "Venom",
    "Daredevil",
    "Thor",
    "Captain America",
    "Iron Man",
    "Hulk",
    "Spawn",
    "Invincible",
    "The Walking Dead",
    "Teenage Mutant Ninja Turtles",
    "Archie",
)

_REPORT_ALIASES: dict[str, tuple[str, ...]] = {
    "Amazing Spider-Man": ("Amazing Spider-Man", "The Amazing Spider-Man"),
    "Teenage Mutant Ninja Turtles": ("Teenage Mutant Ninja Turtles", "TMNT"),
}


def _norm(text: str | None) -> str:
    return normalize_series_name(text or "")


def registry_keys_for_report_label(label: str) -> tuple[str, ...]:
    return _REPORT_ALIASES.get(label, (label,))


def expected_publisher_for_report_label(label: str) -> str:
    keys = registry_keys_for_report_label(label)
    for key in keys:
        spec = CORE_RUNS.get(key)
        if spec is not None:
            return str(spec["publisher"])
    raise KeyError(f"Unknown core run report label: {label}")


def publisher_matches_expected(actual: str | None, expected: str | None) -> bool:
    needle = _norm(expected)
    hay = _norm(actual)
    if not needle:
        return True
    if not hay:
        return False
    if hay == needle:
        return True
    if hay.startswith(f"{needle} ") or needle.startswith(f"{hay} "):
        return True
    return False


def volume_title_matches_report_label(volume_name: str | None, report_label: str) -> bool:
    if not is_core_run(volume_name, None):
        return False
    title_norm = _norm(volume_name)
    for key in registry_keys_for_report_label(report_label):
        key_norm = _norm(key)
        if title_norm == key_norm:
            return True
        prefix = f"{key_norm} "
        if title_norm.startswith(prefix):
            suffix = title_norm[len(prefix) :].strip()
            if suffix.isdigit() and len(suffix) == 4:
                return True
    return False


def pick_best_universe_match(
    candidates: list[T],
    report_label: str,
    *,
    name_getter: Callable[[T], str | None],
    publisher_getter: Callable[[T], str | None],
    issue_count_getter: Callable[[T], int | None],
    start_year_getter: Callable[[T], int | None],
) -> tuple[T | None, bool]:
    """Return (best row, publisher_match). Rank: publisher, issue count desc, start year asc."""
    if not candidates:
        return None, False
    expected = expected_publisher_for_report_label(report_label)

    def sort_key(row: T) -> tuple[int, int, int]:
        pub_ok = publisher_matches_expected(publisher_getter(row), expected)
        issues = int(issue_count_getter(row) or 0)
        start = start_year_getter(row)
        start_year = int(start) if start is not None else 9999
        return (1 if pub_ok else 0, issues, -start_year)

    best = max(candidates, key=sort_key)
    pub_ok = publisher_matches_expected(publisher_getter(best), expected)
    return best, pub_ok
