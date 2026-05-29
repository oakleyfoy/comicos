from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, ShopifyProductMapping, ShopifyStorefront, ShopifySyncEvent, ShopifySyncState, User
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _connect_shopify_marketplace(client: TestClient, token: str, organization_id: int, suffix: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "shopify",
            "marketplace_account_id": f"shopify-sync-{suffix}",
            "display_name": "Shopify Sync",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/shopify-sync-{suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _inventory_copy_ids(client: TestClient, session: Session, email: str, token: str, *, count: int) -> list[int]:
    for index in range(count):
        create_order(
            client,
            token,
            items=[
                {
                    "title": f"Shopify Sync Item {index + 1}",
                    "publisher": "Image",
                    "issue_number": str(index + 1),
                    "cover_name": f"Cover {index + 1}",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 6.00 + index,
                }
            ],
        )
    user = session.exec(select(User).where(User.email == email)).one()
    rows = session.exec(
        select(InventoryCopy)
        .where(InventoryCopy.user_id == user.id)
        .order_by(InventoryCopy.id.desc())
        .limit(count)
    ).all()
    return [int(row.id or 0) for row in reversed(rows)]


def _create_listing(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    account_id: int,
    inventory_item_id: int,
    title: str,
) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "inventory_item_id": inventory_item_id,
            "listing_title": title,
            "listing_description": "Shopify sync test listing",
            "listing_price": "12.00",
            "listing_currency": "USD",
            "listing_quantity": 1,
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["draft"]["id"])


def test_shopify_storefront_mapping_snapshot_and_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "shopify-sync-owner@example.com")
    organization_id = _create_organization(client, owner, slug="shopify-sync-org")
    account_id = _connect_shopify_marketplace(client, owner, organization_id, "ordering")
    inventory_item_ids = _inventory_copy_ids(client, session, "shopify-sync-owner@example.com", owner, count=2)
    listing_ids = [
        _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=item_id, title=f"Shopify Sync Listing {index + 1}")
        for index, item_id in enumerate(inventory_item_ids)
    ]

    storefront = client.post(
        f"/api/v1/organizations/{organization_id}/shopify/storefront",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "storefront_name": "ComicOS Shopify",
            "storefront_identifier": "comicos-shopify",
            "storefront_status": "ready",
        },
    )
    assert storefront.status_code == 201, storefront.text
    storefront_id = int(storefront.json()["data"]["id"])

    first_mapping = client.post(
        f"/api/v1/organizations/{organization_id}/shopify/mappings",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_ids[0],
            "marketplace_listing_draft_id": listing_ids[0],
            "storefront_product_identifier": "shopify-product-1",
            "mapping_status": "mapped",
        },
    )
    second_mapping = client.post(
        f"/api/v1/organizations/{organization_id}/shopify/mappings",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_ids[1],
            "marketplace_listing_draft_id": listing_ids[1],
            "storefront_product_identifier": "shopify-product-2",
            "mapping_status": "mapped",
        },
    )
    assert first_mapping.status_code == 201, first_mapping.text
    assert second_mapping.status_code == 201, second_mapping.text

    updated_mapping = client.patch(
        f"/api/v1/organizations/{organization_id}/shopify/mappings/{int(first_mapping.json()['data']['id'])}",
        headers=auth_headers(owner),
        json={
            "storefront_product_identifier": "shopify-product-1-updated",
            "mapping_status": "unmapped",
        },
    )
    assert updated_mapping.status_code == 200, updated_mapping.text
    assert updated_mapping.json()["data"]["storefront_product_identifier"] == "shopify-product-1-updated"

    mappings = client.get(
        f"/api/v1/organizations/{organization_id}/shopify/mappings?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert mappings.status_code == 200, mappings.text
    assert [row["storefront_product_identifier"] for row in mappings.json()["data"]["items"]] == [
        "shopify-product-1-updated",
        "shopify-product-2",
    ]

    snapshot = client.post(
        f"/api/v1/organizations/{organization_id}/shopify/snapshot",
        headers=auth_headers(owner),
        json={"storefront_id": storefront_id},
    )
    assert snapshot.status_code == 200, snapshot.text
    snapshot_payload = snapshot.json()["data"]
    assert snapshot_payload["sync_state"]["sync_status"] == "completed"
    assert snapshot_payload["projection_payload_json"]["schema_version"] == "P43-08-shopify-sync-v1"
    assert [row["storefront_product_identifier"] for row in snapshot_payload["mappings"]] == [
        "shopify-product-1-updated",
        "shopify-product-2",
    ]

    overview = client.get(
        f"/api/v1/organizations/{organization_id}/shopify",
        headers=auth_headers(owner),
    )
    assert overview.status_code == 200, overview.text
    assert overview.json()["data"]["summary"]["storefront_count"] == 1
    assert overview.json()["data"]["summary"]["mapped_items"] == 1

    sync_states = client.get(
        f"/api/v1/organizations/{organization_id}/shopify/sync-states?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert sync_states.status_code == 200, sync_states.text
    assert sync_states.json()["data"]["items"][0]["sync_status"] == "completed"

    session.expire_all()
    storefront_rows = session.exec(select(ShopifyStorefront).where(ShopifyStorefront.organization_id == organization_id)).all()
    mapping_rows = session.exec(
        select(ShopifyProductMapping)
        .where(ShopifyProductMapping.organization_id == organization_id)
        .order_by(ShopifyProductMapping.updated_at.desc(), ShopifyProductMapping.id.desc())
    ).all()
    sync_state_rows = session.exec(select(ShopifySyncState).where(ShopifySyncState.organization_id == organization_id)).all()
    events = session.exec(
        select(ShopifySyncEvent)
        .where(ShopifySyncEvent.organization_id == organization_id)
        .order_by(ShopifySyncEvent.created_at.asc(), ShopifySyncEvent.id.asc())
    ).all()

    assert len(storefront_rows) == 1
    assert [row.storefront_product_identifier for row in mapping_rows] == [
        "shopify-product-1-updated",
        "shopify-product-2",
    ]
    assert len(sync_state_rows) == 1
    assert [row.event_type for row in events] == [
        "storefront_created",
        "product_mapping_created",
        "product_mapping_created",
        "product_mapping_updated",
        "storefront_projection_generated",
        "sync_snapshot_generated",
    ]


def test_shopify_org_isolation_and_invalid_mapping_detection(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "shopify-sync-isolation-owner@example.com")
    outsider = register_and_login(client, "shopify-sync-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="shopify-sync-isolation-org")
    _create_organization(client, outsider, slug="shopify-sync-isolation-outsider-org")
    account_id = _connect_shopify_marketplace(client, owner, organization_id, "isolation")
    inventory_item_id = _inventory_copy_ids(client, session, "shopify-sync-isolation-owner@example.com", owner, count=1)[0]
    listing_id = _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id, title="Isolation Listing")

    storefront = client.post(
        f"/api/v1/organizations/{organization_id}/shopify/storefront",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "storefront_name": "Isolation Shopify",
            "storefront_identifier": "isolation-shopify",
            "storefront_status": "draft",
        },
    )
    assert storefront.status_code == 201, storefront.text

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/shopify",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    invalid = client.post(
        f"/api/v1/organizations/{organization_id}/shopify/mappings",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_id,
            "marketplace_listing_draft_id": listing_id,
            "storefront_product_identifier": "shopify-invalid",
            "mapping_status": "bogus",
        },
    )
    assert invalid.status_code == 422, invalid.text

    session.expire_all()
    invalid_events = session.exec(
        select(ShopifySyncEvent)
        .where(ShopifySyncEvent.organization_id == organization_id)
        .where(ShopifySyncEvent.event_type == "invalid_product_mapping_detected")
    ).all()
    unauthorized_events = session.exec(
        select(ShopifySyncEvent)
        .where(ShopifySyncEvent.organization_id == organization_id)
        .where(ShopifySyncEvent.event_type == "unauthorized_shopify_access_attempt")
    ).all()
    assert invalid_events
    assert unauthorized_events
