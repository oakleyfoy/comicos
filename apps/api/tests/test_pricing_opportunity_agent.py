from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.db.session import get_engine
from app.models import AgentDefinition, InventoryCopy, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.marketplace_listings import create_listing
from app.services.pricing_opportunity_agent import run_pricing_opportunity_agent
from test_inventory import create_order, register_and_login


def _enable_agent(session: Session, code: str) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def test_pricing_opportunity_agent_detects_underpriced_listing_without_mutation(client: TestClient) -> None:
    token = register_and_login(client, "pricing-opportunity-agent@example.com")
    create_order(client, token)
    with Session(get_engine()) as session:
        _enable_agent(session, "pricing_opportunity_agent")
        owner = session.exec(select(User).where(User.email == "pricing-opportunity-agent@example.com")).one()
        inventory = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner.id)).first()
        assert inventory is not None
        inventory.current_fmv = Decimal("100.00")
        session.add(inventory)
        session.commit()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Underpriced Listing",
                listing_description="desc",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="50.00",
                currency="USD",
                quantity=1,
                inventory_copy_id=int(inventory.id or 0),
            ),
        )
        price_before = listing.listing.asking_price
        result = run_pricing_opportunity_agent(session, owner_user_id=int(owner.id or 0))
        session.refresh(session.get(InventoryCopy, inventory.id))
        assert str(price_before) == "50.00"
        assert any(row.recommendation_type == "PRICING_OPPORTUNITY" for row in result.recommendations)
