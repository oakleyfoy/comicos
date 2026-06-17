"""P98 — Major publisher registry for gap analysis and missing-volume discovery."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.catalog_ingestion_service import normalize_series_name

# Expansion / gap priority weights (unchanged from P98-16).
WEIGHT_MARVEL_DC = 10000
WEIGHT_IMAGE = 8000
WEIGHT_MID = 7000
WEIGHT_LOWER = 6000


@dataclass(frozen=True)
class MajorPublisherConfig:
    canonical: str
    weight: int
    aliases: tuple[str, ...]
    expected_comicvine_publisher_names: tuple[str, ...]

    def normalized_aliases(self) -> frozenset[str]:
        return frozenset(normalize_series_name(a) for a in self.aliases)


REGISTRY: tuple[MajorPublisherConfig, ...] = (
    MajorPublisherConfig(
        "Marvel",
        WEIGHT_MARVEL_DC,
        ("Marvel", "Marvel Comics"),
        ("Marvel",),
    ),
    MajorPublisherConfig(
        "DC Comics",
        WEIGHT_MARVEL_DC,
        ("DC", "DC Comics"),
        ("DC Comics",),
    ),
    MajorPublisherConfig(
        "Image",
        WEIGHT_IMAGE,
        ("Image", "Image Comics"),
        ("Image",),
    ),
    MajorPublisherConfig(
        "Dark Horse Comics",
        WEIGHT_MID,
        ("Dark Horse", "Dark Horse Comics"),
        ("Dark Horse Comics", "Dark Horse"),
    ),
    MajorPublisherConfig(
        "IDW Publishing",
        WEIGHT_MID,
        ("IDW", "IDW Publishing"),
        ("IDW Publishing", "IDW"),
    ),
    MajorPublisherConfig(
        "Boom! Studios",
        WEIGHT_MID,
        ("Boom", "Boom!", "Boom! Studios", "BOOM! Studios"),
        ("Boom! Studios", "BOOM! Studios"),
    ),
    MajorPublisherConfig(
        "Archie Comics",
        WEIGHT_LOWER,
        ("Archie", "Archie Comics"),
        ("Archie Comics", "Archie"),
    ),
    MajorPublisherConfig(
        "Valiant",
        WEIGHT_LOWER,
        ("Valiant", "Valiant Entertainment", "Valiant Comics"),
        ("Valiant", "Valiant Entertainment"),
    ),
    MajorPublisherConfig(
        "Dynamite",
        WEIGHT_LOWER,
        ("Dynamite", "Dynamite Entertainment"),
        ("Dynamite Entertainment", "Dynamite"),
    ),
)


def _alias_matches(normalized: str, alias: str) -> bool:
    a = normalize_series_name(alias)
    return normalized == a or normalized.startswith(a + " ")


def resolve_major_publisher(requested: str) -> MajorPublisherConfig | None:
    norm = normalize_series_name(requested or "")
    if not norm:
        return None
    for entry in REGISTRY:
        if norm == normalize_series_name(entry.canonical):
            return entry
        if any(norm == normalize_series_name(a) or _alias_matches(norm, a) for a in entry.aliases):
            return entry
    return None


def config_for_comicvine_publisher_name(publisher: str | None) -> MajorPublisherConfig | None:
    if not publisher or not str(publisher).strip():
        return None
    norm = normalize_series_name(publisher)
    for entry in REGISTRY:
        for expected in entry.expected_comicvine_publisher_names:
            if norm == normalize_series_name(expected) or _alias_matches(norm, expected):
                return entry
        for alias in entry.aliases:
            if norm == normalize_series_name(alias) or _alias_matches(norm, alias):
                return entry
    return None


def all_major_publishers() -> tuple[MajorPublisherConfig, ...]:
    return REGISTRY
