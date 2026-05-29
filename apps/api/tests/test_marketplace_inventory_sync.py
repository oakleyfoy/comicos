from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    MarketplaceInventoryConflict,
    MarketplaceInventoryState,
    MarketplaceInventorySyncEvent,
)
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


def _connect_marketplace(client: TestClient, token: str, organization_id: int, suffix: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "ebay",
            "marketplace_account_id": f"ebay-sync-{suffix}",
            "display_name": "Sync eBay",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/ebay-sync-{suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _create_listing(client: TestClient, token: str, organization_id: int, *, account_id: int, inventory_item_id: int, title: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "inventory_item_id": inventory_item_id,
            "listing_title": title,
            "listing_description": "Sync foundation listing",
            "listing_price": "19.99",
            "listing_currency": "USD",
            "listing_quantity": 1,
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["draft"]["id"])


def test_sync_run_creates_state_registry_and_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-sync-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-sync-org")
    account_id = _connect_marketplace(client, owner, organization_id, "ordering")

    inventory_a = _inventory_copy_id(client, owner)
    inventory_b = _inventory_copy_id(client, owner)
    listing_a_id = _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_a, title="Alpha sync")
    listing_b_id = _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_b, title="Beta sync")

    run = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/run",
        headers=auth_headers(owner),
        json={"marketplace_account_id": account_id, "sync_run_type": "manual_sync"},
    )
    assert run.status_code == 201, run.text
    data = run.json()["data"]
    assert data["sync_status"] == "completed"
    assert data["records_processed"] == 2
    assert data["conflicts_detected"] == 2

    states = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/states?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert states.status_code == 200, states.text
    items = states.json()["data"]["items"]
    assert [row["marketplace_listing_identifier"] for row in items] == [f"ebay:{listing_a_id}", f"ebay:{listing_b_id}"]
    assert [row["sync_status"] for row in items] == ["failed", "failed"]

    session.expire_all()
    rows = session.exec(
        select(MarketplaceInventoryState)
        .where(MarketplaceInventoryState.organization_id == organization_id)
        .order_by(MarketplaceInventoryState.created_at.asc(), MarketplaceInventoryState.id.asc())
    ).all()
    assert [row.marketplace_listing_identifier for row in rows] == [f"ebay:{listing_a_id}", f"ebay:{listing_b_id}"]


def test_reconciliation_generates_quantity_mismatch_conflict(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-sync-reconcile@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-sync-reconcile-org")
    account_id = _connect_marketplace(client, owner, organization_id, "reconcile")
    inventory_item_id = _inventory_copy_id(client, owner)
    _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id, title="Recon sync")

    run = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/run",
        headers=auth_headers(owner),
        json={"marketplace_account_id": account_id},
    )
    assert run.status_code == 201, run.text

    state = session.exec(
        select(MarketplaceInventoryState)
        .where(MarketplaceInventoryState.organization_id == organization_id)
        .order_by(MarketplaceInventoryState.id.asc())
    ).first()
    assert state is not None
    state.marketplace_quantity = 3
    state.last_sync_at = datetime.now(timezone.utc)
    session.add(state)
    session.commit()

    report = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/reconcile",
        headers=auth_headers(owner),
        json={"marketplace_account_id": account_id},
    )
    assert report.status_code == 200, report.text
    conflicts = report.json()["data"]["conflicts"]
    assert any(row["conflict_type"] == "quantity_mismatch" for row in conflicts)
    assert report.json()["data"]["entries"][0]["marketplace_quantity"] == 3


def test_sync_org_isolation_denied_and_event_recorded(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-sync-isolation-owner@example.com")
    outsider = register_and_login(client, "marketplace-sync-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-sync-isolation-org")
    _create_organization(client, outsider, slug="marketplace-sync-outsider-org")
    account_id = _connect_marketplace(client, owner, organization_id, "isolation")
    inventory_item_id = _inventory_copy_id(client, owner)
    _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id, title="Isolation sync")

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-sync",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    session.expire_all()
    events = session.exec(
        select(MarketplaceInventorySyncEvent)
        .where(MarketplaceInventorySyncEvent.organization_id == organization_id)
        .where(MarketplaceInventorySyncEvent.event_type == "unauthorized_marketplace_sync_access_attempt")
    ).all()
    assert events


def test_sync_processing_is_idempotent_for_state_registry(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-sync-idempotent@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-sync-idempotent-org")
    account_id = _connect_marketplace(client, owner, organization_id, "idempotent")
    inventory_item_id = _inventory_copy_id(client, owner)
    _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id, title="Idempotent sync")

    first = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/run",
        headers=auth_headers(owner),
        json={"marketplace_account_id": account_id},
    )
    second = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/run",
        headers=auth_headers(owner),
        json={"marketplace_account_id": account_id},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    session.expire_all()
    states = session.exec(
        select(MarketplaceInventoryState)
        .where(MarketplaceInventoryState.organization_id == organization_id)
    ).all()
    conflicts = session.exec(
        select(MarketplaceInventoryConflict)
        .join(MarketplaceInventoryState, MarketplaceInventoryConflict.marketplace_inventory_state_id == MarketplaceInventoryState.id)
        .where(MarketplaceInventoryState.organization_id == organization_id)
        .where(MarketplaceInventoryConflict.conflict_status != "resolved")
    ).all()
    assert len(states) == 1
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "missing_marketplace_inventory"
