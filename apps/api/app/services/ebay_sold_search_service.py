from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.ebay_sold_search import EbaySoldSearchPreviewItem, EbaySoldSearchPreviewResponse
from app.services.ebay_oauth import (
    EBAY_OAUTH_BASE_URLS,
    EbayOAuthAuthenticationError,
    EbayOAuthConfigurationError,
    acquire_ebay_oauth_access_token,
)

EBAY_SOLD_SEARCH_PATH = "/buy/browse/v1/item_summary/search"
EBAY_SOLD_SEARCH_MAX_LIMIT = 100
EBAY_SOLD_SEARCH_TIMEOUT_SECONDS = 20.0
EBAY_SOLD_SEARCH_DEFAULT_PROBE_QUERY = "Batman comic"


class EbaySoldSearchError(Exception):
    pass


class EbaySoldSearchConfigurationError(EbaySoldSearchError):
    pass


class EbaySoldSearchApiError(EbaySoldSearchError):
    pass


@dataclass(frozen=True)
class EbaySoldSearchRequest:
    query: str
    params: dict[str, Any]


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


def _normalize_condition_hint(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    mapped = normalized.lower()
    if mapped in {"raw", "raw book", "raw comic"}:
        return "raw"
    if mapped in {"cgc", "slab", "graded", "slabbed"}:
        return "CGC slab graded"
    return normalized


def _compact_terms(terms: list[str]) -> str:
    cleaned = [term.strip() for term in terms if term and term.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for term in cleaned:
        lower = term.lower()
        if lower in seen:
            continue
        seen.add(lower)
        ordered.append(term)
    return " ".join(ordered)


def build_ebay_sold_search_request(
    *,
    q: str | None = None,
    title: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    variant: str | None = None,
    publisher: str | None = None,
    upc: str | None = None,
    condition: str | None = None,
    limit: int = 25,
) -> EbaySoldSearchRequest:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > EBAY_SOLD_SEARCH_MAX_LIMIT:
        raise ValueError("limit must not exceed 100")

    terms: list[str] = []
    if q and q.strip():
        terms.append(q.strip())
    base_title = (title or series or "").strip()
    if base_title:
        terms.append(base_title)
    if issue_number and issue_number.strip():
        terms.append(issue_number.strip())
    if variant and variant.strip():
        terms.append(variant.strip())
    if publisher and publisher.strip():
        terms.append(publisher.strip())
    if upc and upc.strip():
        terms.append(upc.strip())

    condition_hint = _normalize_condition_hint(condition)
    if condition_hint:
        terms.append(condition_hint)

    query = _compact_terms(terms)
    if not query:
        raise ValueError("At least one search term is required.")

    params: dict[str, Any] = {
        "q": query,
        "limit": limit,
        "fieldgroups": "MINIMAL",
        "filter": "soldItems:true",
    }

    return EbaySoldSearchRequest(query=query, params=params)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            normalized = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _list_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("itemSummaries", "item_summary", "items", "searchResult"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]
        if isinstance(candidate, dict):
            nested = candidate.get("itemSummaries") or candidate.get("item") or candidate.get("itemSummary")
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]
    return []


def extract_ebay_sold_search_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _list_from_payload(payload)


def _extract_total_items(payload: dict[str, Any]) -> int:
    candidates = [
        payload.get("total"),
        payload.get("totalEntries"),
        payload.get("totalEntriesCount"),
    ]
    pagination = payload.get("paginationOutput")
    if isinstance(pagination, dict):
        candidates.append(pagination.get("totalEntries"))
    for candidate in candidates:
        try:
            if candidate is not None:
                return max(0, int(candidate))
        except (TypeError, ValueError):
            continue
    return len(_list_from_payload(payload))


def _extract_price(item: dict[str, Any]) -> tuple[float | None, str]:
    price = item.get("price")
    if isinstance(price, dict):
        sold_price = _as_float(price.get("value"))
        currency = str(price.get("currency") or price.get("currencyCode") or "USD")
        return sold_price, currency
    if isinstance(price, (int, float, str)):
        sold_price = _as_float(price)
        currency = str(item.get("currency") or item.get("currencyCode") or "USD")
        return sold_price, currency
    return None, str(item.get("currency") or item.get("currencyCode") or "USD")


def _extract_shipping_price(item: dict[str, Any]) -> float | None:
    shipping = item.get("shippingOptions")
    if isinstance(shipping, list) and shipping:
        first = shipping[0]
        if isinstance(first, dict):
            ship_cost = first.get("shippingCost")
            if isinstance(ship_cost, dict):
                return _as_float(ship_cost.get("value"))
    if isinstance(item.get("shippingCost"), dict):
        return _as_float(item["shippingCost"].get("value"))
    return _as_float(item.get("shippingCost"))


def _build_match_notes(item: dict[str, Any], request: EbaySoldSearchRequest) -> tuple[float, list[str]]:
    notes: list[str] = []
    confidence = 0.35
    title = str(item.get("title") or "")
    query = request.query.lower()

    if request.params.get("upc"):
        notes.append("searched by UPC")
        confidence = 0.95

    if request.params.get("q") and title and query.split()[0] in title.lower():
        notes.append("title matched search text")
        confidence = max(confidence, 0.75)

    if request.params.get("q") and request.params.get("q") == item.get("title"):
        notes.append("exact title match")
        confidence = 0.95

    if "cgc" in query or "slab" in query or "graded" in query:
        notes.append("graded/slab hint")
        confidence = min(1.0, confidence + 0.05)

    if not notes:
        notes.append("broad marketplace preview match")
    return round(min(confidence, 1.0), 2), notes


def _normalize_item(item: dict[str, Any], request: EbaySoldSearchRequest) -> EbaySoldSearchPreviewItem:
    provider_listing_id = str(
        item.get("itemId")
        or item.get("legacyItemId")
        or item.get("listingId")
        or item.get("itemWebUrl")
        or item.get("title")
        or "unknown"
    )
    sold_price, currency = _extract_price(item)
    shipping_price = _extract_shipping_price(item)
    total_price = _as_float(item.get("totalPrice"))
    if total_price is None and sold_price is not None and shipping_price is not None:
        total_price = round(sold_price + shipping_price, 2)
    if sold_price is None:
        sold_price = total_price or 0.0

    condition = item.get("condition") or item.get("conditionDisplayName")
    listing_type = item.get("listingType") or item.get("buyingOptions")
    item_url = item.get("itemWebUrl") or item.get("url")
    image_url = None
    image = item.get("image")
    if isinstance(image, dict):
        image_url = image.get("imageUrl") or image.get("url")
    seller_location = None
    seller = item.get("seller")
    if isinstance(seller, dict):
        seller_location = seller.get("username") or seller.get("feedbackScore")
    location = item.get("itemLocation")
    if isinstance(location, dict):
        seller_location = seller_location or location.get("country") or location.get("postalCode")

    sold_at = _parse_datetime(item.get("soldDate") or item.get("saleDate") or item.get("endedDate"))
    ended_at = _parse_datetime(item.get("endedDate") or item.get("endDate") or item.get("listingEndDate"))

    raw_match_confidence, notes = _build_match_notes(item, request)

    return EbaySoldSearchPreviewItem(
        provider="EBAY",
        provider_listing_id=provider_listing_id,
        title=str(item.get("title") or "Untitled"),
        sold_price=float(sold_price),
        currency=currency,
        shipping_price=shipping_price,
        total_price=total_price,
        sold_at=sold_at,
        ended_at=ended_at,
        condition=str(condition) if condition is not None else None,
        listing_type=str(listing_type) if listing_type is not None else None,
        item_url=str(item_url) if item_url is not None else None,
        image_url=str(image_url) if image_url is not None else None,
        seller_location=str(seller_location) if seller_location is not None else None,
        raw_match_confidence=raw_match_confidence,
        match_notes=notes,
    )


def normalize_ebay_sold_search_payload(
    payload: dict[str, Any],
    request: EbaySoldSearchRequest,
) -> list[EbaySoldSearchPreviewItem]:
    return [_normalize_item(item, request) for item in _list_from_payload(payload)]


def _http_client(*, settings: Settings) -> httpx.Client:
    environment = settings.ebay_environment.strip().lower()
    if environment not in EBAY_OAUTH_BASE_URLS:
        raise EbaySoldSearchConfigurationError(f"Unsupported EBAY_ENVIRONMENT value: {environment}")
    return httpx.Client(
        base_url=EBAY_OAUTH_BASE_URLS[environment],
        timeout=EBAY_SOLD_SEARCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def _perform_search(
    *,
    settings: Settings,
    access_token: str,
    request: EbaySoldSearchRequest,
    client: httpx.Client | None = None,
) -> tuple[dict[str, Any], str | None]:
    owns_client = client is None
    http_client = client or _http_client(settings=settings)
    last_error: str | None = None
    try:
        response = http_client.get(
            EBAY_SOLD_SEARCH_PATH,
            params=request.params,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise EbaySoldSearchApiError("eBay sold search returned a non-object payload.")
        return payload, None
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        last_error = f"HTTP {exc.response.status_code}" + (f": {detail}" if detail else "")
        raise EbaySoldSearchApiError(f"eBay sold search failed with {last_error}") from exc
    except httpx.HTTPError as exc:
        last_error = str(exc)
        raise EbaySoldSearchApiError("Unable to reach eBay sold search endpoint.") from exc
    finally:
        if owns_client:
            http_client.close()


def search_ebay_sold_listings(
    *,
    q: str | None = None,
    title: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    variant: str | None = None,
    publisher: str | None = None,
    upc: str | None = None,
    condition: str | None = None,
    limit: int = 25,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> EbaySoldSearchPreviewResponse:
    resolved = _resolve_settings(settings)
    payload, request = fetch_ebay_sold_search_payload(
        q=q,
        title=title,
        series=series,
        issue_number=issue_number,
        variant=variant,
        publisher=publisher,
        upc=upc,
        condition=condition,
        limit=limit,
        settings=resolved,
        client=client,
    )
    items = normalize_ebay_sold_search_payload(payload, request)
    return EbaySoldSearchPreviewResponse(
        query=request.query,
        sold_search_available=True,
        total_items=_extract_total_items(payload),
        limit=limit,
        items=items,
    )


def fetch_ebay_sold_search_payload(
    *,
    q: str | None = None,
    title: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    variant: str | None = None,
    publisher: str | None = None,
    upc: str | None = None,
    condition: str | None = None,
    limit: int = 25,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> tuple[dict[str, Any], EbaySoldSearchRequest]:
    resolved = _resolve_settings(settings)
    request = build_ebay_sold_search_request(
        q=q,
        title=title,
        series=series,
        issue_number=issue_number,
        variant=variant,
        publisher=publisher,
        upc=upc,
        condition=condition,
        limit=limit,
    )
    token = acquire_ebay_oauth_access_token(settings=resolved)
    payload, _ = _perform_search(settings=resolved, access_token=token.access_token, request=request, client=client)
    return payload, request


def probe_ebay_sold_search_availability(
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> tuple[bool, str | None]:
    resolved = _resolve_settings(settings)
    try:
        request = build_ebay_sold_search_request(q=EBAY_SOLD_SEARCH_DEFAULT_PROBE_QUERY, limit=1)
        token = acquire_ebay_oauth_access_token(settings=resolved)
        _perform_search(settings=resolved, access_token=token.access_token, request=request, client=client)
        return True, None
    except (EbayOAuthConfigurationError, EbayOAuthAuthenticationError, EbaySoldSearchError) as exc:
        return False, str(exc)
