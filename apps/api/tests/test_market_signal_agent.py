from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketAgentExecution, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.whatnot import WhatnotConnectRequest
from app.services.market_signal_agent import collect_market_signals
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_accounts import connect_account
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_market_signal_agent_generates_append_only_signals(client: TestClient) -> None:
    email = "market-signal-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, email)
        connect_account(
            session,
            owner_id=owner_id,
            payload=WhatnotConnectRequest(
                account_name="Signal Shop",
                account_identifier="market-signal-agent",
                api_token="whatnot_valid_signal_agent",
            ),
        )
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Signal Listing",
                listing_description="Signal test listing",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="19.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=listing.listing.id)

        before = len(session.exec(select(MarketSignal).where(MarketSignal.owner_user_id == owner_id)).all())
        first = collect_market_signals(session, owner_user_id=owner_id)
        second = collect_market_signals(session, owner_user_id=owner_id)
        all_rows = session.exec(select(MarketSignal).where(MarketSignal.owner_user_id == owner_id)).all()
        executions = session.exec(select(MarketAgentExecution).where(MarketAgentExecution.owner_user_id == owner_id)).all()

        assert first.execution.status == "COMPLETED"
        assert first.created_count >= 2
        assert len(all_rows) == before + first.created_count + second.created_count
        assert len(executions) >= 2
        assert all("forecast" not in row.signal_type.lower() for row in first.signals)
        assert all("recommend" not in row.signal_type.lower() for row in first.signals)
