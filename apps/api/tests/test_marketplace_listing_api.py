from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.services.marketplace_accounts import create_account
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import auth_headers, register_and_login


def test_marketplace_listing_api_routes_are_owner_scoped_and_append_only(client: TestClient) -> None:
    owner_token = register_and_login(client, "listing-api-owner@example.com")
    outsider_token = register_and_login(client, "listing-api-outsider@example.com")

    created = client.post(
        "/api/v1/marketplace-listings",
        headers=auth_headers(owner_token),
        json={
            "listing_title": "API Listing",
            "listing_description": "Canonical API listing",
            "listing_type": "SINGLE_ISSUE",
            "condition_label": "NM",
            "grade_label": "9.6",
            "asking_price": "18.00",
            "currency": "USD",
            "quantity": 1,
            "variants": [
                {
                    "variant_code": "RAW",
                    "variant_name": "Raw Copy",
                    "sku": "API-RAW",
                    "quantity": 1,
                    "price": "18.00",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["data"]["listing"]["id"]
    assert created.json()["data"]["listing"]["status"] == "DRAFT"

    ready = client.post(f"/api/v1/marketplace-listings/{listing_id}/ready-to-publish", headers=auth_headers(owner_token))
    archived = client.post(f"/api/v1/marketplace-listings/{listing_id}/archive", headers=auth_headers(owner_token))
    detail = client.get(f"/api/v1/marketplace-listings/{listing_id}", headers=auth_headers(owner_token))
    denied = client.get(f"/api/v1/marketplace-listings/{listing_id}", headers=auth_headers(outsider_token))

    assert ready.status_code == 200, ready.text
    assert archived.status_code == 200, archived.text
    assert detail.status_code == 200, detail.text
    assert denied.status_code == 404, denied.text
    assert [row["new_status"] for row in detail.json()["data"]["status_history"]] == [
        "DRAFT",
        "READY_TO_PUBLISH",
        "ARCHIVED",
    ]


def test_marketplace_listing_api_prices_images_and_mappings(client: TestClient) -> None:
    token = register_and_login(client, "listing-api-relations@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "listing-api-relations@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "EBAY")).one()
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="eBay API Account",
                account_identifier="ebay-api-account",
                status="ACTIVE",
            ),
        )
        marketplace_id = int(marketplace.id or 0)
        marketplace_account_id = account.id

    created = client.post(
        "/api/v1/marketplace-listings",
        headers=auth_headers(token),
        json={
            "listing_title": "API Relation Listing",
            "listing_description": "Testing related routes",
            "listing_type": "SINGLE_ISSUE",
            "condition_label": "VF",
            "asking_price": "12.00",
            "currency": "USD",
            "quantity": 1,
        },
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["data"]["listing"]["id"]

    price = client.post(
        f"/api/v1/marketplace-listings/{listing_id}/prices",
        headers=auth_headers(token),
        json={"price_type": "ASKING", "amount": "13.50", "currency": "USD"},
    )
    image = client.post(
        f"/api/v1/marketplace-listings/{listing_id}/images",
        headers=auth_headers(token),
        json={"image_url": "https://example.com/canonical-cover.jpg", "image_type": "COVER", "sort_order": 0},
    )
    set_primary = client.post(
        f"/api/v1/marketplace-listings/{listing_id}/images/{image.json()['data']['id']}/primary",
        headers=auth_headers(token),
    )
    mapping = client.post(
        f"/api/v1/marketplace-listings/{listing_id}/mappings",
        headers=auth_headers(token),
        json={
            "marketplace_id": marketplace_id,
            "marketplace_account_id": marketplace_account_id,
            "external_listing_id": None,
            "external_url": None,
            "sync_status": "PENDING",
        },
    )
    prices = client.get(f"/api/v1/marketplace-listings/{listing_id}/prices", headers=auth_headers(token))
    images = client.get(f"/api/v1/marketplace-listings/{listing_id}/images", headers=auth_headers(token))
    mappings = client.get(f"/api/v1/marketplace-listings/{listing_id}/mappings", headers=auth_headers(token))

    assert price.status_code == 201, price.text
    assert image.status_code == 201, image.text
    assert set_primary.status_code == 200, set_primary.text
    assert mapping.status_code == 201, mapping.text
    assert prices.status_code == 200, prices.text
    assert images.status_code == 200, images.text
    assert mappings.status_code == 200, mappings.text
    assert prices.json()["data"]["items"][0]["amount"] == "13.50"
    assert images.json()["data"]["items"][0]["is_primary"] is True
    assert mappings.json()["data"]["items"][0]["marketplace_id"] == marketplace_id
