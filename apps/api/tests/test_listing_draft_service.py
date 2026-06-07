from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.services.listing_draft_service import generate_listing_draft
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def test_service_generates_draft(client: TestClient, session: Session) -> None:
    email = "p89-svc-draft@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
    from app.models import User
    from app.models.asset_ledger import InventoryCopy

    user = session.exec(select(User).where(User.email == email)).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    copy.current_fmv = Decimal("25")
    session.add(copy)
    session.commit()
    row = generate_listing_draft(
        session,
        owner_user_id=int(user.id),
        inventory_copy_id=int(copy.id),
        marketplace="EBAY",
    )
    assert row.title
    assert row.shipping_notes
    assert row.suggested_price == 25.0
