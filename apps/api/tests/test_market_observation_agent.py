from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketObservation, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.market_observation_agent import generate_market_observations
from app.services.market_signal_agent import collect_market_signals
from app.services.market_snapshot_agent import run_snapshot_agent
from app.services.market_trend_agent import calculate_market_trends
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_market_observation_agent_generates_observations_only(client: TestClient) -> None:
    email = "market-observation-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = _owner_id(session, email)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Observation Listing",
                listing_description="Observation test listing",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="28.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=listing.listing.id)
        collect_market_signals(session, owner_user_id=owner_id)
        run_snapshot_agent(session, owner_user_id=owner_id)
        collect_market_signals(session, owner_user_id=owner_id)
        run_snapshot_agent(session, owner_user_id=owner_id)
        calculate_market_trends(session, owner_user_id=owner_id)

        result = generate_market_observations(session, owner_user_id=owner_id)
        rows = session.exec(select(MarketObservation).where(MarketObservation.owner_user_id == owner_id)).all()

        assert result.execution.status == "COMPLETED"
        assert result.created_count >= 1
        assert rows
        assert all(row.created_by_agent == "market_observation_agent" for row in rows)
        for row in result.observations:
            lowered = f"{row.title} {row.description}".lower()
            assert "recommend" not in lowered
            assert "buy" not in lowered
            assert "sell" not in lowered
