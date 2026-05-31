from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.db.session import get_engine
from app.models import AgentDefinition, User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingMappingCreate
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.marketplace_accounts import create_account
from app.services.marketplace_audit_agent import run_marketplace_audit_agent
from app.services.marketplace_listing_mappings import create_mapping
from app.services.marketplace_listings import create_listing
from app.services.marketplace_registry import disable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def _enable_agent(session: Session, code: str) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def test_marketplace_audit_agent_detects_inactive_marketplace_reference(client: TestClient) -> None:
    register_and_login(client, "marketplace-audit-agent@example.com")
    with Session(get_engine()) as session:
        _enable_agent(session, "marketplace_audit_agent")
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "marketplace-audit-agent@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "EBAY")).one()
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Audit Account",
                account_identifier="audit-account",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Audit Listing",
                listing_description="desc",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="20.00",
                currency="USD",
                quantity=1,
            ),
        )
        create_mapping(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingMappingCreate(
                marketplace_id=int(marketplace.id or 0),
                marketplace_account_id=account.id,
                external_listing_id="ebay-123",
                external_url="https://example.com/ebay-123",
                sync_status="mapped",
            ),
        )
        disable_marketplace(session, marketplace_id=int(marketplace.id or 0))
        result = run_marketplace_audit_agent(session, owner_user_id=int(owner.id or 0))
        assert any(row.recommendation_type == "MARKETPLACE_AUDIT" for row in result.recommendations)
