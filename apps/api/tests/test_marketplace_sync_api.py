from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingMappingCreate
from app.services.marketplace_accounts import create_account
from app.services.marketplace_listing_mappings import create_mapping
from app.services.marketplace_listings import create_listing
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import auth_headers, register_and_login


def _setup_sync_owner(client: TestClient, email: str) -> tuple[int, int]:
    token = register_and_login(client, email)
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == email)).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "SHOPIFY")).one()
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Sync API Account",
                account_identifier=f"sync-api-{owner.id}",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Sync API Listing",
                listing_description="Sync API listing description",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="20.00",
                currency="USD",
                quantity=2,
            ),
        )
        create_mapping(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingMappingCreate(
                marketplace_id=int(marketplace.id or 0),
                marketplace_account_id=account.id,
                external_listing_id="shopify-sync-api-1",
                external_url="https://example.com/listings/shopify-sync-api-1",
                sync_status="mapped",
            ),
        )
        return token, listing.listing.id


def test_marketplace_sync_api_routes_and_owner_scoping(client: TestClient) -> None:
    owner_token, listing_id = _setup_sync_owner(client, "sync-api-owner@example.com")
    outsider_token = register_and_login(client, "sync-api-outsider@example.com")

    reservation = client.post(
        "/api/v1/marketplace-sync/reservations",
        headers=auth_headers(owner_token),
        json={
            "listing_id": listing_id,
            "inventory_copy_id": None,
            "reservation_type": "cart_hold",
            "quantity_reserved": 1,
            "source": "api_hold",
            "expires_at": None,
        },
    )
    assert reservation.status_code == 201, reservation.text
    reservation_id = reservation.json()["data"]["id"]

    reservations = client.get("/api/v1/marketplace-sync/reservations?limit=20&offset=0", headers=auth_headers(owner_token))
    availability = client.get(f"/api/v1/marketplace-sync/availability/{listing_id}", headers=auth_headers(owner_token))
    order = client.post(
        "/api/v1/marketplace-sync/orders",
        headers=auth_headers(owner_token),
        json={
            "marketplace_id": None,
            "marketplace_account_id": None,
            "external_order_id": "ext-order-1",
            "buyer_name": "API Buyer",
            "buyer_email": "api-buyer@example.com",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "currency": "USD",
            "items": [
                {
                    "listing_id": listing_id,
                    "inventory_copy_id": None,
                    "external_item_id": None,
                    "title": "Sync API Item",
                    "quantity": 1,
                    "unit_price": "20.00",
                }
            ],
        },
    )
    assert reservations.status_code == 200, reservations.text
    assert availability.status_code == 200, availability.text
    assert order.status_code == 201, order.text
    order_id = order.json()["data"]["order"]["id"]

    order_list = client.get("/api/v1/marketplace-sync/orders?limit=20&offset=0", headers=auth_headers(owner_token))
    order_detail = client.get(f"/api/v1/marketplace-sync/orders/{order_id}", headers=auth_headers(owner_token))
    paid = client.post(f"/api/v1/marketplace-sync/orders/{order_id}/paid", headers=auth_headers(owner_token))
    fulfilled = client.post(f"/api/v1/marketplace-sync/orders/{order_id}/fulfilled", headers=auth_headers(owner_token))
    release = client.post(
        f"/api/v1/marketplace-sync/reservations/{reservation_id}/release",
        headers=auth_headers(owner_token),
    )
    plan = client.post(
        "/api/v1/marketplace-sync/plans/generate",
        headers=auth_headers(owner_token),
        json={"listing_ids": [listing_id], "marketplace_ids": []},
    )
    assert order_list.status_code == 200, order_list.text
    assert order_detail.status_code == 200, order_detail.text
    assert paid.status_code == 200, paid.text
    assert fulfilled.status_code == 200, fulfilled.text
    assert release.status_code == 200, release.text
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["data"]["plan"]["id"]

    plan_list = client.get("/api/v1/marketplace-sync/plans?limit=20&offset=0", headers=auth_headers(owner_token))
    plan_detail = client.get(f"/api/v1/marketplace-sync/plans/{plan_id}", headers=auth_headers(owner_token))
    outsider_order = client.get(f"/api/v1/marketplace-sync/orders/{order_id}", headers=auth_headers(outsider_token))
    outsider_plan = client.get(f"/api/v1/marketplace-sync/plans/{plan_id}", headers=auth_headers(outsider_token))

    assert plan_list.status_code == 200, plan_list.text
    assert plan_detail.status_code == 200, plan_detail.text
    assert outsider_order.status_code == 404, outsider_order.text
    assert outsider_plan.status_code == 404, outsider_plan.text
    assert availability.json()["data"]["available_quantity"] == 1
    assert fulfilled.json()["data"]["order"]["order_status"] == "FULFILLED"
    assert plan_detail.json()["data"]["items"]
