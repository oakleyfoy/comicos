from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketTrend, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.market_signal_agent import collect_market_signals
from app.services.market_snapshot_agent import run_snapshot_agent
from app.services.market_trend_agent import calculate_market_strength, calculate_market_trends
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_market_trend_agent_generates_trends_without_forecasts(client: TestClient) -> None:
    email = "market-trend-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = _owner_id(session, email)
        first_listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Trend Listing One",
                listing_description="Trend test one",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="10.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=first_listing.listing.id)
        collect_market_signals(session, owner_user_id=owner_id)
        run_snapshot_agent(session, owner_user_id=owner_id)

        second_listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Trend Listing Two",
                listing_description="Trend test two",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="35.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=second_listing.listing.id)
        collect_market_signals(session, owner_user_id=owner_id)
        run_snapshot_agent(session, owner_user_id=owner_id)

        result = calculate_market_trends(session, owner_user_id=owner_id)
        strength = calculate_market_strength(session, owner_user_id=owner_id)
        rows = session.exec(select(MarketTrend).where(MarketTrend.owner_user_id == owner_id)).all()

        assert result.execution.status == "COMPLETED"
        assert result.created_count >= 1
        assert rows
        assert strength["snapshot_count"] >= 2
        assert all("forecast" not in row.trend_type.lower() for row in result.trends)
