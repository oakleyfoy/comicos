"""P88 marketplace registry and URL helpers (no network)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse, urlunparse

MarketplaceCode = Literal[
    "EBAY",
    "WHATNOT",
    "MYCOMICSHOP",
    "MIDTOWN",
    "THIRD_EYE",
    "HIPCOMIC",
    "ATOMIC_AVENUE",
    "OTHER",
]


@dataclass(frozen=True)
class MarketplaceDefinition:
    code: MarketplaceCode
    display_name: str
    base_domain: str
    marketplace_type: str
    supports_search: bool = False
    supports_listing_lookup: bool = False
    supports_price_tracking: bool = False
    supports_refresh: bool = False
    supports_live_ingestion: bool = False


MARKETPLACE_REGISTRY: dict[MarketplaceCode, MarketplaceDefinition] = {
    "EBAY": MarketplaceDefinition(
        code="EBAY",
        display_name="eBay",
        base_domain="ebay.com",
        marketplace_type="AUCTION",
        supports_search=True,
        supports_listing_lookup=True,
        supports_price_tracking=True,
        supports_refresh=True,
        supports_live_ingestion=True,
    ),
    "WHATNOT": MarketplaceDefinition(
        code="WHATNOT",
        display_name="Whatnot",
        base_domain="whatnot.com",
        marketplace_type="LIVE",
    ),
    "MYCOMICSHOP": MarketplaceDefinition(
        code="MYCOMICSHOP",
        display_name="MyComicShop",
        base_domain="mycomicshop.com",
        marketplace_type="RETAIL",
    ),
    "MIDTOWN": MarketplaceDefinition(
        code="MIDTOWN",
        display_name="Midtown Comics",
        base_domain="midtowncomics.com",
        marketplace_type="RETAIL",
    ),
    "THIRD_EYE": MarketplaceDefinition(
        code="THIRD_EYE",
        display_name="Third Eye Comics",
        base_domain="thirdeyecomics.com",
        marketplace_type="RETAIL",
    ),
    "HIPCOMIC": MarketplaceDefinition(
        code="HIPCOMIC",
        display_name="HipComic",
        base_domain="hipcomic.com",
        marketplace_type="RETAIL",
    ),
    "ATOMIC_AVENUE": MarketplaceDefinition(
        code="ATOMIC_AVENUE",
        display_name="Atomic Avenue",
        base_domain="atomicavenue.com",
        marketplace_type="RETAIL",
    ),
    "OTHER": MarketplaceDefinition(
        code="OTHER",
        display_name="Other Marketplace",
        base_domain="",
        marketplace_type="UNKNOWN",
    ),
}


def list_supported_marketplace_codes(*, include_other: bool = False) -> list[MarketplaceCode]:
    codes: list[MarketplaceCode] = [
        "EBAY",
        "MYCOMICSHOP",
        "MIDTOWN",
        "THIRD_EYE",
        "HIPCOMIC",
        "ATOMIC_AVENUE",
    ]
    if include_other:
        codes.append("OTHER")
    return codes


def marketplace_definition(code: str) -> MarketplaceDefinition:
    key = str(code).strip().upper()
    if key in MARKETPLACE_REGISTRY:
        return MARKETPLACE_REGISTRY[key]  # type: ignore[index]
    return MARKETPLACE_REGISTRY["OTHER"]

_HOST_TO_CODE: list[tuple[str, MarketplaceCode]] = [
    ("ebay.com", "EBAY"),
    ("whatnot.com", "WHATNOT"),
    ("mycomicshop.com", "MYCOMICSHOP"),
    ("midtowncomics.com", "MIDTOWN"),
    ("thirdeyecomics.com", "THIRD_EYE"),
    ("hipcomic.com", "HIPCOMIC"),
    ("atomicavenue.com", "ATOMIC_AVENUE"),
]


def _normalize_host(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def detect_marketplace_from_url(url: str) -> MarketplaceCode:
    parsed = urlparse(url.strip())
    host = _normalize_host(parsed.hostname or "")
    if not host:
        return "OTHER"
    for domain, code in _HOST_TO_CODE:
        if host == domain or host.endswith(f".{domain}"):
            return code
    return "OTHER"


def normalize_marketplace_url(url: str, *, max_length: int = 2048) -> str:
    raw = url.strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL must include scheme and host.")
    scheme = parsed.scheme.lower()
    if scheme != "https":
        raise ValueError("Only https URLs are supported.")
    host = _normalize_host(parsed.hostname or "")
    netloc = host
    if parsed.port and parsed.port not in (443,):
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    if len(normalized) > max_length:
        raise ValueError(f"URL exceeds maximum length of {max_length} characters.")
    return normalized


def marketplace_display_name(code: str | MarketplaceCode) -> str:
    key = str(code).strip().upper()
    if key in MARKETPLACE_REGISTRY:
        return MARKETPLACE_REGISTRY[key].display_name  # type: ignore[index]
    return MARKETPLACE_REGISTRY["OTHER"].display_name


def extract_external_listing_id(url: str, marketplace: MarketplaceCode) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    if marketplace == "EBAY":
        parts = [p for p in path.split("/") if p]
        for idx, part in enumerate(parts):
            if part.lower() == "itm" and idx + 1 < len(parts):
                return parts[idx + 1][:128]
        return ""
    slug = path.strip("/").split("/")[-1] if path.strip("/") else ""
    return slug[:128]
