from __future__ import annotations

from typing import Any

from app.services.external_catalog.importance_signals import parse_ratio_from_text
from app.services.external_catalog.normalization import parse_price


def normalize_variant_row(raw: dict[str, Any]) -> dict[str, Any]:
    variant_name = (raw.get("variant_name") or raw.get("name") or "").strip() or None
    cover_label = (raw.get("cover_label") or raw.get("cover") or "").strip() or None
    artist = (raw.get("artist") or raw.get("variant_artist") or raw.get("cover_artist") or "").strip() or None
    ratio_value = raw.get("ratio_value")
    if ratio_value is not None:
        try:
            ratio_int = int(ratio_value)
        except (TypeError, ValueError):
            ratio_int = parse_ratio_from_text(str(variant_name or ""))
    else:
        ratio_int = parse_ratio_from_text(str(variant_name or ""))
    detail_url = (
        raw.get("variant_detail_url")
        or raw.get("source_url")
        or raw.get("url")
        or None
    )
    if detail_url is not None:
        detail_url = str(detail_url).strip() or None
    image_url = raw.get("image_url") or raw.get("cover_image_url")
    if image_url is not None:
        image_url = str(image_url).strip() or None
    return {
        "cover_label": cover_label,
        "variant_name": variant_name,
        "artist": artist,
        "ratio_value": ratio_int,
        "price": parse_price(raw.get("price")),
        "image_url": image_url,
        "source_url": detail_url,
        "variant_detail_url": detail_url,
    }


def normalize_variants_from_raw(raw: dict[str, Any]) -> list[dict[str, Any]]:
    variants = raw.get("variants")
    if not isinstance(variants, list):
        return []
    return [normalize_variant_row(v) for v in variants if isinstance(v, dict)]
