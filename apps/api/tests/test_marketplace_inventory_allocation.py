from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace_sync import MarketplaceInventoryReservation
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.marketplace_sync import MarketplaceInventoryReservationCreate, MarketplaceOrderCreate, MarketplaceOrderItemCreate
from app.services.marketplace_inventory_reservations import create_reservation
from app.services.marketplace_listings import create_listing
from app.services.marketplace_orders import create_order
from test_inventory import register_and_login


def _setup_listing(client: TestClient, email: str, *, quantity: int = 2) -> tuple[int, int]:
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Allocation Listing",
                listing_description="Allocation test listing",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="18.00",
                currency="USD",
                quantity=quantity,
            ),
        )
        return int(owner.id or 0), listing.listing.id


def test_marketplace_inventory_allocation_prevents_overselling(client: TestClient) -> None:
    owner_id, listing_id = _setup_listing(client, "allocation-owner@example.com", quantity=2)

    with Session(get_engine()) as session:
        create_reservation(
            session,
            owner_id=owner_id,
            payload=MarketplaceInventoryReservationCreate(
                listing_id=listing_id,
                inventory_copy_id=None,
                reservation_type="cart_hold",
                quantity_reserved=1,
                source="preexisting_hold",
                expires_at=None,
            ),
        )
        first = create_order(
            session,
            owner_id=owner_id,
            payload=MarketplaceOrderCreate(
                buyer_name="Buyer One",
                buyer_email="buyer-one@example.com",
                shipping_amount="0.00",
                tax_amount="0.00",
                currency="USD",
                items=[
                    MarketplaceOrderItemCreate(
                        listing_id=listing_id,
                        inventory_copy_id=None,
                        external_item_id=None,
                        title="Allocated Item",
                        quantity=1,
                        unit_price="18.00",
                    )
                ],
            ),
        )
        active_reservations = session.exec(
            select(MarketplaceInventoryReservation)
            .where(MarketplaceInventoryReservation.owner_id == owner_id)
            .where(MarketplaceInventoryReservation.status == "ACTIVE")
        ).all()

        assert first.order.order_status == "PENDING"
        assert len(active_reservations) == 2

        try:
            create_order(
                session,
                owner_id=owner_id,
                payload=MarketplaceOrderCreate(
                    buyer_name="Buyer Two",
                    buyer_email="buyer-two@example.com",
                    shipping_amount="0.00",
                    tax_amount="0.00",
                    currency="USD",
                    items=[
                        MarketplaceOrderItemCreate(
                            listing_id=listing_id,
                            inventory_copy_id=None,
                            external_item_id=None,
                            title="Oversell Item",
                            quantity=1,
                            unit_price="18.00",
                        )
                    ],
                ),
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "available" in exc.detail.lower()
        else:
            raise AssertionError("Expected oversell attempt to fail.")
