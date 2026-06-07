"""P88-02 live eBay Browse API search (active listings, no scraping)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.ebay_oauth import (
    EBAY_OAUTH_BASE_URLS,
    EbayOAuthConfigurationError,
    acquire_ebay_oauth_access_token,
)
from app.services.ebay_sold_search_service import (
    EBAY_SOLD_SEARCH_MAX_LIMIT,
    EBAY_SOLD_SEARCH_TIMEOUT_SECONDS,
    _as_float,
    _compact_terms,
    _list_from_payload,
    _parse_datetime,
)

EBAY_BROWSE_SEARCH_PATH = "/buy/browse/v1/item_summary/search"
EBAY_BROWSE_ITEM_PATH = "/buy/browse/v1/item"
_MAX_RETRIES = 3
_RETRY_STATUS = {429, 500, 502, 503, 504}
_MIN_REQUEST_INTERVAL_SECONDS = 0.25
_rate_lock = Lock()
_last_request_at = 0.0


class EbayLiveSearchError(Exception):
    pass


class EbayLiveSearchConfigurationError(EbayLiveSearchError):
    pass


class EbayLiveSearchApiError(EbayLiveSearchError):
    pass


@dataclass(frozen=True)
class NormalizedMarketplaceListing:
    marketplace: str
    item_id: str
    title: str
    url: str
    price: float
    shipping: float
    condition: str
    seller: str
    listing_type: str
    end_time: datetime | None
    image_url: str


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


def _throttle() -> None:
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        wait = _MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _canonical_item_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if "|" in text:
        parts = text.split("|")
        if len(parts) >= 2 and parts[1].strip().isdigit():
            return parts[1].strip()
    match = re.search(r"\d{6,}", text)
    if match:
        return match.group(0)
    return text


def _extract_price(item: dict[str, Any]) -> float:
    price = item.get("price")
    if isinstance(price, dict):
        return float(_as_float(price.get("value")) or 0.0)
    return float(_as_float(price) or 0.0)


def _extract_shipping(item: dict[str, Any]) -> float:
    shipping = item.get("shippingOptions")
    if isinstance(shipping, list) and shipping:
        first = shipping[0]
        if isinstance(first, dict):
            ship_cost = first.get("shippingCost")
            if isinstance(ship_cost, dict):
                return float(_as_float(ship_cost.get("value")) or 0.0)
    if isinstance(item.get("shippingCost"), dict):
        return float(_as_float(item["shippingCost"].get("value")) or 0.0)
    return float(_as_float(item.get("shippingCost")) or 0.0)


def _normalize_browse_item(item: dict[str, Any]) -> NormalizedMarketplaceListing | None:
    raw_id = str(item.get("itemId") or item.get("legacyItemId") or item.get("listingId") or "")
    item_id = _canonical_item_id(raw_id)
    if not item_id:
        return None
    item_url = str(item.get("itemWebUrl") or item.get("url") or "")
    if not item_url and item_id.isdigit():
        item_url = f"https://www.ebay.com/itm/{item_id}"
    if not item_url.lower().startswith("https://"):
        return None

    condition = item.get("condition") or item.get("conditionDisplayName") or ""
    listing_type = item.get("listingType") or item.get("buyingOptions") or ""
    if isinstance(listing_type, list):
        listing_type = ",".join(str(x) for x in listing_type)

    seller_name = ""
    seller = item.get("seller")
    if isinstance(seller, dict):
        seller_name = str(seller.get("username") or seller.get("sellerAccountType") or "")

    image_url = ""
    image = item.get("image")
    if isinstance(image, dict):
        image_url = str(image.get("imageUrl") or image.get("url") or "")

    end_time = _parse_datetime(
        item.get("itemEndDate") or item.get("endDate") or item.get("listingEndDate") or item.get("endedDate")
    )

    return NormalizedMarketplaceListing(
        marketplace="EBAY",
        item_id=item_id,
        title=str(item.get("title") or "Untitled"),
        url=item_url,
        price=_extract_price(item),
        shipping=_extract_shipping(item),
        condition=str(condition),
        seller=seller_name,
        listing_type=str(listing_type),
        end_time=end_time,
        image_url=image_url,
    )


def build_live_search_params(
    *,
    title: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
    limit: int = 25,
) -> tuple[str, dict[str, Any]]:
    if limit < 1 or limit > EBAY_SOLD_SEARCH_MAX_LIMIT:
        raise ValueError("limit must be between 1 and 100")
    terms: list[str] = []
    base = (title or series or "").strip()
    if base:
        terms.append(base)
    if issue_number and issue_number.strip():
        terms.append(issue_number.strip())
    if publisher and publisher.strip():
        terms.append(publisher.strip())
    query = _compact_terms(terms)
    if not query:
        raise ValueError("At least one search term is required.")
    params: dict[str, Any] = {
        "q": query,
        "limit": limit,
        "fieldgroups": "EXTENDED",
    }
    return query, params


def _http_client(*, settings: Settings) -> httpx.Client:
    environment = settings.ebay_environment.strip().lower()
    if environment not in EBAY_OAUTH_BASE_URLS:
        raise EbayLiveSearchConfigurationError(f"Unsupported EBAY_ENVIRONMENT value: {environment}")
    return httpx.Client(
        base_url=EBAY_OAUTH_BASE_URLS[environment],
        timeout=EBAY_SOLD_SEARCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def _get_with_retry(
    *,
    settings: Settings,
    access_token: str,
    path: str,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    http_client = client or _http_client(settings=settings)
    last_exc: Exception | None = None
    try:
        for attempt in range(_MAX_RETRIES):
            _throttle()
            try:
                response = http_client.get(
                    path,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    },
                )
                if response.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise EbayLiveSearchApiError("eBay Browse API returned a non-object payload.")
                return payload
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                detail = exc.response.text.strip()
                raise EbayLiveSearchApiError(
                    f"eBay Browse API failed HTTP {exc.response.status_code}"
                    + (f": {detail}" if detail else "")
                ) from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise EbayLiveSearchApiError("Unable to reach eBay Browse API.") from exc
        raise EbayLiveSearchApiError(str(last_exc or "eBay Browse API failed."))
    finally:
        if owns_client:
            http_client.close()


def search_comics(
    *,
    title: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
    limit: int = 25,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> list[NormalizedMarketplaceListing]:
    """Search active eBay listings for comic-related items."""
    resolved = _resolve_settings(settings)
    try:
        token = acquire_ebay_oauth_access_token(settings=resolved)
    except EbayOAuthConfigurationError as exc:
        raise EbayLiveSearchConfigurationError(str(exc)) from exc

    _, params = build_live_search_params(
        title=title,
        series=series,
        issue_number=issue_number,
        publisher=publisher,
        limit=limit,
    )
    payload = _get_with_retry(
        settings=resolved,
        access_token=token.access_token,
        path=EBAY_BROWSE_SEARCH_PATH,
        params=params,
        client=client,
    )
    results: list[NormalizedMarketplaceListing] = []
    seen: set[str] = set()
    for item in _list_from_payload(payload):
        normalized = _normalize_browse_item(item)
        if normalized is None or normalized.item_id in seen:
            continue
        seen.add(normalized.item_id)
        results.append(normalized)
    return results


def fetch_item_by_id(
    *,
    item_id: str,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> NormalizedMarketplaceListing | None:
    """Refresh a single listing via Browse item endpoint."""
    resolved = _resolve_settings(settings)
    canonical = _canonical_item_id(item_id)
    if not canonical:
        return None
    token = acquire_ebay_oauth_access_token(settings=resolved)
    path = f"{EBAY_BROWSE_ITEM_PATH}/v1|{canonical}|0"
    try:
        payload = _get_with_retry(
            settings=resolved,
            access_token=token.access_token,
            path=path,
            client=client,
        )
    except EbayLiveSearchApiError:
        return None
    return _normalize_browse_item(payload if isinstance(payload, dict) else {})
