from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.asset_ledger import InventoryCopy
from app.services.listing_draft_service import generate_listing_draft
from app.services.listing_management_service import (
    archive_managed_listing,
    cancel_managed_listing,
    create_managed_listing_from_draft,
    mark_listing_active,
    mark_listing_expired,
    mark_listing_sold,
)
from test_inventory import create_order, register_and_login


def test_create_from_draft_and_lifecycle(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p89-ml-svc@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "p89-ml-svc@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    copy.acquisition_cost = Decimal("6.00")
    session.add(copy)
    session.commit()
    draft = generate_listing_draft(
        session,
        owner_user_id=int(user.id),
        inventory_copy_id=int(copy.id),
        marketplace="EBAY",
    )
    session.commit()
    row = create_managed_listing_from_draft(session, owner_user_id=int(user.id), listing_draft_id=int(draft.id))
    assert row.status == "DRAFT"
    mark_listing_active(session, owner_user_id=int(user.id), listing_id=int(row.id))
    mark_listing_expired(session, owner_user_id=int(user.id), listing_id=int(row.id))
    mark_listing_active(session, owner_user_id=int(user.id), listing_id=int(row.id))
    mark_listing_sold(session, owner_user_id=int(user.id), listing_id=int(row.id), sale_price=20.0, marketplace_fees=2.0)
    assert row.net_profit is not None
    archive_managed_listing(session, owner_user_id=int(user.id), listing_id=int(row.id))
    assert row.status == "ARCHIVED"


def test_cancel_draft_listing(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p89-ml-cancel@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "p89-ml-cancel@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    draft = generate_listing_draft(
        session,
        owner_user_id=int(user.id),
        inventory_copy_id=int(copy.id),
        marketplace="EBAY",
    )
    session.commit()
    row = create_managed_listing_from_draft(session, owner_user_id=int(user.id), listing_draft_id=int(draft.id))
    cancel_managed_listing(session, owner_user_id=int(user.id), listing_id=int(row.id))
    assert row.status == "CANCELLED"
