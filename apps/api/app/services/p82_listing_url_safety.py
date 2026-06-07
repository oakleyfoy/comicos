"""No-network rules for P82 marketplace listing URL safety (read-only classification)."""

from __future__ import annotations

import re
from typing import Literal

UrlBucket = Literal[
    "missing_url",
    "simulated_external_id",
    "fake_ebay_generated",
    "ebay_non_numeric",
    "likely_safe_ebay",
    "non_ebay_https",
    "other_unsafe",
]

_SIMULATED_PREFIXES = ("SIM-", "SIM-EBAY", "P82-TEST", "CERT-")
_EBAY_NUMERIC = re.compile(r"^https://(www\.)?ebay\.com/itm/(\d+)(/)?(\?.*)?$", re.IGNORECASE)


def is_simulated_external_listing_id(external_listing_id: str | None) -> bool:
    raw = (external_listing_id or "").strip().upper()
    if not raw:
        return False
    return raw.startswith(_SIMULATED_PREFIXES)


def url_contains_simulated_token(listing_url: str | None) -> bool:
    lower = (listing_url or "").lower()
    return (
        "/itm/sim-" in lower
        or "sim-ebay" in lower
        or "p82-test" in lower
        or "cert-" in lower
    )


def is_safe_marketplace_listing_url(*, listing_url: str | None, external_listing_id: str | None) -> bool:
    url = (listing_url or "").strip()
    if not url:
        return False
    if is_simulated_external_listing_id(external_listing_id):
        return False
    if url_contains_simulated_token(url):
        return False
    if _EBAY_NUMERIC.match(url):
        return True
    if "ebay.com/itm/" in url.lower():
        return False
    if url.startswith("https://"):
        return True
    return False


def classify_p82_listing_url(*, listing_url: str | None, external_listing_id: str | None) -> UrlBucket:
    url = (listing_url or "").strip()
    if not url:
        return "missing_url"
    if is_simulated_external_listing_id(external_listing_id):
        return "simulated_external_id"
    if url_contains_simulated_token(url):
        return "fake_ebay_generated"
    if _EBAY_NUMERIC.match(url):
        return "likely_safe_ebay"
    if "ebay.com/itm/" in url.lower():
        return "ebay_non_numeric"
    if url.startswith("https://"):
        return "non_ebay_https"
    return "other_unsafe"
