from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import select

from app.core.config import get_settings
from app.models import EbayCompImportRun, EbayCompRecord, P68MarketPricingProvider, User
from app.services.ebay_oauth import EbayOAuthAccessToken
from app.services.ebay_sold_search_service import build_ebay_sold_search_request
from app.services.market_normalization import deterministic_normalize_title
from test_inventory import auth_headers, register_and_login


def _sample_payload(*, title: str, listing_id: str, price: str) -> dict:
    return {
        "totalEntries": 1,
        "itemSummaries": [
            {
                "itemId": listing_id,
                "title": title,
                "price": {"value": price, "currency": "USD"},
                "shippingOptions": [{"shippingCost": {"value": "5.50", "currency": "USD"}}],
                "endedDate": "2026-06-01T12:34:56.000Z",
                "condition": "CGC 9.8",
                "listingType": "AUCTION",
                "itemWebUrl": "https://example.test/item/123",
                "image": {"imageUrl": "https://example.test/image.jpg"},
                "seller": {"username": "graded-books"},
                "itemLocation": {"country": "US"},
            }
        ],
    }


def test_import_route_persists_records_and_updates_provider_health(
    client: TestClient,
    session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ebay-comp-import@example.com")
    monkeypatch.setenv("EBAY_API_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_API_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EBAY_ENVIRONMENT", "production")
    get_settings.cache_clear()

    search_request = build_ebay_sold_search_request(
        title="Absolute Batman",
        issue_number="1",
        variant="Cover A",
        publisher="DC Comics",
        condition="CGC 9.8",
        limit=25,
    )
    payload = _sample_payload(title="Absolute Batman #1 CGC 9.8", listing_id="v1|123", price="49.99")

    monkeypatch.setattr(
        "app.api.market_pricing_engine_api.fetch_ebay_sold_search_payload",
        lambda **kwargs: (payload, search_request),
    )

    response = client.post(
        "/api/v1/market-pricing/ebay/import",
        headers=auth_headers(token),
        json={
            "title": "Absolute Batman",
            "issue_number": "1",
            "variant": "Cover A",
            "publisher": "DC Comics",
            "condition": "CGC 9.8",
            "limit": 25,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["provider"] == "EBAY"
    assert body["fetched"] == 1
    assert body["inserted"] == 1
    assert body["updated"] == 0
    assert body["duplicates"] == 0
    assert body["error_count"] == 0
    assert body["import_run_id"] > 0

    owner_id = int(session.exec(select(User.id).where(User.email == "ebay-comp-import@example.com")).one())
    comp_row = session.exec(select(EbayCompRecord).where(EbayCompRecord.owner_user_id == owner_id)).one()
    assert comp_row.provider == "EBAY"
    assert comp_row.provider_listing_id == "v1|123"
    assert comp_row.normalized_title == deterministic_normalize_title("Absolute Batman #1 CGC 9.8")
    assert comp_row.sold_price == Decimal("49.99")
    assert comp_row.shipping_price == Decimal("5.50")
    assert comp_row.total_price == Decimal("55.49")
    assert comp_row.raw_payload_json["itemId"] == "v1|123"
    assert comp_row.match_confidence > 0

    import_run = session.exec(select(EbayCompImportRun).where(EbayCompImportRun.owner_user_id == owner_id)).one()
    assert import_run.fetched_count == 1
    assert import_run.inserted_count == 1
    assert import_run.search_criteria_json["title"] == "Absolute Batman"
    assert import_run.search_criteria_json["issue_number"] == "1"

    provider_row = session.exec(
        select(P68MarketPricingProvider).where(
            P68MarketPricingProvider.owner_user_id == owner_id,
            P68MarketPricingProvider.provider_type == "EBAY_SOLD",
        )
    ).one()
    assert provider_row.last_ingest_at is not None
    assert provider_row.metadata_json["import_available"] is True
    assert provider_row.metadata_json["last_error"] is None

    monkeypatch.setattr(
        "app.services.market_pricing_provider_health.acquire_ebay_oauth_access_token",
        lambda **kwargs: EbayOAuthAccessToken(
            access_token="token",
            token_type="Bearer",
            expires_in=7200,
            scope="https://api.ebay.com/oauth/api_scope",
            environment="production",
        ),
    )
    monkeypatch.setattr(
        "app.services.market_pricing_provider_health.probe_ebay_sold_search_availability",
        lambda **kwargs: (True, None),
    )
    health = client.get("/api/v1/market-pricing/providers/health", headers=auth_headers(token))
    assert health.status_code == 200, health.text
    providers = health.json()["data"]["providers"]
    ebay = next(row for row in providers if row["provider_type"] == "EBAY_SOLD")
    assert ebay["health_status"] == "AUTHENTICATED"
    assert ebay["last_ingest_at"] is not None
    assert ebay["metadata_json"]["import_available"] is True
    assert ebay["metadata_json"]["sold_search_available"] is True
