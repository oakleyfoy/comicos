"""Shared helpers for P98 master universe services."""

from __future__ import annotations

import zlib

from app.services.catalog_ingestion_service import normalize_series_name

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

PUBLISHER_EXPANSION_PRIORITY = (
    "marvel",
    "dc comics",
    "image",
    "dark horse comics",
    "idw publishing",
    "idw",
    "boom studios",
    "boom",
    "archie comics",
    "valiant",
    "dynamite",
)


def clamp_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return DEFAULT_LIMIT
    return min(int(limit), MAX_LIMIT)


def clamp_offset(offset: int | None) -> int:
    if offset is None or offset < 0:
        return 0
    return int(offset)


def normalize_publisher_name(name: str) -> str:
    return normalize_series_name(name)


def synthetic_publisher_id(normalized_name: str) -> int:
    """Stable negative id when ComicVine publisher id is not yet known."""
    crc = zlib.crc32(normalized_name.encode("utf-8")) & 0x7FFFFFFF
    return -int(crc or 1)


def publisher_priority_rank(normalized_name: str) -> int | None:
    key = normalize_publisher_name(normalized_name)
    for index, label in enumerate(PUBLISHER_EXPANSION_PRIORITY):
        if key == label or key.startswith(label):
            return index
    return None
