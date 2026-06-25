"""Resolve retailer import cover URLs for review UI and draft enrichment."""

from __future__ import annotations

import re

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

_DCBS_FILES_PATH_RE = re.compile(
    r"(?:^|[/\\])files[/\\]([A-Za-z0-9]+)\.(?:jpg|jpeg|png|webp)\b",
    flags=re.IGNORECASE,
)
_DCBS_PRODUCT_CODE_RE = re.compile(r"^[A-Za-z0-9]+$")
_DCBS_CODE_IN_TEXT_RE = re.compile(r"\b([A-Z]{3}\d{5,7})\b")


def _dcbs_product_code_from_raw(raw: dict) -> str | None:
    for key in ("retailer_item_id", "product_code", "sku"):
        candidate = raw.get(key)
        if isinstance(candidate, str) and candidate.strip():
            code = candidate.strip().upper()
            if _DCBS_PRODUCT_CODE_RE.fullmatch(code):
                return code
    cover_name = raw.get("cover_name")
    if isinstance(cover_name, str):
        match = _DCBS_CODE_IN_TEXT_RE.search(cover_name.upper())
        if match:
            return match.group(1)
    return None


def dcbs_product_code_cover_url(product_code: str | None, *, size: str = "small") -> str | None:
    if not product_code or not str(product_code).strip():
        return None
    code = str(product_code).strip().upper()
    if not _DCBS_PRODUCT_CODE_RE.fullmatch(code):
        return None
    return f"https://media.dcbservice.com/{size}/{code}.jpg"


def remap_dcbs_cover_url(url: str | None, *, product_code: str | None = None) -> str | None:
    """Map legacy /files/{code}.jpg paths to DCBS media CDN URLs."""
    if not url or not str(url).strip():
        return None
    cleaned = str(url).strip()
    match = _DCBS_FILES_PATH_RE.search(cleaned.replace("\\", "/"))
    code = product_code or (match.group(1) if match else None)
    media = dcbs_product_code_cover_url(code)
    if media and (
        match is not None
        or "dcbservice.com/files/" in cleaned.casefold()
        or cleaned.casefold().startswith("/files/")
    ):
        return media
    return cleaned


def absolutize_retailer_image_url(url: str | None, retailer: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    cleaned = str(url).strip()
    if cleaned.startswith(("http://", "https://", "data:")):
        if (retailer or "").casefold() == "dcbs":
            return remap_dcbs_cover_url(cleaned) or cleaned
        return cleaned
    if cleaned.startswith("//"):
        absolute = f"https:{cleaned}"
        if (retailer or "").casefold() == "dcbs":
            return remap_dcbs_cover_url(absolute) or absolute
        return absolute
    origin = _RETAILER_ORIGINS.get((retailer or "").casefold())
    if not origin:
        return cleaned
    path = cleaned if cleaned.startswith("/") else f"/{cleaned}"
    absolute = f"{origin}{path}"
    if (retailer or "").casefold() == "dcbs":
        return remap_dcbs_cover_url(absolute, product_code=None) or absolute
    return absolute


def resolve_retailer_cover_url(
    raw_item_json: dict | None,
    *,
    retailer: str | None,
    fallback_image_url: str | None = None,
    fallback_cover_image_url: str | None = None,
    fallback_retailer_item_id: str | None = None,
    fallback_cover_name: str | None = None,
) -> str | None:
    raw = raw_item_json if isinstance(raw_item_json, dict) else {}
    diagnostics = raw.get("parse_diagnostics") if isinstance(raw.get("parse_diagnostics"), dict) else {}
    merged_for_code = dict(raw)
    if fallback_retailer_item_id and not merged_for_code.get("retailer_item_id"):
        merged_for_code["retailer_item_id"] = fallback_retailer_item_id
    if fallback_cover_name and not merged_for_code.get("cover_name"):
        merged_for_code["cover_name"] = fallback_cover_name
    product_code = _dcbs_product_code_from_raw(merged_for_code)
    is_dcbs = (retailer or "").casefold() == "dcbs"

    for key in _REMOTE_IMAGE_KEYS:
        candidate = raw.get(key) or diagnostics.get(key)
        if isinstance(candidate, str) and candidate.strip():
            resolved = absolutize_retailer_image_url(candidate.strip(), retailer)
            if resolved:
                if is_dcbs and product_code:
                    media = dcbs_product_code_cover_url(product_code)
                    if media and "dcbservice.com/files/" in resolved.casefold():
                        return media
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

    if is_dcbs:
        media = dcbs_product_code_cover_url(product_code)
        if media:
            return media

    return None
