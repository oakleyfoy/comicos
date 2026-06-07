"""P88 marketplace URL validation (no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.marketplace.marketplace_registry import (
    MARKETPLACE_REGISTRY,
    MarketplaceCode,
    detect_marketplace_from_url,
    normalize_marketplace_url,
)

MAX_URL_LENGTH = 2048

ALLOWED_HOST_SUFFIXES = (
    "ebay.com",
    "whatnot.com",
    "mycomicshop.com",
    "midtowncomics.com",
    "thirdeyecomics.com",
    "hipcomic.com",
    "atomicavenue.com",
)


@dataclass(frozen=True)
class MarketplaceUrlValidationResult:
    is_valid: bool
    marketplace: MarketplaceCode | None
    normalized_url: str | None
    error_message: str | None


def _host_allowed(host: str) -> bool:
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in ALLOWED_HOST_SUFFIXES)


def validate_marketplace_url(url: str) -> MarketplaceUrlValidationResult:
    raw = (url or "").strip()
    if not raw:
        return MarketplaceUrlValidationResult(False, None, None, "URL is required.")
    if len(raw) > MAX_URL_LENGTH:
        return MarketplaceUrlValidationResult(False, None, None, f"URL exceeds {MAX_URL_LENGTH} characters.")
    if not raw.lower().startswith("https://"):
        return MarketplaceUrlValidationResult(False, None, None, "Only https URLs are supported.")

    try:
        normalized = normalize_marketplace_url(raw, max_length=MAX_URL_LENGTH)
    except ValueError as exc:
        return MarketplaceUrlValidationResult(False, None, None, str(exc))

    from urllib.parse import urlparse

    host = urlparse(normalized).hostname or ""
    if not _host_allowed(host):
        return MarketplaceUrlValidationResult(
            False,
            None,
            None,
            "URL host is not a supported marketplace domain.",
        )

    marketplace = detect_marketplace_from_url(normalized)
    if marketplace not in MARKETPLACE_REGISTRY:
        marketplace = "OTHER"

    return MarketplaceUrlValidationResult(True, marketplace, normalized, None)
