from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, AgentExecutionEvent, WorkflowDefinition
from app.schemas.agent_workflow import WorkflowDefinitionCreate, WorkflowStepCreate
from app.services.agent_seed import seed_foundational_agents
from app.services.workflow_orchestrator import (
    complete_step,
    execute_step,
    fail_step,
    get_workflow_execution,
    list_workflow_executions,
    start_workflow,
)
from app.services.workflow_registry import create_workflow, enable_workflow, update_workflow
from app.services.agent_registry import enable_agent
from test_inventory import auth_headers, register_and_login


def _agent_id(session, code: str) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def _enabled_workflow(session, *, code: str) -> int:
    seed_foundational_agents(session)
    inventory_agent = enable_agent(session, agent_id=_agent_id(session, "inventory_agent"))
    pricing_agent = enable_agent(session, agent_id=_agent_id(session, "pricing_agent"))
    grant_agent_execute(session, agent_id=inventory_agent.id)
    grant_agent_execute(session, agent_id=pricing_agent.id)
    existing = session.exec(select(WorkflowDefinition).where(WorkflowDefinition.workflow_code == code)).first()
    if existing is not None and existing.id is not None:
        enabled = enable_workflow(session, workflow_id=int(existing.id))
        return enabled.id
    created = create_workflow(
        session,
        payload=WorkflowDefinitionCreate(
            workflow_code=code,
            workflow_name=f"{code} workflow",
            description=f"{code} workflow description",
            enabled=False,
            schedule_enabled=False,
            steps=[
                WorkflowStepCreate(
                    step_order=1,
                    agent_definition_id=_agent_id(session, "inventory_agent"),
                    step_name="InventoryAgent",
                    step_code="inventory_agent",
                    required_success=True,
                    timeout_seconds=300,
                ),
                WorkflowStepCreate(
                    step_order=2,
                    agent_definition_id=_agent_id(session, "pricing_agent"),
                    step_name="PricingAgent",
                    step_code="pricing_agent",
                    required_success=True,
                    timeout_seconds=300,
                ),
            ],
        ),
    )
    enabled = enable_workflow(session, workflow_id=created.id)
    return enabled.id


def test_workflow_orchestrator_enforces_step_order_and_completes_workflow(client, session) -> None:
    token = register_and_login(client, "workflow-execution@example.com")
    workflow_id = _enabled_workflow(session, code="pricing_refresh_test_workflow")

    started = start_workflow(
        session,
        workflow_id=workflow_id,
        triggered_by="workflow-execution@example.com",
        trigger_source="manual",
    )
    execution_id = started.execution.id
    assert started.execution.status == "RUNNING"
    assert started.step_executions == []

    first_step_detail = execute_step(session, workflow_execution_id=execution_id)
    assert [row.status for row in first_step_detail.step_executions] == ["RUNNING"]
    first_step_execution_id = first_step_detail.step_executions[0].id
    first_agent_execution_id = first_step_detail.step_executions[0].agent_execution_id

    try:
        execute_step(session, workflow_execution_id=execution_id)
    except HTTPException as exc:
        assert exc.status_code == 409
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected concurrent step start to be rejected.")

    after_first_complete = complete_step(
        session,
        workflow_step_execution_id=first_step_execution_id,
        event_payload_json={"result": "ok"},
    )
    assert after_first_complete.execution.status == "RUNNING"
    assert [row.status for row in after_first_complete.step_executions] == ["COMPLETED"]

    second_step_detail = execute_step(session, workflow_execution_id=execution_id)
    assert [row.status for row in second_step_detail.step_executions] == ["COMPLETED", "RUNNING"]
    second_step_execution_id = second_step_detail.step_executions[-1].id
    second_agent_execution_id = second_step_detail.step_executions[-1].agent_execution_id

    finished = complete_step(
        session,
        workflow_step_execution_id=second_step_execution_id,
        event_payload_json={"result": "ok"},
    )
    assert finished.execution.status == "COMPLETED"
    assert [row.status for row in finished.step_executions] == ["COMPLETED", "COMPLETED"]

    workflow_events = session.exec(
        select(AgentExecutionEvent.event_type)
        .where(AgentExecutionEvent.execution_id == first_agent_execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()
    assert list(workflow_events) == [
        "execution_started",
        "workflow_started",
        "step_started",
        "step_completed",
        "execution_completed",
    ]

    terminal_events = session.exec(
        select(AgentExecutionEvent.event_type)
        .where(AgentExecutionEvent.execution_id == second_agent_execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()
    assert list(terminal_events) == [
        "execution_started",
        "step_started",
        "step_completed",
        "workflow_completed",
        "execution_completed",
    ]

    listing = client.get(
        "/api/v1/workflow-executions?execution_status=COMPLETED&limit=20&offset=0",
        headers=auth_headers(token),
    )
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["data"]["items"]] == [execution_id]

    detail = client.get(f"/api/v1/workflow-executions/{execution_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["execution"]["status"] == "COMPLETED"
    assert [row["status"] for row in detail.json()["data"]["step_executions"]] == ["COMPLETED", "COMPLETED"]


def test_workflow_orchestrator_failure_and_definition_immutability(client, session) -> None:
    del client
    workflow_id = _enabled_workflow(session, code="pricing_failure_test_workflow")
    started = start_workflow(
        session,
        workflow_id=workflow_id,
        triggered_by="system:test",
        trigger_source="scheduler",
    )
    execution_id = started.execution.id

    running = execute_step(session, workflow_execution_id=execution_id)
    step_execution_id = running.step_executions[0].id
    agent_execution_id = running.step_executions[0].agent_execution_id

    failed = fail_step(session, workflow_step_execution_id=step_execution_id, reason="timeout path")
    assert failed.execution.status == "FAILED"
    assert [row.status for row in failed.step_executions] == ["FAILED"]

    event_types = session.exec(
        select(AgentExecutionEvent.event_type)
        .where(AgentExecutionEvent.execution_id == agent_execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()
    assert list(event_types) == [
        "execution_started",
        "workflow_started",
        "step_started",
        "step_failed",
        "workflow_failed",
        "execution_failed",
    ]

    try:
        execute_step(session, workflow_execution_id=execution_id)
    except HTTPException as exc:
        assert exc.status_code == 409
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected failed workflow execution to reject later steps.")

    try:
        update_workflow(
            session,
            workflow_id=workflow_id,
            description="mutated after history",
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected workflow mutation after execution history to be rejected.")

    listed = list_workflow_executions(session, workflow_id=workflow_id, status="FAILED", limit=20, offset=0)
    assert execution_id in [row.id for row in listed.items]
    detail = get_workflow_execution(session, workflow_execution_id=execution_id)
    assert detail.execution.status == "FAILED"
