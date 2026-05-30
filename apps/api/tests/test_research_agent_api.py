from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.models import AgentExecution
from test_inventory import auth_headers, register_and_login
from test_marketplace_research_agent import _seed_marketplace_inventory
from test_new_release_research_agent import _seed_release_inventory


def _enable_research_agents(session: Session) -> None:
    seed_foundational_agents(session)
    for code in ("marketplace_research_agent", "new_release_research_agent"):
        row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
        assert row is not None and row.id is not None
        enable_agent(session, agent_id=int(row.id))
        grant_agent_execute(session, agent_id=int(row.id))


def test_research_agent_api_routes_scope_results_and_allow_review_status_only(
    client: TestClient,
    session: Session,
) -> None:
    _enable_research_agents(session)

    owner_email = "research-api-owner@example.com"
    other_email = "research-api-other@example.com"
    owner_token = register_and_login(client, owner_email)
    other_token = register_and_login(client, other_email)

    _seed_marketplace_inventory(client, session, email=owner_email)
    _seed_release_inventory(client, session, email=other_email)

    execution_count_before = len(session.exec(select(AgentExecution)).all())

    marketplace_run = client.post(
        "/api/v1/research-agents/marketplace/run",
        headers=auth_headers(owner_token),
    )
    assert marketplace_run.status_code == 201, marketplace_run.text
    marketplace_data = marketplace_run.json()["data"]
    snapshot_id = marketplace_data["snapshot"]["id"]
    finding_id = marketplace_data["findings"][0]["id"]
    execution_id = marketplace_data["snapshot"]["agent_execution_id"]
    assert marketplace_data["snapshot"]["status"] == "COMPLETED"

    new_release_run = client.post(
        "/api/v1/research-agents/new-releases/run",
        headers=auth_headers(other_token),
    )
    assert new_release_run.status_code == 201, new_release_run.text
    assert len(session.exec(select(AgentExecution)).all()) == execution_count_before + 2

    listing = client.get("/api/v1/research-snapshots?limit=20&offset=0", headers=auth_headers(owner_token))
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["data"]["items"]] == [snapshot_id]

    detail = client.get(f"/api/v1/research-snapshots/{snapshot_id}", headers=auth_headers(owner_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["snapshot"]["agent_execution_id"] == execution_id

    findings = client.get("/api/v1/research-findings?limit=50&offset=0", headers=auth_headers(owner_token))
    assert findings.status_code == 200, findings.text
    assert finding_id in [row["id"] for row in findings.json()["data"]["items"]]

    finding_detail = client.get(f"/api/v1/research-findings/{finding_id}", headers=auth_headers(owner_token))
    assert finding_detail.status_code == 200, finding_detail.text
    assert finding_detail.json()["data"]["evidence"]

    reviewed = client.post(
        f"/api/v1/research-findings/{finding_id}/reviewed",
        headers=auth_headers(owner_token),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["status"] == "REVIEWED"

    dismissed = client.post(
        f"/api/v1/research-findings/{finding_id}/dismissed",
        headers=auth_headers(owner_token),
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["data"]["status"] == "DISMISSED"

    other_listing = client.get("/api/v1/research-snapshots?limit=20&offset=0", headers=auth_headers(other_token))
    assert other_listing.status_code == 200, other_listing.text
    assert snapshot_id not in [row["id"] for row in other_listing.json()["data"]["items"]]

    other_detail = client.get(f"/api/v1/research-snapshots/{snapshot_id}", headers=auth_headers(other_token))
    assert other_detail.status_code == 404, other_detail.text
    other_finding = client.get(f"/api/v1/research-findings/{finding_id}", headers=auth_headers(other_token))
    assert other_finding.status_code == 404, other_finding.text
