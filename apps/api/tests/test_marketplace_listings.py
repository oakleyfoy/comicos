from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketplaceListingEvent, MarketplaceListingProjection, User
from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingStatusHistory
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingUpdate
from app.services.marketplace_listings import archive_listing, create_listing, get_listing, mark_ready_to_publish, update_listing
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


def _canonical_inventory_copy_id(client: TestClient, token: str) -> int:
    create_order(client, token)
    response = client.get("/inventory?page=1&page_size=1", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return int(response.json()["items"][0]["inventory_copy_id"])


def test_canonical_marketplace_listing_create_update_archive_and_history(client: TestClient) -> None:
    token = register_and_login(client, "canonical-listing-owner@example.com")
    inventory_copy_id = _canonical_inventory_copy_id(client, token)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "canonical-listing-owner@example.com")).one()
        detail = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                inventory_copy_id=inventory_copy_id,
                listing_title="Canonical Listing",
                listing_description="Internal source of truth listing.",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                grade_label="9.8",
                asking_price="19.99",
                currency="usd",
                quantity=1,
                variants=[
                    {
                        "variant_code": "RAW",
                        "variant_name": "Raw Copy",
                        "sku": "RAW-1",
                        "quantity": 1,
                        "price": "19.99",
                    }
                ],
            ),
        )
        listing_id = detail.listing.id
        assert detail.listing.inventory_copy_id == inventory_copy_id
        assert detail.listing.status == "DRAFT"
        assert detail.variants[0].variant_code == "RAW"

        updated = update_listing(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing_id,
            payload=MarketplaceListingUpdate(
                listing_title="Canonical Listing Updated",
                quantity=2,
                variants=[
                    {
                        "variant_code": "SLAB",
                        "variant_name": "Slabbed Copy",
                        "sku": "SLAB-1",
                        "quantity": 1,
                        "price": "29.99",
                    }
                ],
            ),
        )
        ready = mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing_id)
        archived = archive_listing(session, owner_id=int(owner.id or 0), listing_id=listing_id)

        assert updated.listing.listing_title == "Canonical Listing Updated"
        assert updated.variants[0].variant_code == "SLAB"
        assert ready.listing.status == "READY_TO_PUBLISH"
        assert archived.listing.status == "ARCHIVED"

        session.expire_all()
        history = session.exec(
            select(MarketplaceListingStatusHistory)
            .where(MarketplaceListingStatusHistory.listing_id == listing_id)
            .order_by(MarketplaceListingStatusHistory.changed_at.asc(), MarketplaceListingStatusHistory.id.asc())
        ).all()
        assert [row.new_status for row in history] == ["DRAFT", "READY_TO_PUBLISH", "ARCHIVED"]


def test_canonical_marketplace_listing_owner_scoping(client: TestClient) -> None:
    token = register_and_login(client, "canonical-scope-owner@example.com")
    outsider_token = register_and_login(client, "canonical-scope-outsider@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "canonical-scope-owner@example.com")).one()
        outsider = session.exec(select(User).where(User.email == "canonical-scope-outsider@example.com")).one()
        detail = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Scoped Listing",
                listing_description="Owner only.",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="11.00",
                currency="USD",
                quantity=1,
            ),
        )

        same_owner = get_listing(session, owner_id=int(owner.id or 0), listing_id=detail.listing.id)
        assert same_owner.listing.id == detail.listing.id

        try:
            get_listing(session, owner_id=int(outsider.id or 0), listing_id=detail.listing.id)
        except Exception as exc:  # pragma: no cover - explicit assertion below
            assert getattr(exc, "status_code", None) == 404
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected owner scoping to hide canonical listing.")
