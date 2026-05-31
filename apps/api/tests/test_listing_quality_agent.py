from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.db.session import get_engine
from app.models import AgentDefinition, User
from app.models.marketplace_listing import MarketplaceListing
from app.models.marketplace_operations import MarketplaceRecommendationEvidence
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.listing_quality_agent import run_listing_quality_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def _enable_agent(session: Session, code: str) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def test_listing_quality_agent_generates_evidence_backed_recommendations(client: TestClient) -> None:
    register_and_login(client, "listing-quality-agent@example.com")
    with Session(get_engine()) as session:
        _enable_agent(session, "listing_quality_agent")
        owner = session.exec(select(User).where(User.email == "listing-quality-agent@example.com")).one()
        before = session.exec(select(MarketplaceListing)).all()
        create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="comic",
                listing_description="",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="12.00",
                currency="USD",
                quantity=1,
            ),
        )
        after = session.exec(select(MarketplaceListing)).all()
        assert len(after) == len(before) + 1

        result = run_listing_quality_agent(session, owner_user_id=int(owner.id or 0))
        assert result.agent_execution_id is not None
        assert result.recommendations_created >= 2
        assert all(row.recommendation_type == "LISTING_QUALITY" for row in result.recommendations)
        evidence = session.exec(select(MarketplaceRecommendationEvidence)).all()
        assert evidence
        assert len(after) == len(before) + 1
