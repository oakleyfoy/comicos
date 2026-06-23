"""Series name compatibility for photo import / ComicVine volume pick."""

from __future__ import annotations

from app.services.catalog_ingestion_service import normalize_series_name, series_names_compatible


def test_superman_not_compatible_with_superman_batman() -> None:
    assert not series_names_compatible(
        normalize_series_name("Superman"),
        normalize_series_name("Superman/Batman"),
    )


def test_superman_compatible_with_year_suffix() -> None:
    assert series_names_compatible(
        normalize_series_name("Superman"),
        normalize_series_name("Superman (2016)"),
    )
