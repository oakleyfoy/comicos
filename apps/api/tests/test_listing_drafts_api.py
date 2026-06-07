from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.p89_listing_draft import P89ListingDraft
from app.services.listing_draft_service import generate_listing_draft
from test_inventory import auth_headers, create_order, register_and_login


def test_generate_draft_with_fmv_fallback(client: TestClient, session: Session) -> None:
    email = "p89-draft@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
    from app.models import User
    from app.models.asset_ledger import InventoryCopy

    user = session.exec(select(User).where(User.email == email)).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    copy.current_fmv = Decimal("42.00")
    session.add(copy)
    session.commit()

    resp = client.post(
        "/api/v1/listing-drafts",
        headers=auth_headers(token),
        json={"inventory_copy_id": int(copy.id), "marketplace": "EBAY"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["title"]
    assert data["description"]
    assert data["suggested_price"] == 42.0
    assert data["minimum_price"] is not None


def test_patch_and_mark_reviewed(client: TestClient, session: Session) -> None:
    email = "p89-draft-edit@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
    from app.models import User
    from app.models.asset_ledger import InventoryCopy

    user = session.exec(select(User).where(User.email == email)).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    row = generate_listing_draft(
        session,
        owner_user_id=int(user.id),
        inventory_copy_id=int(copy.id),
        marketplace="EBAY",
    )
    session.commit()
    draft_id = int(row.id or 0)
    patch = client.patch(
        f"/api/v1/listing-drafts/{draft_id}",
        headers=auth_headers(token),
        json={"title": "Custom Title", "suggested_price": 99.0},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["title"] == "Custom Title"
    reviewed = client.post(f"/api/v1/listing-drafts/{draft_id}/mark-reviewed", headers=auth_headers(token))
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "REVIEWED"
    archived = client.patch(
        f"/api/v1/listing-drafts/{draft_id}",
        headers=auth_headers(token),
        json={"status": "ARCHIVED"},
    )
    assert archived.json()["data"]["status"] == "ARCHIVED"


def test_list_filter(client: TestClient, session: Session) -> None:
    email = "p89-draft-list@example.com"
    token = register_and_login(client, email)
    listing = client.get("/api/v1/listing-drafts?status=DRAFT", headers=auth_headers(token))
    assert listing.status_code == 200
    assert "items" in listing.json()["data"]
