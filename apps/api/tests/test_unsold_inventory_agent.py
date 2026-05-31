from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.db.session import get_engine
from app.models import AgentDefinition, User
from app.models.marketplace_listing import MarketplaceListing
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.marketplace_listings import create_listing
from app.services.unsold_inventory_agent import run_unsold_inventory_agent
from test_inventory import register_and_login


def _enable_agent(session: Session, code: str) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def test_unsold_inventory_agent_detects_unmapped_listings(client: TestClient) -> None:
    register_and_login(client, "unsold-inventory-agent@example.com")
    with Session(get_engine()) as session:
        _enable_agent(session, "unsold_inventory_agent")
        owner = session.exec(select(User).where(User.email == "unsold-inventory-agent@example.com")).one()
        detail = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Unsold Listing",
                listing_description="desc",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="14.00",
                currency="USD",
                quantity=1,
            ),
        )
        row = session.get(MarketplaceListing, detail.listing.id)
        assert row is not None
        row.created_at = datetime.now(timezone.utc) - timedelta(days=45)
        row.status = "READY"
        session.add(row)
        session.commit()
        result = run_unsold_inventory_agent(session, owner_user_id=int(owner.id or 0))
        assert any(row.recommendation_type == "UNSOLD_INVENTORY" for row in result.recommendations)
