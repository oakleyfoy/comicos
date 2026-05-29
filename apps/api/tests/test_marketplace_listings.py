from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MarketplaceListingEvent, MarketplaceListingProjection
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _inventory_copy_id(client: TestClient, token: str) -> int:
    create_order(client, token)
    listing = client.get("/inventory?page=1&page_size=1", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    return int(listing.json()["items"][0]["inventory_copy_id"])


def _connect_marketplace(client: TestClient, token: str, organization_id: int) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "ebay",
            "marketplace_account_id": f"ebay-listing-{organization_id}",
            "display_name": "Listing eBay",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/ebay-listing-{organization_id}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _create_listing(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    account_id: int,
    inventory_item_id: int,
    title: str = "Invincible #1 Raw Copy",
    price: str = "24.99",
):
    return client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "inventory_item_id": inventory_item_id,
            "listing_title": title,
            "listing_description": "Deterministic listing draft for tests.",
            "listing_price": price,
            "listing_currency": "USD",
            "listing_quantity": 1,
        },
    )


def test_listing_draft_creation_update_archive_and_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "listing-owner@example.com")
    organization_id = _create_organization(client, owner, slug="listing-org")
    account_id = _connect_marketplace(client, owner, organization_id)
    inventory_a = _inventory_copy_id(client, owner)
    inventory_b = _inventory_copy_id(client, owner)

    first = _create_listing(
        client,
        owner,
        organization_id,
        account_id=account_id,
        inventory_item_id=inventory_a,
        title="Alpha Listing",
    )
    second = _create_listing(
        client,
        owner,
        organization_id,
        account_id=account_id,
        inventory_item_id=inventory_b,
        title="Beta Listing",
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    listing_id = int(first.json()["data"]["draft"]["id"])

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-listings?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    payload = listing.json()["data"]
    assert [row["listing_title"] for row in payload["items"]] == ["Alpha Listing", "Beta Listing"]
    assert payload["permissions"]["can_manage"] is True

    updated = client.patch(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}",
        headers=auth_headers(owner),
        json={"listing_title": "Alpha Listing Updated", "listing_status": "ready"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["draft"]["listing_status"] == "ready"
    assert updated.json()["data"]["draft"]["validation_status"] == "valid"

    archived = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}/archive",
        headers=auth_headers(owner),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["draft"]["listing_status"] == "archived"
    assert archived.json()["data"]["draft"]["archived_at"] is not None


def test_listing_projection_generation_is_deterministic(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "listing-projection-owner@example.com")
    organization_id = _create_organization(client, owner, slug="listing-projection-org")
    account_id = _connect_marketplace(client, owner, organization_id)
    inventory_item_id = _inventory_copy_id(client, owner)

    created = _create_listing(
        client,
        owner,
        organization_id,
        account_id=account_id,
        inventory_item_id=inventory_item_id,
    )
    assert created.status_code == 201, created.text
    listing_id = int(created.json()["data"]["draft"]["id"])

    not_ready = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}/projection",
        headers=auth_headers(owner),
    )
    assert not_ready.status_code == 422, not_ready.text

    ready = client.patch(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}",
        headers=auth_headers(owner),
        json={"listing_status": "ready"},
    )
    assert ready.status_code == 200, ready.text

    first_projection = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}/projection",
        headers=auth_headers(owner),
    )
    second_projection = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}/projection",
        headers=auth_headers(owner),
    )
    assert first_projection.status_code == 200, first_projection.text
    assert second_projection.status_code == 200, second_projection.text

    detail = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}",
        headers=auth_headers(owner),
    )
    assert detail.status_code == 200, detail.text
    projections = detail.json()["data"]["projections"]
    assert len(projections) >= 2
    assert projections[0]["marketplace_type"] == "ebay"
    assert projections[0]["projection_payload_json"]["marketplace"] == "ebay"
    assert "acquisition_cost" not in projections[0]["projection_payload_json"]["inventory"]

    session.expire_all()
    rows = session.exec(
        select(MarketplaceListingProjection)
        .where(MarketplaceListingProjection.marketplace_listing_draft_id == listing_id)
        .order_by(MarketplaceListingProjection.generated_at.asc(), MarketplaceListingProjection.id.asc())
    ).all()
    assert rows[0].projection_status == "superseded"
    assert rows[-1].projection_status == "current"
    assert rows[0].projection_payload_json == rows[1].projection_payload_json


def test_listing_validation_failure_and_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "listing-validation-owner@example.com")
    organization_id = _create_organization(client, owner, slug="listing-validation-org")
    account_id = _connect_marketplace(client, owner, organization_id)
    inventory_item_id = _inventory_copy_id(client, owner)

    created = _create_listing(
        client,
        owner,
        organization_id,
        account_id=account_id,
        inventory_item_id=inventory_item_id,
        price="19.99",
    )
    listing_id = int(created.json()["data"]["draft"]["id"])

    failed = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}/projection",
        headers=auth_headers(owner),
    )
    assert failed.status_code == 422, failed.text

    session.expire_all()
    events = session.exec(
        select(MarketplaceListingEvent)
        .where(MarketplaceListingEvent.marketplace_listing_draft_id == listing_id)
        .order_by(MarketplaceListingEvent.created_at.asc(), MarketplaceListingEvent.id.asc())
    ).all()
    assert events[0].event_type == "marketplace_listing_draft_created"
    assert any(row.event_type == "marketplace_listing_validation_failed" for row in events)


def test_listing_org_isolation_and_account_validation(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "listing-isolation-owner@example.com")
    outsider = register_and_login(client, "listing-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="listing-isolation-org")
    _create_organization(client, outsider, slug="listing-outsider-org")
    account_id = _connect_marketplace(client, owner, organization_id)
    inventory_item_id = _inventory_copy_id(client, owner)

    created = _create_listing(
        client,
        owner,
        organization_id,
        account_id=account_id,
        inventory_item_id=inventory_item_id,
    )
    assert created.status_code == 201, created.text
    listing_id = int(created.json()["data"]["draft"]["id"])

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-listings",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    other_org = _create_organization(client, owner, slug="listing-other-org")
    wrong_account = client.post(
        f"/api/v1/organizations/{other_org}/marketplace-listings",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "inventory_item_id": inventory_item_id,
            "listing_title": "Cross org listing",
            "listing_price": "12.00",
            "listing_currency": "USD",
            "listing_quantity": 1,
        },
    )
    assert wrong_account.status_code == 403, wrong_account.text

    session.expire_all()
    unauthorized_events = session.exec(
        select(MarketplaceListingEvent)
        .where(MarketplaceListingEvent.organization_id == organization_id)
        .where(MarketplaceListingEvent.event_type == "unauthorized_marketplace_listing_access_attempt")
    ).all()
    assert unauthorized_events

    disconnected = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/disconnect",
        headers=auth_headers(owner),
        json={"account_id": account_id, "reason": "test disconnect"},
    )
    assert disconnected.status_code == 200, disconnected.text

    blocked = _create_listing(
        client,
        owner,
        organization_id,
        account_id=account_id,
        inventory_item_id=inventory_item_id,
        title="After disconnect",
    )
    assert blocked.status_code == 409, blocked.text

    assert listing_id > 0
