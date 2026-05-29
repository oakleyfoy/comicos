from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import LiveSaleClaim, LiveSaleEvent, LiveSaleQueueItem, LiveSaleSession
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _connect_marketplace(client: TestClient, token: str, organization_id: int, suffix: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "ebay",
            "marketplace_account_id": f"ebay-live-sales-{suffix}",
            "display_name": "Live Sales eBay",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/ebay-live-sales-{suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _inventory_copy_id(client: TestClient, token: str) -> int:
    create_order(client, token)
    listing = client.get("/inventory?page=1&page_size=1", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    return int(listing.json()["items"][0]["inventory_copy_id"])


def _inventory_copy_ids(client: TestClient, token: str, *, count: int) -> list[int]:
    for index in range(count):
        create_order(
            client,
            token,
            items=[
                {
                    "title": f"Live Sale Item {index + 1}",
                    "publisher": "Image",
                    "issue_number": str(index + 1),
                    "cover_name": f"Cover {index + 1}",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 5.00 + index,
                }
            ],
        )
    listing = client.get("/inventory?page=1&page_size=20", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    return [int(item["inventory_copy_id"]) for item in listing.json()["items"][:count]]


def _create_listing(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    account_id: int,
    inventory_item_id: int,
    title: str,
    price: str = "10.00",
) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "inventory_item_id": inventory_item_id,
            "listing_title": title,
            "listing_description": "Live sale test listing",
            "listing_price": price,
            "listing_currency": "USD",
            "listing_quantity": 1,
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["draft"]["id"])


def _create_session(client: TestClient, token: str, organization_id: int, *, account_id: int) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "session_name": "Friday live sale",
            "planned_start_at": "2026-05-29T12:00:00Z",
            "planned_end_at": "2026-05-29T13:30:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_live_sale_session_queue_claim_lineage_and_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "live-sales-owner@example.com")
    organization_id = _create_organization(client, owner, slug="live-sales-org")
    account_id = _connect_marketplace(client, owner, organization_id, "workflow")
    inventory_item_ids = _inventory_copy_ids(client, owner, count=3)
    listing_ids = [
        _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=item_id, title=f"Live Sale Listing {index + 1}")
        for index, item_id in enumerate(inventory_item_ids)
    ]

    session_body = _create_session(client, owner, organization_id, account_id=account_id)
    session_id = int(session_body["session"]["id"])
    assert session_body["session"]["session_status"] == "planned"

    updated_session = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}",
        headers=auth_headers(owner),
        json={"session_name": "Friday live sale updated"},
    )
    assert updated_session.status_code == 200, updated_session.text
    assert updated_session.json()["data"]["session"]["session_name"] == "Friday live sale updated"

    add_one = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_ids[0],
            "marketplace_listing_draft_id": listing_ids[0],
            "planned_price": "12.00",
        },
    )
    add_two = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_ids[1],
            "marketplace_listing_draft_id": listing_ids[1],
            "planned_price": "15.00",
        },
    )
    add_three = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_ids[2],
            "marketplace_listing_draft_id": listing_ids[2],
            "planned_price": "20.00",
        },
    )
    assert add_one.status_code == 201, add_one.text
    assert add_two.status_code == 201, add_two.text
    assert add_three.status_code == 201, add_three.text

    queue_listing = client.get(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert queue_listing.status_code == 200, queue_listing.text
    assert [row["queue_position"] for row in queue_listing.json()["data"]["items"]] == [1, 2, 3]

    reordered = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/reorder",
        headers=auth_headers(owner),
        json={"queue_item_ids": [int(add_three.json()["data"]["id"]), int(add_one.json()["data"]["id"]), int(add_two.json()["data"]["id"])]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [row["id"] for row in reordered.json()["data"]["items"]] == [
        int(add_three.json()["data"]["id"]),
        int(add_one.json()["data"]["id"]),
        int(add_two.json()["data"]["id"]),
    ]

    started = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/start",
        headers=auth_headers(owner),
    )
    assert started.status_code == 200, started.text
    assert started.json()["data"]["session"]["session_status"] == "live"

    active = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/{int(add_one.json()['data']['id'])}/status",
        headers=auth_headers(owner),
        json={"item_status": "active"},
    )
    sold = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/{int(add_one.json()['data']['id'])}/status",
        headers=auth_headers(owner),
        json={"item_status": "sold", "actual_sale_price": "13.50"},
    )
    passed = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/{int(add_two.json()['data']['id'])}/status",
        headers=auth_headers(owner),
        json={"item_status": "passed"},
    )
    removed = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/{int(add_three.json()['data']['id'])}/status",
        headers=auth_headers(owner),
        json={"item_status": "removed"},
    )
    assert active.status_code == 200, active.text
    assert sold.status_code == 200, sold.text
    assert passed.status_code == 200, passed.text
    assert removed.status_code == 200, removed.text

    claim = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/claims",
        headers=auth_headers(owner),
        json={
            "live_sale_queue_item_id": int(add_one.json()["data"]["id"]),
            "buyer_identifier": "buyer-live-1",
            "claimed_status": "claimed",
            "claimed_price": "13.50",
        },
    )
    assert claim.status_code == 201, claim.text
    updated_claim = client.patch(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/claims/{claim.json()['data']['id']}",
        headers=auth_headers(owner),
        json={"claim_status": "confirmed"},
    )
    duplicate_claim = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/claims",
        headers=auth_headers(owner),
        json={
            "live_sale_queue_item_id": int(add_one.json()["data"]["id"]),
            "buyer_identifier": "buyer-live-1",
            "claimed_status": "claimed",
            "claimed_price": "13.50",
        },
    )
    ended = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}/end",
        headers=auth_headers(owner),
    )
    assert updated_claim.status_code == 200, updated_claim.text
    assert duplicate_claim.status_code == 201, duplicate_claim.text
    assert duplicate_claim.json()["data"]["id"] == claim.json()["data"]["id"]
    assert ended.status_code == 200, ended.text
    assert ended.json()["data"]["session"]["session_status"] == "ended"

    detail = client.get(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}",
        headers=auth_headers(owner),
    )
    assert detail.status_code == 200, detail.text
    assert [row["queue_position"] for row in detail.json()["data"]["queue_items"]] == [1, 2, 3]
    assert [row["item_status"] for row in detail.json()["data"]["queue_items"]] == ["removed", "sold", "passed"]
    assert detail.json()["data"]["claims"][0]["claim_status"] == "confirmed"

    session.expire_all()
    sessions = session.exec(select(LiveSaleSession).where(LiveSaleSession.organization_id == organization_id)).all()
    queue_rows = session.exec(
        select(LiveSaleQueueItem)
        .where(LiveSaleQueueItem.organization_id == organization_id)
        .order_by(LiveSaleQueueItem.queue_position.asc(), LiveSaleQueueItem.id.asc())
    ).all()
    claim_rows = session.exec(select(LiveSaleClaim).where(LiveSaleClaim.organization_id == organization_id)).all()
    events = session.exec(
        select(LiveSaleEvent)
        .where(LiveSaleEvent.organization_id == organization_id)
        .order_by(LiveSaleEvent.created_at.asc(), LiveSaleEvent.id.asc())
    ).all()

    assert sessions[0].session_status == "ended"
    assert [row.queue_position for row in queue_rows] == [1, 2, 3]
    assert [row.item_status for row in queue_rows] == ["removed", "sold", "passed"]
    assert len(claim_rows) == 1
    assert [row.event_type for row in events] == [
        "live_sale_session_created",
        "live_sale_session_updated",
        "live_sale_queue_item_added",
        "live_sale_queue_item_added",
        "live_sale_queue_item_added",
        "live_sale_queue_reordered",
        "live_sale_session_started",
        "live_sale_item_active",
        "live_sale_item_sold",
        "live_sale_item_passed",
        "live_sale_claim_created",
        "live_sale_claim_status_updated",
        "duplicate_live_sale_claim_detected",
        "live_sale_session_ended",
    ]


def test_live_sale_org_isolation_and_unauthorized_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "live-sales-isolation-owner@example.com")
    outsider = register_and_login(client, "live-sales-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="live-sales-isolation-org")
    _create_organization(client, outsider, slug="live-sales-isolation-outsider-org")
    account_id = _connect_marketplace(client, owner, organization_id, "isolation")
    session_body = _create_session(client, owner, organization_id, account_id=account_id)
    session_id = int(session_body["session"]["id"])

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/live-sales",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    session.expire_all()
    unauthorized_events = session.exec(
        select(LiveSaleEvent)
        .where(LiveSaleEvent.organization_id == organization_id)
        .where(LiveSaleEvent.event_type == "unauthorized_live_sale_access_attempt")
    ).all()
    assert unauthorized_events

    cross_org_session = client.get(
        f"/api/v1/organizations/{organization_id}/live-sales/{session_id}",
        headers=auth_headers(outsider),
    )
    assert cross_org_session.status_code == 403, cross_org_session.text
