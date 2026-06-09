"""Display URL helpers for import line covers."""

from __future__ import annotations

from typing import Any


def effective_import_cover_url(item: dict[str, Any] | Any) -> str | None:
    """Unified display URL for API + UI (thumb > full > retailer > cover_url alias)."""
    if isinstance(item, dict):
        for key in (
            "cover_thumbnail_url",
            "cover_image_url",
            "cover_url",
            "retailer_cover_url",
        ):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    for attr in (
        "cover_thumbnail_url",
        "cover_image_url",
        "cover_url",
        "retailer_cover_url",
    ):
        value = getattr(item, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def item_has_verified_cover_lock(item: dict[str, Any]) -> bool:
    if item.get("cover_verified_by") != "USER":
        return False
    return effective_import_cover_url(item) is not None


def cover_display_fields_from_urls(
    *,
    cover_image_url: str | None,
    cover_thumbnail_url: str | None,
    retailer_cover_url: str | None = None,
) -> dict[str, Any]:
    display = (
        (cover_thumbnail_url or "").strip()
        or (cover_image_url or "").strip()
        or (retailer_cover_url or "").strip()
        or None
    )
    has_cover = bool(display)
    return {
        "cover_image_url": cover_image_url or display,
        "cover_thumbnail_url": cover_thumbnail_url or display,
        "cover_url": display,
        "has_cover_image": has_cover if display else False,
    }
