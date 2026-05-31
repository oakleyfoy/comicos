from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace_sync import MarketplaceInventoryReservation
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.marketplace_sync import MarketplaceInventoryReservationCreate
from app.services.marketplace_inventory_reservations import (
    create_reservation,
    expire_reservations,
    get_reservation,
    list_reservations,
    release_reservation,
)
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def _setup_listing(client: TestClient, email: str, *, quantity: int = 3) -> tuple[int, int]:
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Reservation Listing",
                listing_description="Reservation test listing",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="12.00",
                currency="USD",
                quantity=quantity,
            ),
        )
        return int(owner.id or 0), listing.listing.id


def test_marketplace_inventory_reservation_create_release_and_history(client: TestClient) -> None:
    owner_id, listing_id = _setup_listing(client, "reservation-owner@example.com", quantity=3)

    with Session(get_engine()) as session:
        created = create_reservation(
            session,
            owner_id=owner_id,
            payload=MarketplaceInventoryReservationCreate(
                listing_id=listing_id,
                inventory_copy_id=None,
                reservation_type="cart_hold",
                quantity_reserved=2,
                source="checkout_preview",
                expires_at=None,
            ),
        )
        fetched = get_reservation(session, owner_id=owner_id, reservation_id=created.id)
        released = release_reservation(session, owner_id=owner_id, reservation_id=created.id)
        listed = list_reservations(session, owner_id=owner_id, limit=20, offset=0)

        assert created.status == "ACTIVE"
        assert fetched.reservation_uuid == created.reservation_uuid
        assert released.status == "RELEASED"
        assert released.released_at is not None
        assert listed.total_items == 1
        assert listed.items[0].status == "RELEASED"

        rows = session.exec(select(MarketplaceInventoryReservation)).all()
        assert len(rows) == 1


def test_marketplace_inventory_reservation_cannot_exceed_available_quantity(client: TestClient) -> None:
    owner_id, listing_id = _setup_listing(client, "reservation-cap-owner@example.com", quantity=1)

    with Session(get_engine()) as session:
        try:
            create_reservation(
                session,
                owner_id=owner_id,
                payload=MarketplaceInventoryReservationCreate(
                    listing_id=listing_id,
                    inventory_copy_id=None,
                    reservation_type="cart_hold",
                    quantity_reserved=2,
                    source="oversell_attempt",
                    expires_at=None,
                ),
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "available quantity" in exc.detail.lower()
        else:
            raise AssertionError("Expected create_reservation to reject an oversized reservation.")


def test_marketplace_inventory_reservation_expiration_keeps_history(client: TestClient) -> None:
    owner_id, listing_id = _setup_listing(client, "reservation-expire-owner@example.com", quantity=2)

    with Session(get_engine()) as session:
        created = create_reservation(
            session,
            owner_id=owner_id,
            payload=MarketplaceInventoryReservationCreate(
                listing_id=listing_id,
                inventory_copy_id=None,
                reservation_type="cart_hold",
                quantity_reserved=1,
                source="expiring_hold",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ),
        )
        expired = expire_reservations(session, owner_id=owner_id)
        listed = list_reservations(session, owner_id=owner_id, limit=20, offset=0)

        assert len(expired) == 1
        assert expired[0].id == created.id
        assert expired[0].status == "EXPIRED"
        assert listed.items[0].status == "EXPIRED"
