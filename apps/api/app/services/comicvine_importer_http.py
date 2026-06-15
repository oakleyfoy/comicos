"""Shared ComicVine HTTP settings aligned with ``ComicVineCatalogImporter``."""

from __future__ import annotations

from app.core.config import Settings

DEFAULT_COMICVINE_BASE_URL = "https://comicvine.gamespot.com/api"
# Observed known-good volume from P97 manual seeds (Amazing Spider-Man).
DEFAULT_DIAGNOSTIC_VOLUME_ID = 87154


def comicvine_importer_user_agent(settings: Settings) -> str:
    return settings.catalog_import_user_agent


def comicvine_importer_request_headers(settings: Settings) -> dict[str, str]:
    return {"User-Agent": comicvine_importer_user_agent(settings)}


def comicvine_importer_base_url(settings: Settings) -> str:
    return (settings.comicvine_api_base_url or DEFAULT_COMICVINE_BASE_URL).rstrip("/")
