from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, User, WorkflowDefinition
from app.services.agent_execution import complete_execution, fail_execution, start_execution
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


def test_agent_dashboard_routes_aggregate_health_queue_and_execution_visibility(
    client: TestClient,
    session: Session,
) -> None:
    seed_foundational_agents(session)
    seed_foundational_workflows(session)
    _enable_intelligence_agents(session)

    inventory_agent_id = _agent_id(session, "inventory_agent")
    enable_agent(session, agent_id=inventory_agent_id)
    grant_agent_execute(session, agent_id=inventory_agent_id)
    workflow_id = _workflow_id(session, "inventory_refresh_workflow")
    enable_workflow(session, workflow_id=workflow_id)

    owner_email = "agent-dashboard-owner@example.com"
    other_email = "agent-dashboard-other@example.com"
    owner_token = register_and_login(client, owner_email)
    other_token = register_and_login(client, other_email)
    owner_row = session.exec(select(User).where(User.email == owner_email)).first()
    other_row = session.exec(select(User).where(User.email == other_email)).first()
    assert owner_row is not None and owner_row.id is not None
    assert other_row is not None and other_row.id is not None
    owner_id = int(owner_row.id)
    other_id = int(other_row.id)

    _seed_marketplace_inventory(client, session, email=owner_email)
    _seed_catalog_inventory(client, session, email=owner_email)

    running_execution = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="dashboard:manual",
    )
    successful_execution = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="dashboard:manual",
    )
    complete_execution(session, execution_id=successful_execution.execution.id)
    failed_execution = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="dashboard:manual",
    )
    fail_execution(session, execution_id=failed_execution.execution.id, event_payload_json={"reason": "dashboard-test"})

    other_running = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(other_id),
        trigger_source="dashboard:manual",
    )
    assert other_running.execution.id is not None

    workflow_detail = start_workflow(
        session,
        workflow_id=workflow_id,
        triggered_by=str(owner_id),
        trigger_source="dashboard:workflow",
    )
    workflow_execution_id = workflow_detail.execution.id
    step_running = execute_step(session, workflow_execution_id=workflow_execution_id)
    completed_workflow = complete_step(
        session,
        workflow_step_execution_id=step_running.step_executions[0].id,
        event_payload_json={"source": "dashboard-test"},
    )
    assert completed_workflow.execution.status == "COMPLETED"
    post_workflow_failure = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="dashboard:manual",
    )
    fail_execution(
        session,
        execution_id=post_workflow_failure.execution.id,
        event_payload_json={"reason": "post-workflow-failure"},
    )

    pricing_run = client.post("/api/v1/intelligence/pricing-agent/run", headers=auth_headers(owner_token))
    assert pricing_run.status_code == 201, pricing_run.text
    catalog_run = client.post("/api/v1/intelligence/catalog-agent/run", headers=auth_headers(owner_token))
    assert catalog_run.status_code == 201, catalog_run.text
    pricing_recommendation_id = pricing_run.json()["data"]["recommendations"][0]["id"]

    reviewed = client.post(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}/reviewed",
        headers=auth_headers(owner_token),
    )
    assert reviewed.status_code == 200, reviewed.text

    summary_response = client.get("/api/v1/agent-dashboard", headers=auth_headers(owner_token))
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()["data"]
    assert summary["total_agents"] >= 6
    assert summary["enabled_agents"] >= 3
    assert summary["total_workflows"] >= 4
    assert summary["active_executions"] == 1
    assert summary["total_research_snapshots"] == 2
    assert summary["total_recommendations"] >= 2
    assert summary["recommendations_awaiting_review"] >= 1

    other_summary = client.get("/api/v1/agent-dashboard", headers=auth_headers(other_token))
    assert other_summary.status_code == 200, other_summary.text
    assert other_summary.json()["data"]["active_executions"] == 1
    assert other_summary.json()["data"]["total_recommendations"] == 0

    agent_health_response = client.get("/api/v1/agent-dashboard/agents?limit=50&offset=0", headers=auth_headers(owner_token))
    assert agent_health_response.status_code == 200, agent_health_response.text
    agent_items = {
        row["agent_code"]: row for row in agent_health_response.json()["data"]["items"]
    }
    assert agent_items["inventory_agent"]["execution_count"] >= 5
    assert agent_items["inventory_agent"]["failure_count"] >= 1
    assert agent_items["inventory_agent"]["health_status"] == "FAILED"
    assert agent_items["pricing_intelligence_agent"]["success_count"] >= 1
    assert agent_items["pricing_intelligence_agent"]["health_status"] == "HEALTHY"

    workflow_health_response = client.get(
        "/api/v1/agent-dashboard/workflows?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert workflow_health_response.status_code == 200, workflow_health_response.text
    workflow_items = {
        row["workflow_code"]: row for row in workflow_health_response.json()["data"]["items"]
    }
    assert workflow_items["inventory_refresh_workflow"]["success_count"] >= 1
    assert workflow_items["inventory_refresh_workflow"]["health_status"] == "HEALTHY"

    execution_response = client.get(
        "/api/v1/agent-dashboard/executions?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert execution_response.status_code == 200, execution_response.text
    execution_items = execution_response.json()["data"]["items"]
    assert execution_items
    started_at_values = [row["started_at"] for row in execution_items]
    assert started_at_values == sorted(started_at_values, reverse=True)
    assert running_execution.execution.id in [row["execution_id"] for row in execution_items]
    assert any(row["workflow_code"] == "inventory_refresh_workflow" for row in execution_items)

    workflow_execution_response = client.get(
        "/api/v1/agent-dashboard/executions?workflow_code=inventory_refresh_workflow&limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert workflow_execution_response.status_code == 200, workflow_execution_response.text
    assert workflow_execution_response.json()["data"]["items"]
    assert all(
        row["workflow_code"] == "inventory_refresh_workflow"
        for row in workflow_execution_response.json()["data"]["items"]
    )

    queue_response = client.get(
        "/api/v1/agent-dashboard/recommendations?queue_only=true&limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert queue_response.status_code == 200, queue_response.text
    queue_items = queue_response.json()["data"]["items"]
    assert queue_items
    assert pricing_recommendation_id not in [row["recommendation_id"] for row in queue_items]
    assert all(row["status"] == "OPEN" for row in queue_items)

    recent_recommendation_response = client.get(
        "/api/v1/agent-dashboard/recommendations?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert recent_recommendation_response.status_code == 200, recent_recommendation_response.text
    recent_recommendation_items = recent_recommendation_response.json()["data"]["items"]
    assert recent_recommendation_items
    assert any(row["status"] == "REVIEWED" for row in recent_recommendation_items)

    health_response = client.get("/api/v1/agent-dashboard/health", headers=auth_headers(owner_token))
    assert health_response.status_code == 200, health_response.text
    health_data = health_response.json()["data"]
    assert any(row["agent_code"] == "inventory_agent" for row in health_data["agents"])
    assert any(row["workflow_code"] == "inventory_refresh_workflow" for row in health_data["workflows"])
