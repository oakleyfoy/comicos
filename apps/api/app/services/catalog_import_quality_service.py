from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.catalog_publisher_registry import (
    is_international_publisher,
    is_primary_us_publisher,
)
from app.services.catalog_ingestion_service import normalize_series_name

_NON_ENGLISH_CHARS = re.compile(r"[ÉÄÖÜÑéäöüñ]")
_TRANSLATION_WORDS = re.compile(
    r"\b(edition|édition|ausgabe|colección|colecao|samling|tome)\b",
    re.IGNORECASE,
)

KNOWN_COLLECTOR_PUBLISHERS = frozenset(
    {
        "Archie Comics",
        "Dark Horse Comics",
        "Image Comics",
        "BOOM Studios",
    }
)


@dataclass(frozen=True)
class CatalogImportQuality:
    quality_score: int
    quality_tier: str
    recommendation: str


def detect_series_language_signals(series_name: str | None) -> list[str]:
    signals: list[str] = []
    series = series_name or ""
    if _NON_ENGLISH_CHARS.search(series):
        signals.append("non_english_characters_in_series")
    if _TRANSLATION_WORDS.search(series):
        signals.append("translation_edition_keyword_in_series")
    return signals


def detect_probable_non_english(*, publisher: str | None, series_name: str | None) -> tuple[bool, list[str]]:
    signals = detect_series_language_signals(series_name)
    if is_international_publisher(publisher):
        signals.append("international_publisher")
    return bool(signals), signals


def _tier_for_score(score: int) -> str:
    if score >= 90:
        return "PRIMARY"
    if score >= 60:
        return "ACCEPTABLE"
    if score >= 1:
        return "LOW_PRIORITY"
    return "REJECT"


def _recommendation_for_tier(tier: str) -> str:
    return {
        "PRIMARY": "import",
        "ACCEPTABLE": "import",
        "LOW_PRIORITY": "import_with_caution",
        "REJECT": "skip",
    }[tier]


def _collector_publisher_bonus(publisher: str) -> int:
    norm = normalize_series_name(publisher)
    for name in KNOWN_COLLECTOR_PUBLISHERS:
        if norm == normalize_series_name(name) or norm.startswith(normalize_series_name(name)):
            return 25
    return 0


def score_import_candidate(
    *,
    publisher: str | None,
    series_name: str | None,
    volume_metadata: dict[str, Any] | None = None,
) -> CatalogImportQuality:
    _ = volume_metadata
    score = 0
    pub = publisher or ""
    if is_primary_us_publisher(pub):
        score += 100
    elif not is_international_publisher(pub):
        score += 50
    score += _collector_publisher_bonus(pub)
    if is_international_publisher(pub):
        score -= 100
    non_english, signals = detect_probable_non_english(publisher=pub, series_name=series_name)
    if non_english:
        score -= 50
    if "translation_edition_keyword_in_series" in signals:
        score -= 75
    tier = _tier_for_score(score)
    return CatalogImportQuality(
        quality_score=score,
        quality_tier=tier,
        recommendation=_recommendation_for_tier(tier),
    )
