from __future__ import annotations

import pytest

from app.services.catalog_import_quality_service import detect_probable_non_english, score_import_candidate
from app.services.catalog_publisher_registry import (
    is_international_publisher,
    is_primary_us_publisher,
    publisher_quality_score,
)
from app.services.comicvine_catalog_importer import should_import_volume


def test_primary_us_publishers() -> None:
    assert is_primary_us_publisher("Marvel")
    assert is_primary_us_publisher("Marvel Comics")
    assert is_primary_us_publisher("DC Comics")
    assert is_primary_us_publisher("Image Comics")


def test_international_publishers_rejected() -> None:
    assert is_international_publisher("Panini Comics")
    assert is_international_publisher("Delcourt")
    assert is_international_publisher("Egmont Comics")


def test_should_import_spawn_image_only() -> None:
    image = should_import_volume(
        publisher="Image",
        series_name="Spawn",
        volume_metadata={},
        allow_international_editions=False,
        strict_english=True,
    )
    panini = should_import_volume(
        publisher="Panini Comics",
        series_name="Spawn",
        volume_metadata={},
        allow_international_editions=False,
        strict_english=True,
    )
    assert image.allowed is True
    assert panini.allowed is False
    assert panini.reason == "INTERNATIONAL_LICENSE_EDITION"


def test_international_override() -> None:
    decision = should_import_volume(
        publisher="Panini Comics",
        series_name="Spawn",
        volume_metadata={},
        allow_international_editions=True,
        strict_english=False,
    )
    assert decision.allowed is True
    assert decision.reason == "INTERNATIONAL_ALLOWED"


def test_probable_non_english_series() -> None:
    flagged, signals = detect_probable_non_english(publisher="Image", series_name="Spawn \u00c9dition")
    assert flagged is True
    assert "non_english_characters_in_series" in signals
    decision = should_import_volume(
        publisher="Image",
        series_name="Spawn \u00c9dition",
        volume_metadata={},
        allow_international_editions=False,
        strict_english=True,
    )
    assert decision.allowed is False
    assert decision.reason == "PROBABLE_NON_ENGLISH_EDITION"


def test_quality_tiers() -> None:
    primary = score_import_candidate(publisher="Marvel", series_name="Amazing Spider-Man")
    assert primary.quality_tier == "PRIMARY"
    assert primary.quality_score >= 90
    intl = score_import_candidate(publisher="Panini Comics", series_name="Spawn")
    assert intl.quality_tier == "REJECT"


def test_publisher_quality_score() -> None:
    assert publisher_quality_score("Marvel") == 100
    assert publisher_quality_score("Panini Comics") == 0
