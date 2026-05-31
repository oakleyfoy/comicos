from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.db.session import get_engine
from app.models import AgentDefinition, AgentExecution, User
from app.models.marketplace_operations import MarketplaceRecommendationReview
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.marketplace_listings import create_listing
from test_inventory import auth_headers, register_and_login


def _enable_marketplace_ops_agents(session: Session) -> None:
    seed_foundational_agents(session)
    for code in (
        "listing_quality_agent",
        "inventory_health_agent",
        "pricing_opportunity_agent",
        "unsold_inventory_agent",
        "marketplace_audit_agent",
    ):
        row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
        assert row is not None and row.id is not None
        enable_agent(session, agent_id=int(row.id))
        grant_agent_execute(session, agent_id=int(row.id))


def test_marketplace_operations_api_routes_review_and_owner_scoping(client: TestClient) -> None:
    owner_token = register_and_login(client, "marketplace-ops-api-owner@example.com")
    outsider_token = register_and_login(client, "marketplace-ops-api-outsider@example.com")

    with Session(get_engine()) as session:
        _enable_marketplace_ops_agents(session)
        owner = session.exec(select(User).where(User.email == "marketplace-ops-api-owner@example.com")).one()
        executions_before = len(session.exec(select(AgentExecution)).all())
        create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="comic",
                listing_description="",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="9.00",
                currency="USD",
                quantity=1,
            ),
        )

    run = client.post("/api/v1/marketplace-operations/run/listing-quality", headers=auth_headers(owner_token))
    assert run.status_code == 201, run.text
    recommendation_id = run.json()["data"]["recommendations"][0]["id"]
    execution_id = run.json()["data"]["agent_execution_id"]

    listing = client.get("/api/v1/marketplace-operations/recommendations?limit=20&offset=0", headers=auth_headers(owner_token))
    detail = client.get(f"/api/v1/marketplace-operations/recommendations/{recommendation_id}", headers=auth_headers(owner_token))
    reviewed = client.post(
        f"/api/v1/marketplace-operations/recommendations/{recommendation_id}/reviewed",
        headers=auth_headers(owner_token),
    )
    dismissed = client.post(
        f"/api/v1/marketplace-operations/recommendations/{recommendation_id}/dismissed",
        headers=auth_headers(owner_token),
    )
    denied = client.get(f"/api/v1/marketplace-operations/recommendations/{recommendation_id}", headers=auth_headers(outsider_token))

    assert listing.status_code == 200, listing.text
    assert detail.status_code == 200, detail.text
    assert reviewed.status_code == 200, reviewed.text
    assert dismissed.status_code == 200, dismissed.text
    assert denied.status_code == 404, denied.text
    assert listing.json()["data"]["dashboard"]["total_recommendations"] >= 1
    assert detail.json()["data"]["evidence"]
    assert dismissed.json()["data"]["recommendation"]["recommendation_status"] == "DISMISSED"
    assert execution_id is not None

    with Session(get_engine()) as session:
        executions_after = len(session.exec(select(AgentExecution)).all())
        reviews = session.exec(select(MarketplaceRecommendationReview)).all()
        assert executions_after == executions_before + 1
        assert len(reviews) >= 2
