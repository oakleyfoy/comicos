from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, AgentExecution, IntelligenceRecommendation, IntelligenceRecommendationReview, User, WorkflowDefinition
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


def test_agent_analytics_snapshot_generation_and_latest_views_are_append_only(
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

    owner_email = "agent-analytics-owner@example.com"
    other_email = "agent-analytics-other@example.com"
    owner_token = register_and_login(client, owner_email)
    other_token = register_and_login(client, other_email)
    owner_row = session.exec(select(User).where(User.email == owner_email)).first()
    assert owner_row is not None and owner_row.id is not None
    owner_id = int(owner_row.id)

    _seed_marketplace_inventory(client, session, email=owner_email)
    _seed_catalog_inventory(client, session, email=owner_email)

    completed_execution = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="analytics:manual",
    )
    complete_execution(session, execution_id=completed_execution.execution.id)
    failed_execution = start_execution(
        session,
        agent_id=inventory_agent_id,
        triggered_by=str(owner_id),
        trigger_source="analytics:manual",
    )
    fail_execution(session, execution_id=failed_execution.execution.id, event_payload_json={"reason": "analytics-test"})

    workflow_execution = start_workflow(
        session,
        workflow_id=workflow_id,
        triggered_by=str(owner_id),
        trigger_source="analytics:workflow",
    )
    running_step = execute_step(session, workflow_execution_id=workflow_execution.execution.id)
    complete_step(
        session,
        workflow_step_execution_id=running_step.step_executions[0].id,
        event_payload_json={"source": "analytics-test"},
    )

    pricing_run = client.post("/api/v1/intelligence/pricing-agent/run", headers=auth_headers(owner_token))
    assert pricing_run.status_code == 201, pricing_run.text
    pricing_data = pricing_run.json()["data"]
    pricing_recommendation_id = pricing_data["recommendations"][0]["id"]
    pricing_recommendation_type = pricing_data["recommendations"][0]["recommendation_type"]

    catalog_run = client.post("/api/v1/intelligence/catalog-agent/run", headers=auth_headers(owner_token))
    assert catalog_run.status_code == 201, catalog_run.text
    catalog_data = catalog_run.json()["data"]
    catalog_recommendation_id = catalog_data["recommendations"][0]["id"]
    catalog_recommendation_type = catalog_data["recommendations"][0]["recommendation_type"]

    accepted = client.post(
        f"/api/v1/intelligence/recommendations/{pricing_recommendation_id}/accepted",
        headers=auth_headers(owner_token),
    )
    assert accepted.status_code == 200, accepted.text
    dismissed = client.post(
        f"/api/v1/intelligence/recommendations/{catalog_recommendation_id}/dismissed",
        headers=auth_headers(owner_token),
    )
    assert dismissed.status_code == 200, dismissed.text

    execution_count_before = len(session.exec(select(AgentExecution)).all())
    recommendation_count_before = len(session.exec(select(IntelligenceRecommendation)).all())
    review_count_before = len(session.exec(select(IntelligenceRecommendationReview)).all())

    first_generate = client.post("/api/v1/agent-analytics/generate", headers=auth_headers(owner_token))
    assert first_generate.status_code == 201, first_generate.text
    first_detail = first_generate.json()["data"]
    assert first_detail["snapshot"]["id"] is not None
    assert first_detail["agent_metrics"]
    assert first_detail["workflow_metrics"]
    assert first_detail["recommendation_metrics"]
    assert first_detail["snapshot"]["summary_json"]["recommendation_acceptance_rate"] > 0

    workflow_metrics = {
        row["workflow_code"]: row
        for row in first_detail["workflow_metrics"]
    }
    assert workflow_metrics["inventory_refresh_workflow"]["executions_total"] >= 1
    assert workflow_metrics["inventory_refresh_workflow"]["executions_completed"] >= 1

    recommendation_metrics = {
        row["recommendation_type"]: row
        for row in first_detail["recommendation_metrics"]
    }
    assert recommendation_metrics[pricing_recommendation_type]["accepted_total"] >= 1
    assert recommendation_metrics[catalog_recommendation_type]["dismissed_total"] >= 1

    assert len(session.exec(select(AgentExecution)).all()) == execution_count_before
    assert len(session.exec(select(IntelligenceRecommendation)).all()) == recommendation_count_before
    assert len(session.exec(select(IntelligenceRecommendationReview)).all()) == review_count_before

    second_generate = client.post("/api/v1/agent-analytics/generate", headers=auth_headers(owner_token))
    assert second_generate.status_code == 201, second_generate.text
    second_snapshot_id = second_generate.json()["data"]["snapshot"]["id"]
    assert second_snapshot_id != first_detail["snapshot"]["id"]

    summary_response = client.get("/api/v1/agent-analytics", headers=auth_headers(owner_token))
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()["data"]
    assert summary["latest_snapshot"]["id"] == second_snapshot_id
    assert summary["agent_metric_count"] >= 1
    assert summary["workflow_metric_count"] >= 1
    assert summary["recommendation_metric_count"] >= 1

    snapshots_response = client.get("/api/v1/agent-analytics/snapshots?limit=10&offset=0", headers=auth_headers(owner_token))
    assert snapshots_response.status_code == 200, snapshots_response.text
    snapshot_items = snapshots_response.json()["data"]["items"]
    assert len(snapshot_items) == 2
    generated_order = [row["generated_at"] for row in snapshot_items]
    assert generated_order == sorted(generated_order, reverse=True)
    assert snapshot_items[0]["id"] == second_snapshot_id

    detail_response = client.get(
        f"/api/v1/agent-analytics/snapshots/{second_snapshot_id}",
        headers=auth_headers(owner_token),
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["data"]["snapshot"]["id"] == second_snapshot_id

    agent_metrics_response = client.get("/api/v1/agent-analytics/agents", headers=auth_headers(owner_token))
    assert agent_metrics_response.status_code == 200, agent_metrics_response.text
    assert any(row["agent_code"] == "inventory_agent" for row in agent_metrics_response.json()["data"]["items"])

    workflow_metrics_response = client.get("/api/v1/agent-analytics/workflows", headers=auth_headers(owner_token))
    assert workflow_metrics_response.status_code == 200, workflow_metrics_response.text
    assert any(
        row["workflow_code"] == "inventory_refresh_workflow"
        for row in workflow_metrics_response.json()["data"]["items"]
    )

    recommendation_metrics_response = client.get("/api/v1/agent-analytics/recommendations", headers=auth_headers(owner_token))
    assert recommendation_metrics_response.status_code == 200, recommendation_metrics_response.text
    assert any(
        row["recommendation_type"] == pricing_recommendation_type
        for row in recommendation_metrics_response.json()["data"]["items"]
    )

    other_summary = client.get("/api/v1/agent-analytics", headers=auth_headers(other_token))
    assert other_summary.status_code == 200, other_summary.text
    assert other_summary.json()["data"]["latest_snapshot"] is None

    other_detail = client.get(
        f"/api/v1/agent-analytics/snapshots/{second_snapshot_id}",
        headers=auth_headers(other_token),
    )
    assert other_detail.status_code == 404, other_detail.text
