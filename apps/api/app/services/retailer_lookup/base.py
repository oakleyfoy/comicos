"""Retailer lookup result models and dispatch helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


RETAILER_LOOKUP_SUCCESS_TTL = timedelta(days=7)
RETAILER_LOOKUP_FAILURE_TTL = timedelta(days=1)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_retailer_name(value: str | None) -> str:
    return (value or "").strip().casefold()


def cover_letter_from_text(text: str | None) -> str | None:
    if not text:
        return None
    import re

    normalized = " ".join(text.strip().split())
    patterns = (
        r"\bcover\s*([a-z0-9]{1,2})\b",
        r"\bcvr\s*([a-z0-9]{1,2})\b",
        r"\bvariant\s+cover\s*([a-z0-9]{1,2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


@dataclass(frozen=True)
class RetailerProductCandidate:
    retailer: str
    product_title: str
    product_url: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    publisher: str | None = None
    series_title: str | None = None
    issue_number: str | None = None
    cover_name: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    release_date: str | None = None
    price: str | None = None
    sku: str | None = None
    source_confidence: float | None = None
    raw_score_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetailerLookupResult:
    matched: bool
    possible_match: bool
    retailer: str
    selected_candidate: RetailerProductCandidate | None
    candidates: tuple[RetailerProductCandidate, ...] = ()
    rejected_reason: str | None = None
    query: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def retailer_lookup_is_fresh(
    enrichment: dict[str, Any] | None,
    *,
    force: bool = False,
) -> bool:
    if force or not enrichment:
        return False
    checked_at = enrichment.get("checked_at")
    if not isinstance(checked_at, str) or not checked_at.strip():
        return False
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = _utc_now() - checked.astimezone(timezone.utc)
    matched = bool(enrichment.get("matched"))
    if matched:
        return age <= RETAILER_LOOKUP_SUCCESS_TTL
    return age <= RETAILER_LOOKUP_FAILURE_TTL


def lookup_retailer_product(
    item: dict[str, Any],
    *,
    limit: int = 10,
    force: bool = False,
) -> RetailerLookupResult:
    retailer = normalize_retailer_name(item.get("retailer") or item.get("retailer_source"))
    product_url = str(item.get("retailer_product_url") or "")
    if retailer == "midtown comics" or retailer == "midtown" or "midtowncomics.com" in product_url.casefold():
        from .midtown import lookup_midtown_product

        return lookup_midtown_product(item, limit=limit, force=force)
    return RetailerLookupResult(
        matched=False,
        possible_match=False,
        retailer=retailer or "unknown",
        selected_candidate=None,
        rejected_reason="retailer_not_supported",
        query=None,
        diagnostics={"supported_retailers": ["Midtown Comics"]},
    )
