from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute, grant_agent_review
from app.models import AgentDefinition, AgentExecution, IntelligenceRecommendation, ResearchSnapshot
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from test_catalog_intelligence_agent import _seed_catalog_inventory
from test_inventory import auth_headers, register_and_login
from test_marketplace_research_agent import _seed_marketplace_inventory


def _enable_intelligence_agents(session: Session) -> None:
    seed_foundational_agents(session)
    for code in ("pricing_intelligence_agent", "catalog_intelligence_agent"):
        row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
        assert row is not None and row.id is not None
        enable_agent(session, agent_id=int(row.id))
        grant_agent_execute(session, agent_id=int(row.id))
        grant_agent_review(session, agent_id=int(row.id), admin=True)


def test_intelligence_api_routes_are_owner_scoped_and_reviewable(
    client: TestClient,
    session: Session,
) -> None:
    _enable_intelligence_agents(session)

    pricing_email = "intelligence-api-pricing@example.com"
    catalog_email = "intelligence-api-catalog@example.com"
    pricing_token = register_and_login(client, pricing_email)
    catalog_token = register_and_login(client, catalog_email)

    _seed_marketplace_inventory(client, session, email=pricing_email)
    _seed_catalog_inventory(client, session, email=catalog_email)

    execution_count_before = len(session.exec(select(AgentExecution)).all())
    snapshot_count_before = len(session.exec(select(ResearchSnapshot)).all())
    recommendation_count_before = len(session.exec(select(IntelligenceRecommendation)).all())

    pricing_run = client.post("/api/v1/intelligence/pricing-agent/run", headers=auth_headers(pricing_token))
    assert pricing_run.status_code == 201, pricing_run.text
    pricing_data = pricing_run.json()["data"]
    pricing_snapshot_id = pricing_data["snapshot"]["id"]
    pricing_recommendation_id = pricing_data["recommendations"][0]["id"]
    assert pricing_data["recommendations"]

    catalog_run = client.post("/api/v1/intelligence/catalog-agent/run", headers=auth_headers(catalog_token))
    assert catalog_run.status_code == 201, catalog_run.text
    catalog_data = catalog_run.json()["data"]
    assert catalog_data["recommendations"]

    assert len(session.exec(select(AgentExecution)).all()) == execution_count_before + 2
    assert len(session.exec(select(ResearchSnapshot)).all()) == snapshot_count_before + 2
    assert len(session.exec(select(IntelligenceRecommendation)).all()) > recommendation_count_before

    types_response = client.get("/api/v1/intelligence/recommendations/types", headers=auth_headers(pricing_token))
    assert types_response.status_code == 200, types_response.text
    assert {"underpriced_inventory", "missing_metadata"} <= set(types_response.json()["data"]["items"])

    pricing_list = client.get("/api/v1/intelligence/recommendations?limit=100&offset=0", headers=auth_headers(pricing_token))
    assert pricing_list.status_code == 200, pricing_list.text
    pricing_ids = [row["id"] for row in pricing_list.json()["data"]["items"]]
    assert pricing_recommendation_id in pricing_ids

    pricing_detail = client.get(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}",
        headers=auth_headers(pricing_token),
    )
    assert pricing_detail.status_code == 200, pricing_detail.text
    assert pricing_detail.json()["data"]["evidence"]

    reviewed = client.post(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}/reviewed",
        headers=auth_headers(pricing_token),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["recommendation"]["status"] == "REVIEWED"

    dismissed = client.post(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}/dismissed",
        headers=auth_headers(pricing_token),
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["data"]["recommendation"]["status"] == "DISMISSED"

    accepted = client.post(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}/accepted",
        headers=auth_headers(pricing_token),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["recommendation"]["status"] == "ACCEPTED"
    assert len(accepted.json()["data"]["reviews"]) == 3

    other_detail = client.get(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}",
        headers=auth_headers(catalog_token),
    )
    assert other_detail.status_code == 404, other_detail.text

    other_snapshot_listing = client.get(
        "/api/v1/intelligence/recommendations?limit=100&offset=0",
        headers=auth_headers(catalog_token),
    )
    assert other_snapshot_listing.status_code == 200, other_snapshot_listing.text
    assert pricing_recommendation_id not in [row["id"] for row in other_snapshot_listing.json()["data"]["items"]]
    assert pricing_snapshot_id is not None
