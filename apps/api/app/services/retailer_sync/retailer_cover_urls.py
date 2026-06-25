"""Resolve retailer import cover URLs for review UI and draft enrichment."""

from __future__ import annotations

_RETAILER_ORIGINS: dict[str, str] = {
    "dcbs": "https://www.dcbservice.com",
    "midtown": "https://www.midtowncomics.com",
    "third_eye": "https://www.thirdeyecomics.com",
    "mycomicshop": "https://www.mycomicshop.com",
}

_REMOTE_IMAGE_KEYS = (
    "remote_shopify_image_url",
    "remote_midtown_image_url",
    "remote_dcbs_image_url",
    "remote_retailer_image_url",
)


def absolutize_retailer_image_url(url: str | None, retailer: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    cleaned = str(url).strip()
    if cleaned.startswith(("http://", "https://", "data:")):
        return cleaned
    if cleaned.startswith("//"):
        return f"https:{cleaned}"
    origin = _RETAILER_ORIGINS.get((retailer or "").casefold())
    if not origin:
        return cleaned
    path = cleaned if cleaned.startswith("/") else f"/{cleaned}"
    return f"{origin}{path}"


def resolve_retailer_cover_url(
    raw_item_json: dict | None,
    *,
    retailer: str | None,
    fallback_image_url: str | None = None,
    fallback_cover_image_url: str | None = None,
) -> str | None:
    raw = raw_item_json if isinstance(raw_item_json, dict) else {}
    diagnostics = raw.get("parse_diagnostics") if isinstance(raw.get("parse_diagnostics"), dict) else {}

    for key in _REMOTE_IMAGE_KEYS:
        candidate = raw.get(key) or diagnostics.get(key)
        if isinstance(candidate, str) and candidate.strip():
            resolved = absolutize_retailer_image_url(candidate.strip(), retailer)
            if resolved:
                return resolved

    for key in ("cover_image_url", "source_image_url", "image_url", "thumbnail_url"):
        candidate = raw.get(key)
        if isinstance(candidate, str) and candidate.strip():
            resolved = absolutize_retailer_image_url(candidate.strip(), retailer)
            if resolved and resolved.startswith(("http://", "https://", "data:")):
                return resolved

    for candidate in (fallback_cover_image_url, fallback_image_url):
        if isinstance(candidate, str) and candidate.strip():
            resolved = absolutize_retailer_image_url(candidate.strip(), retailer)
            if resolved and resolved.startswith(("http://", "https://", "data:")):
                return resolved

    return None
