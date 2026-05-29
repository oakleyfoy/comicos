from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    InventoryCopy,
    OfflineInventoryChange,
    OfflineSyncQueue,
    OrganizationInventoryAssignment,
    QuickSaleEvent,
    QuickSalePayment,
    QuickSaleLineItem,
    User,
)
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _register_device(client: TestClient, token: str, organization_id: int, *, device_identifier: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/devices",
        headers=auth_headers(token),
        json={
            "device_identifier": device_identifier,
            "device_name": device_identifier,
            "device_type": "tablet",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _start_mobile_session(client: TestClient, token: str, organization_id: int, *, device_id: int) -> None:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(token),
        json={"device_id": device_id},
    )
    assert response.status_code == 201, response.text


def _user_id(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).one()
    assert user.id is not None
    return int(user.id)


def _inventory_copy_id(client: TestClient, session: Session, email: str, token: str) -> int:
    create_order(
        client,
        token,
        items=[
            {
                "title": "Quick Sale Item",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 7.00,
            }
        ],
    )
    user_id = _user_id(session, email)
    row = session.exec(
        select(InventoryCopy)
        .where(InventoryCopy.user_id == user_id)
        .order_by(InventoryCopy.id.desc())
    ).first()
    assert row is not None and row.id is not None
    return int(row.id)


def _assign_inventory(session: Session, *, organization_id: int, user_id: int, inventory_item_id: int) -> None:
    session.add(
        OrganizationInventoryAssignment(
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
            assigned_user_id=user_id,
            assigned_by_user_id=user_id,
            assignment_status="ACTIVE",
        )
    )
    session.commit()


def test_quick_sale_creation_idempotency_and_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "quick-sale-owner@example.com")
    organization_id = _create_organization(client, owner, slug="quick-sale-org")

    alpha = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "sale-alpha", "sale_source": "convention", "currency": "USD"},
    )
    zeta = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "sale-zeta", "sale_source": "mobile", "currency": "USD"},
    )
    alpha_repeat = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "sale-alpha", "sale_source": "convention", "currency": "USD"},
    )

    assert alpha.status_code == 201, alpha.text
    assert zeta.status_code == 201, zeta.text
    assert alpha_repeat.status_code == 200, alpha_repeat.text
    assert alpha_repeat.json()["data"]["sale"]["id"] == alpha.json()["data"]["sale"]["id"]

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/quick-sales?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    assert [row["sale_identifier"] for row in listing.json()["data"]["items"]] == ["sale-alpha", "sale-zeta"]


