from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketSnapshot, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.market_signal_agent import collect_market_signals
from app.services.market_snapshot_agent import generate_daily_snapshot, generate_weekly_snapshot, run_snapshot_agent
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_market_snapshot_agent_generates_append_only_snapshots(client: TestClient) -> None:
    email = "market-snapshot-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = _owner_id(session, email)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Snapshot Listing",
                listing_description="Snapshot test listing",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="22.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=listing.listing.id)
        collect_market_signals(session, owner_user_id=owner_id)

        before = len(session.exec(select(MarketSnapshot).where(MarketSnapshot.owner_user_id == owner_id)).all())
        daily = generate_daily_snapshot(session, owner_user_id=owner_id)
        weekly = generate_weekly_snapshot(session, owner_user_id=owner_id)
        session.commit()
        run = run_snapshot_agent(session, owner_user_id=owner_id)
        rows = session.exec(select(MarketSnapshot).where(MarketSnapshot.owner_user_id == owner_id)).all()

        assert daily.market_score >= 0
        assert weekly.market_score >= 0
        assert run.execution.status == "COMPLETED"
        assert len(rows) == before + 3
        assert all(row.market_score <= 100 for row in rows)
