from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.asset_ledger import InventoryCopy
from app.services.listing_draft_service import generate_listing_draft
from test_inventory import auth_headers, create_order, register_and_login


def test_api_create_from_draft_and_mark_sold(client: TestClient, session: Session) -> None:
    email = "p89-ml@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
    user = session.exec(select(User).where(User.email == email)).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    copy.acquisition_cost = Decimal("8.00")
    session.add(copy)
    session.commit()
    draft = generate_listing_draft(
        session,
        owner_user_id=int(user.id),
        inventory_copy_id=int(copy.id),
        marketplace="EBAY",
    )
    session.commit()
    created = client.post(
        "/api/v1/listing-management",
        headers=auth_headers(token),
        json={"listing_draft_id": int(draft.id)},
    )
    assert created.status_code == 201
    listing_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "DRAFT"
    active = client.post(f"/api/v1/listing-management/{listing_id}/mark-active", headers=auth_headers(token))
    assert active.status_code == 200
    assert active.json()["data"]["status"] == "ACTIVE"
    sold = client.post(
        f"/api/v1/listing-management/{listing_id}/mark-sold",
        headers=auth_headers(token),
        json={"sale_price": 25.0, "marketplace_fees": 2.5, "shipping_cost": 5.0},
    )
    assert sold.status_code == 200
    body = sold.json()["data"]
    assert body["status"] == "SOLD"
    assert body["profit"]["cost_basis_known"] is True
    assert body["profit"]["net_profit"] is not None
    assert body["inventory_auto_updated"] is False
    inv = client.post(
        f"/api/v1/listing-management/{listing_id}/mark-inventory-sold",
        headers=auth_headers(token),
    )
    assert inv.status_code == 200
    session.refresh(copy)
    assert copy.order_status == "sold"


def test_api_list_and_portfolio_summary(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p89-ml-list@example.com")
    listing = client.get("/api/v1/listing-management?status=DRAFT", headers=auth_headers(token))
    assert listing.status_code == 200
    summary = client.get("/api/v1/listing-management/portfolio-summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert "active_listing_value" in summary.json()["data"]
