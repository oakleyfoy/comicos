from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, User, WorkflowDefinition
from app.services.agent_analytics import generate_snapshot
from app.services.agent_execution import complete_execution, start_execution
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.workflow_orchestrator import complete_step, execute_step, start_workflow
from app.services.workflow_registry import enable_workflow
from app.services.workflow_seed import seed_foundational_workflows
from test_catalog_intelligence_agent import _seed_catalog_inventory
from test_intelligence_api import _enable_intelligence_agents
from test_inventory import auth_headers, register_and_login
from test_marketplace_research_agent import _seed_marketplace_inventory


def _agent_id(session: Session, code: str) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def _workflow_id(session: Session, workflow_code: str) -> int:
    row = session.exec(select(WorkflowDefinition).where(WorkflowDefinition.workflow_code == workflow_code)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def test_agent_platform_readiness_validation_and_summary_routes_reflect_owner_scoped_state(
    client: TestClient,
    session: Session,
) -> None:
    seed_foundational_agents(session)
    seed_foundational_workflows(session)
    _enable_intelligence_agents(session)

    inventory_agent_id = _agent_id(session, "inventory_agent")
    workflow_id = _workflow_id(session, "inventory_refresh_workflow")
    enable_agent(session, agent_id=inventory_agent_id)
    enable_workflow(session, workflow_id=workflow_id)
    grant_agent_execute(session, agent_id=inventory_agent_id)

    owner_email = "agent-platform-owner@example.com"
    other_email = "agent-platform-other@example.com"
    owner_token = register_and_login(client, owner_email)
    other_token = register_and_login(client, other_email)
    owner_row = session.exec(select(User).where(User.email == owner_email)).first()
    other_row = session.exec(select(User).where(User.email == other_email)).first()
    assert owner_row is not None and owner_row.id is not None
    assert other_row is not None and other_row.id is not None
    owner_id = int(owner_row.id)

    _seed_marketplace_inventory(client, session, email=owner_email)
    _seed_catalog_inventory(client, session, email=owner_email)

    execution = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="platform:manual",
    )
    complete_execution(session, execution_id=execution.execution.id)

    workflow_execution = start_workflow(
        session,
        workflow_id=workflow_id,
        triggered_by=str(owner_id),
        trigger_source="platform:workflow",
    )
    running_step = execute_step(session, workflow_execution_id=workflow_execution.execution.id)
    complete_step(
        session,
        workflow_step_execution_id=running_step.step_executions[0].id,
        event_payload_json={"source": "platform-test"},
    )

    pricing_run = client.post("/api/v1/intelligence/pricing-agent/run", headers=auth_headers(owner_token))
    assert pricing_run.status_code == 201, pricing_run.text
    pricing_recommendation_id = pricing_run.json()["data"]["recommendations"][0]["id"]
    accepted = client.post(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}/accepted",
        headers=auth_headers(owner_token),
    )
    assert accepted.status_code == 200, accepted.text

    generate_snapshot(session, owner_user_id=owner_id)

    summary_response = client.get("/api/v1/agent-platform/summary", headers=auth_headers(owner_token))
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()["data"]
    assert summary["overall_status"] == "PASS"
    assert summary["validation_status"] == "PASS"
    assert summary["security_status"] == "PASS"
    assert summary["analytics_status"] == "PASS"
    assert summary["recommendation_engine_status"] == "PASS"
    assert summary["workflow_status"] == "PASS"

    validation_response = client.get("/api/v1/agent-platform/validation", headers=auth_headers(owner_token))
    assert validation_response.status_code == 200, validation_response.text
    validation = validation_response.json()["data"]
    assert validation["overall_status"] == "PASS"
    check_statuses = {row["check_code"]: row["status"] for row in validation["checks"]}
    assert check_statuses["agents"] == "PASS"
    assert check_statuses["workflows"] == "PASS"
    assert check_statuses["permissions"] == "PASS"
    assert check_statuses["recommendations"] == "PASS"
    assert check_statuses["dashboard"] == "PASS"
    assert check_statuses["analytics"] == "PASS"

    readiness_response = client.get("/api/v1/agent-platform/readiness", headers=auth_headers(owner_token))
    assert readiness_response.status_code == 200, readiness_response.text
    readiness = readiness_response.json()["data"]
    assert readiness["report_name"] == "Agent Platform Readiness Report"
    assert readiness["overall_status"] == "PASS"
    section_statuses = {row["section_code"]: row["status"] for row in readiness["sections"]}
    assert section_statuses["agent_registry"] == "PASS"
    assert section_statuses["workflow_engine"] == "PASS"
    assert section_statuses["research_agents"] == "PASS"
    assert section_statuses["intelligence_agents"] == "PASS"
    assert section_statuses["dashboard"] == "PASS"
    assert section_statuses["security"] == "PASS"
    assert section_statuses["analytics"] == "PASS"
    assert section_statuses["test_coverage"] == "PASS"

    other_readiness = client.get("/api/v1/agent-platform/readiness", headers=auth_headers(other_token))
    assert other_readiness.status_code == 200, other_readiness.text
    other_sections = {row["section_code"]: row for row in other_readiness.json()["data"]["sections"]}
    assert other_sections["research_agents"]["details_json"]["research_snapshot_count"] == 0
    assert other_sections["intelligence_agents"]["details_json"]["recommendation_count"] == 0