def test_quick_sale_completion_totals_inventory_and_offline_queue(client: TestClient, session: Session) -> None:
    owner_email = "quick-sale-lineage@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="quick-sale-lineage-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="quick-sale-device")
    _start_mobile_session(client, owner, organization_id, device_id=device_id)
    owner_user_id = _user_id(session, owner_email)
    inventory_item_id = _inventory_copy_id(client, session, owner_email, owner)
    _assign_inventory(session, organization_id=organization_id, user_id=owner_user_id, inventory_item_id=inventory_item_id)

    sale = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={
            "sale_identifier": "offline-sale-1",
            "sale_source": "offline",
            "currency": "USD",
            "mobile_device_id": device_id,
        },
    )
    assert sale.status_code == 201, sale.text
    sale_id = sale.json()["data"]["sale"]["id"]

    line_item = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/line-items",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "quantity": 1, "unit_price": "10.00", "discount_amount": "1.00"},
    )
    assert line_item.status_code == 201, line_item.text
    payment = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/payments",
        headers=auth_headers(owner),
        json={"payment_method": "cash", "amount": "9.00", "currency": "USD"},
    )
    assert payment.status_code == 201, payment.text
    completed = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/complete",
        headers=auth_headers(owner),
    )
    assert completed.status_code == 200, completed.text
    body = completed.json()["data"]
    assert body["sale"]["subtotal_amount"] == "10.00"
    assert body["sale"]["discount_amount"] == "1.00"
    assert body["sale"]["total_amount"] == "9.00"
    assert body["sale"]["sale_status"] == "completed"

    inventory_row = session.get(InventoryCopy, inventory_item_id)
    assert inventory_row is not None
    assert inventory_row.hold_status == "sold_internal"
    queued = session.exec(
        select(OfflineSyncQueue)
        .where(OfflineSyncQueue.organization_id == organization_id)
        .order_by(OfflineSyncQueue.queued_at.asc(), OfflineSyncQueue.id.asc())
    ).all()
    assert len(queued) == 1
    changes = session.exec(
        select(OfflineInventoryChange)
        .where(OfflineInventoryChange.organization_id == organization_id)
        .order_by(OfflineInventoryChange.created_at.asc(), OfflineInventoryChange.id.asc())
    ).all()
    assert len(changes) == 1
    events = session.exec(
        select(QuickSaleEvent)
        .where(QuickSaleEvent.organization_id == organization_id)
        .where(QuickSaleEvent.quick_sale_id == sale_id)
        .order_by(QuickSaleEvent.created_at.asc(), QuickSaleEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "quick_sale_created",
        "quick_sale_inventory_reserved",
        "quick_sale_line_item_added",
        "quick_sale_payment_recorded",
        "quick_sale_inventory_sold",
        "quick_sale_completed",
        "quick_sale_offline_queued",
    ]


def test_quick_sale_line_item_removal_and_voiding_release_inventory(client: TestClient, session: Session) -> None:
    owner_email = "quick-sale-void@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="quick-sale-void-org")
    owner_user_id = _user_id(session, owner_email)
    inventory_item_id = _inventory_copy_id(client, session, owner_email, owner)
    _assign_inventory(session, organization_id=organization_id, user_id=owner_user_id, inventory_item_id=inventory_item_id)

    sale = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "void-sale-1", "sale_source": "convention", "currency": "USD"},
    )
    sale_id = sale.json()["data"]["sale"]["id"]
    with_item = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/line-items",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "quantity": 1, "unit_price": "12.00", "discount_amount": "0.00"},
    )
    line_item_id = with_item.json()["data"]["line_items"][0]["id"]
    removed = client.patch(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/line-items/{line_item_id}",
        headers=auth_headers(owner),
        json={"line_status": "removed"},
    )
    assert removed.status_code == 200, removed.text
    inventory_row = session.get(InventoryCopy, inventory_item_id)
    assert inventory_row is not None
    assert inventory_row.hold_status == "hold"

    payment = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/payments",
        headers=auth_headers(owner),
        json={"payment_method": "cash", "amount": "0.00", "currency": "USD"},
    )
    assert payment.status_code == 201, payment.text
    voided = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/void",
        headers=auth_headers(owner),
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["sale"]["sale_status"] == "voided"
    payment_rows = session.exec(
        select(QuickSalePayment)
        .where(QuickSalePayment.quick_sale_id == sale_id)
        .order_by(QuickSalePayment.created_at.asc(), QuickSalePayment.id.asc())
    ).all()
    assert [row.payment_status for row in payment_rows] == ["voided"]
    line_rows = session.exec(
        select(QuickSaleLineItem)
        .where(QuickSaleLineItem.quick_sale_id == sale_id)
        .order_by(QuickSaleLineItem.created_at.asc(), QuickSaleLineItem.id.asc())
    ).all()
    assert [row.line_status for row in line_rows] == ["removed"]


def test_quick_sale_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "quick-sale-isolation-owner@example.com")
    outsider = register_and_login(client, "quick-sale-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="quick-sale-isolation-org")
    _create_organization(client, outsider, slug="quick-sale-outsider-org")

    created = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "private-sale", "sale_source": "convention", "currency": "USD"},
    )
    assert created.status_code == 201, created.text
    sale_id = created.json()["data"]["sale"]["id"]

    denied_list = client.get(f"/api/v1/organizations/{organization_id}/quick-sales", headers=auth_headers(outsider))
    denied_detail = client.get(f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}", headers=auth_headers(outsider))
    denied_create = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(outsider),
        json={"sale_identifier": "hack-sale", "sale_source": "mobile", "currency": "USD"},
    )

    assert denied_list.status_code == 403, denied_list.text
    assert denied_detail.status_code == 403, denied_detail.text
    assert denied_create.status_code == 403, denied_create.text

    attempts = session.exec(
        select(QuickSaleEvent)
        .where(QuickSaleEvent.organization_id == organization_id)
        .where(QuickSaleEvent.event_type == "unauthorized_quick_sale_access_attempt")
        .order_by(QuickSaleEvent.id.asc())
    ).all()
    assert len(attempts) >= 3
