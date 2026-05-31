from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.db.session import get_engine
from app.models import AgentDefinition, User
from app.models.marketplace_sync import MarketplaceInventoryReservation
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.marketplace_sync import MarketplaceInventoryReservationCreate
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.inventory_health_agent import run_inventory_health_agent
from app.services.marketplace_inventory_reservations import create_reservation
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def _enable_agent(session: Session, code: str) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def test_inventory_health_agent_detects_stale_reservations(client: TestClient) -> None:
    register_and_login(client, "inventory-health-agent@example.com")
    with Session(get_engine()) as session:
        _enable_agent(session, "inventory_health_agent")
        owner = session.exec(select(User).where(User.email == "inventory-health-agent@example.com")).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Health Listing",
                listing_description="desc",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="10.00",
                currency="USD",
                quantity=3,
            ),
        )
        create_reservation(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceInventoryReservationCreate(
                listing_id=listing.listing.id,
                inventory_copy_id=None,
                reservation_type="cart_hold",
                quantity_reserved=1,
                source="stale-test",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
        )
        reservations_before = len(session.exec(select(MarketplaceInventoryReservation)).all())
        result = run_inventory_health_agent(session, owner_user_id=int(owner.id or 0))
        reservations_after = len(session.exec(select(MarketplaceInventoryReservation)).all())
        assert reservations_before == reservations_after
        assert any(row.recommendation_type == "INVENTORY_HEALTH" for row in result.recommendations)
