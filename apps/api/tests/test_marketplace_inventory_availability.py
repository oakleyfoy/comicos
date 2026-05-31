from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.marketplace_sync import MarketplaceInventoryReservationCreate, MarketplaceOrderCreate, MarketplaceOrderItemCreate
from app.services.marketplace_inventory_availability import calculate_availability, get_availability
from app.services.marketplace_inventory_reservations import create_reservation
from app.services.marketplace_listings import create_listing
from app.services.marketplace_orders import create_order, mark_order_fulfilled, mark_order_paid
from test_inventory import register_and_login


def _setup_listing(client: TestClient, email: str, *, quantity: int = 5) -> tuple[int, int]:
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Availability Listing",
                listing_description="Availability test listing",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="15.00",
                currency="USD",
                quantity=quantity,
            ),
        )
        return int(owner.id or 0), listing.listing.id


def test_marketplace_inventory_availability_calculation_uses_reservations_and_sold_items(client: TestClient) -> None:
    owner_id, listing_id = _setup_listing(client, "availability-owner@example.com", quantity=5)

    with Session(get_engine()) as session:
        create_reservation(
            session,
            owner_id=owner_id,
            payload=MarketplaceInventoryReservationCreate(
                listing_id=listing_id,
                inventory_copy_id=None,
                reservation_type="cart_hold",
                quantity_reserved=2,
                source="cart_hold",
                expires_at=None,
            ),
        )
        order = create_order(
            session,
            owner_id=owner_id,
            payload=MarketplaceOrderCreate(
                buyer_name="Buyer One",
                buyer_email="buyer@example.com",
                shipping_amount="0.00",
                tax_amount="0.00",
                currency="USD",
                items=[
                    MarketplaceOrderItemCreate(
                        listing_id=listing_id,
                        inventory_copy_id=None,
                        external_item_id=None,
                        title="Availability Item",
                        quantity=1,
                        unit_price="15.00",
                    )
                ],
            ),
        )
        mark_order_paid(session, owner_id=owner_id, order_id=order.order.id)
        mark_order_fulfilled(session, owner_id=owner_id, order_id=order.order.id)

        calculated = calculate_availability(session, owner_id=owner_id, listing_id=listing_id)
        latest = get_availability(session, owner_id=owner_id, listing_id=listing_id)

        assert calculated.total_quantity == 5
        assert calculated.reserved_quantity == 2
        assert calculated.sold_quantity == 1
        assert calculated.available_quantity == 2
        assert latest.available_quantity == 2
