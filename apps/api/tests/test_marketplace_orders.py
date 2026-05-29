from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MarketplaceOrder, MarketplaceOrderEvent, MarketplaceTransaction
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
            "marketplace_account_id": f"ebay-orders-{suffix}",
            "display_name": "Orders eBay",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/ebay-orders-{suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _import_order(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    account_id: int,
    order_identifier: str,
    inventory_item_id: int | None = None,
    ordered_at: str = "2026-05-28T12:00:00Z",
    total: str = "19.99",
    transaction_reference: str = "txn-1",
) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-orders/import",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "marketplace_order_identifier": order_identifier,
            "order_status": "imported",
            "buyer_identifier": "buyer-123",
            "order_total": total,
            "order_currency": "USD",
            "ordered_at": ordered_at,
            "line_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "marketplace_listing_identifier": f"ebay-listing-{order_identifier}",
                    "quantity": 1,
                    "unit_price": total,
                    "line_total": total,
                }
            ],
            "transactions": [
                {
                    "transaction_type": "sale",
                    "transaction_status": "completed",
                    "gross_amount": total,
                    "fee_amount": "1.99",
                    "net_amount": str((Decimal(total) - Decimal("1.99")).quantize(Decimal("0.01"))),
                    "transaction_currency": "USD",
                    "transaction_reference": transaction_reference,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_order_import_persists_detail_and_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-order-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-order-org")
    account_id = _connect_marketplace(client, owner, organization_id, "ordering")
    inventory_item_id = _inventory_copy_id(client, owner)

    _import_order(
        client,
        owner,
        organization_id,
        account_id=account_id,
        order_identifier="order-a",
        inventory_item_id=inventory_item_id,
        ordered_at="2026-05-27T10:00:00Z",
        total="15.00",
        transaction_reference="txn-a",
    )
    _import_order(
        client,
        owner,
        organization_id,
        account_id=account_id,
        order_identifier="order-b",
        inventory_item_id=inventory_item_id,
        ordered_at="2026-05-28T10:00:00Z",
        total="25.00",
        transaction_reference="txn-b",
    )

    orders = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-orders?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert orders.status_code == 200, orders.text
    items = orders.json()["data"]["items"]
    assert [row["marketplace_order_identifier"] for row in items] == ["order-b", "order-a"]

    session.expire_all()
    rows = session.exec(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.organization_id == organization_id)
        .order_by(MarketplaceOrder.ordered_at.asc(), MarketplaceOrder.id.asc())
    ).all()
    assert [row.marketplace_order_identifier for row in rows] == ["order-a", "order-b"]


def test_duplicate_order_import_is_idempotent_and_records_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-order-duplicate@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-order-duplicate-org")
    account_id = _connect_marketplace(client, owner, organization_id, "duplicate")

    first = _import_order(
        client,
        owner,
        organization_id,
        account_id=account_id,
        order_identifier="duplicate-order",
        transaction_reference="txn-duplicate",
    )
    second = _import_order(
        client,
        owner,
        organization_id,
        account_id=account_id,
        order_identifier="duplicate-order",
        transaction_reference="txn-duplicate",
    )
    assert first["order"]["id"] == second["order"]["id"]
    assert second["import_summary"]["duplicate_detected"] is True

    session.expire_all()
    orders = session.exec(
        select(MarketplaceOrder).where(MarketplaceOrder.organization_id == organization_id)
    ).all()
    transactions = session.exec(
        select(MarketplaceTransaction).where(MarketplaceTransaction.organization_id == organization_id)
    ).all()
    events = session.exec(
        select(MarketplaceOrderEvent)
        .where(MarketplaceOrderEvent.organization_id == organization_id)
        .order_by(MarketplaceOrderEvent.created_at.asc(), MarketplaceOrderEvent.id.asc())
    ).all()
    assert len(orders) == 1
    assert len(transactions) == 1
    assert any(event.event_type == "marketplace_duplicate_order_detected" for event in events)
    assert any(event.event_type == "marketplace_order_updated" for event in events)


def test_reconciliation_generates_amount_mismatch_report(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-order-reconcile@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-order-reconcile-org")
    account_id = _connect_marketplace(client, owner, organization_id, "reconcile")
    body = _import_order(
        client,
        owner,
        organization_id,
        account_id=account_id,
        order_identifier="reconcile-order",
        total="20.00",
        transaction_reference="txn-reconcile",
    )
    order_id = int(body["order"]["id"])

    transaction = session.exec(
        select(MarketplaceTransaction)
        .where(MarketplaceTransaction.marketplace_order_id == order_id)
        .order_by(MarketplaceTransaction.id.asc())
    ).first()
    assert transaction is not None
    transaction.gross_amount = Decimal("10.00")
    transaction.net_amount = Decimal("8.00")
    session.add(transaction)
    session.commit()

    report = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-orders/reconcile",
        headers=auth_headers(owner),
        json={"marketplace_account_id": account_id},
    )
    assert report.status_code == 200, report.text
    mismatches = report.json()["data"]["mismatches"]
    assert any(row["mismatch_code"] == "amount_mismatch" for row in mismatches)
    assert any(row["mismatch_code"] == "fee_mismatch" for row in mismatches)


def test_order_org_isolation_denied_and_audited(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-order-isolation-owner@example.com")
    outsider = register_and_login(client, "marketplace-order-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-order-isolation-org")
    _create_organization(client, outsider, slug="marketplace-order-outsider-org")
    account_id = _connect_marketplace(client, owner, organization_id, "isolation")
    body = _import_order(
        client,
        owner,
        organization_id,
        account_id=account_id,
        order_identifier="isolated-order",
        ordered_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-orders/{body['order']['id']}",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    session.expire_all()
    events = session.exec(
        select(MarketplaceOrderEvent)
        .where(MarketplaceOrderEvent.organization_id == organization_id)
        .where(MarketplaceOrderEvent.event_type == "unauthorized_marketplace_order_access_attempt")
    ).all()
    assert events
