from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import DealerStorefrontEvent
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
    return int(listing.json()["items"][0]["inventory_copy_id"])


def _bootstrap_public_storefront(client: TestClient, owner: str, organization_id: int, inventory_item_id: int) -> str:
    profile = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(owner),
        json={
            "public_slug": "alpha-dealer",
            "display_name": "Alpha Dealer",
            "tagline": "Premium comics",
            "profile_status": "ACTIVE",
        },
    )
    assert profile.status_code == 200, profile.text
    settings = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/settings",
        headers=auth_headers(owner),
        json={
            "storefront_visibility": "PUBLIC",
            "public_inventory_enabled": True,
            "featured_inventory_limit": 2,
            "featured_inventory_sort": "manually_selected",
            "featured_manual_inventory_ids": [inventory_item_id],
        },
    )
    assert settings.status_code == 200, settings.text
    return "alpha-dealer"


def test_storefront_creation_public_resolution_and_featured_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "storefront-owner@example.com")
    organization_id = _create_organization(client, owner, slug="storefront-org")
    inventory_item_id = _inventory_copy_id(client, owner)
    public_slug = _bootstrap_public_storefront(client, owner, organization_id, inventory_item_id)

    storefront = client.get(f"/api/v1/storefronts/{public_slug}")
    assert storefront.status_code == 200, storefront.text
    assert storefront.json()["data"]["profile"]["display_name"] == "Alpha Dealer"

    featured = client.get(f"/api/v1/storefronts/{public_slug}/featured")
    assert featured.status_code == 200, featured.text
    assert [row["inventory_copy_id"] for row in featured.json()["data"]["items"]] == [inventory_item_id]

    inventory = client.get(f"/api/v1/storefronts/{public_slug}/inventory?limit=10&offset=0")
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["data"]["items"][0]["title"] == "Invincible"
    assert "acquisition_cost" not in inventory.json()["data"]["items"][0]
    assert "organization_review_status" not in inventory.json()["data"]["items"][0]


def test_hidden_inventory_and_visibility_enforcement(client: TestClient) -> None:
    owner = register_and_login(client, "storefront-hidden-owner@example.com")
    outsider = register_and_login(client, "storefront-hidden-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="hidden-storefront-org")
    _inventory_copy_id(client, owner)

    client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(owner),
        json={"public_slug": "hidden-dealer", "display_name": "Hidden Dealer", "profile_status": "ACTIVE"},
    )
    client.post(
        f"/api/v1/organizations/{organization_id}/storefront/settings",
        headers=auth_headers(owner),
        json={"storefront_visibility": "PRIVATE", "public_inventory_enabled": True},
    )

    hidden = client.get("/api/v1/storefronts/hidden-dealer/inventory")
    assert hidden.status_code == 404, hidden.text

    other_org = _create_organization(client, outsider, slug="outsider-storefront-org")
    denied = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/settings",
        headers=auth_headers(outsider),
        json={"storefront_visibility": "PUBLIC", "public_inventory_enabled": True},
    )
    assert denied.status_code == 403, denied.text
    assert other_org > 0


def test_append_only_storefront_events_and_unauthorized_access(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "storefront-events-owner@example.com")
    outsider = register_and_login(client, "storefront-events-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="events-storefront-org")

    before = len(session.exec(select(DealerStorefrontEvent)).all())
    client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(owner),
        json={"public_slug": "events-dealer", "display_name": "Events Dealer", "profile_status": "ACTIVE"},
    )
    after_create = session.exec(select(DealerStorefrontEvent).order_by(DealerStorefrontEvent.id.asc())).all()
    assert len(after_create) >= before + 1
    assert after_create[-1].event_type in {"storefront_created", "storefront_updated"}

    denied = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(outsider),
        json={"public_slug": "blocked-dealer", "display_name": "Blocked", "profile_status": "ACTIVE"},
    )
    assert denied.status_code == 403, denied.text

    updated = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(owner),
        json={"public_slug": "events-dealer", "display_name": "Events Dealer Updated", "profile_status": "ACTIVE"},
    )
    assert updated.status_code == 200, updated.text
    session.expire_all()
    event_types = [row.event_type for row in session.exec(select(DealerStorefrontEvent)).all()]
    assert "storefront_updated" in event_types
