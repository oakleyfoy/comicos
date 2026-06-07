from __future__ import annotations

from sqlmodel import Session

from app.models.p89_managed_listing import P89ManagedListing, utc_now
from app.services.listing_profit_service import calculate_listing_profit


def test_profit_missing_cost_basis(session: Session) -> None:
    listing = P89ManagedListing(
        owner_user_id=1,
        inventory_copy_id=999_999,
        marketplace="EBAY",
        title="Comic",
        status="SOLD",
        sale_price=40.0,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    b = calculate_listing_profit(session, listing=listing)
    assert b.cost_basis_known is False
    assert b.net_profit is None
