from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_analytics import get_marketplace_analytics
from app.services.marketplace_listings import create_listing
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_marketplace_analytics_aggregates_owner_data(client: TestClient) -> None:
    register_and_login(client, "marketplace-analytics@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "marketplace-analytics@example.com")
        create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Analytics Listing",
                listing_description="Dashboard analytics test",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="12.00",
                currency="USD",
                quantity=1,
            ),
        )
        analytics = get_marketplace_analytics(session, owner_id=owner_id)

        assert analytics.marketplace_activity_counts["listings_total"] >= 1
        assert "DRAFT" in analytics.listings_by_status or len(analytics.listings_by_status) >= 1
        assert analytics.generated_at
