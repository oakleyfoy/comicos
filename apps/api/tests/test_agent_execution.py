from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import AgentDefinition, AgentExecution, AgentExecutionEvent
from app.schemas.agent import AgentDefinitionCreate
from app.services.agent_execution import complete_execution, fail_execution, log_event, start_execution
from app.services.agent_registry import enable_agent, register_agent
from agent_security_test_utils import grant_agent_execute
from test_inventory import auth_headers, register_and_login


def _register_enabled_agent(session: Session, *, code: str) -> int:
    existing = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    if existing is not None:
        enabled = enable_agent(session, agent_id=int(existing.id or 0))
        grant_agent_execute(session, agent_id=enabled.id)
        return enabled.id
    registered = register_agent(
        session,
        payload=AgentDefinitionCreate(
            code=code,
            name=f"{code} name",
            description=f"{code} description",
            version="1.0.0",
            enabled=False,
            capabilities=[],
        ),
    )
    enabled = enable_agent(session, agent_id=registered.id)
    grant_agent_execute(session, agent_id=enabled.id)
    return enabled.id


def test_agent_execution_creation_completion_event_logging_and_api_visibility(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "agent-execution@example.com")
    agent_id = _register_enabled_agent(session, code="execution_agent")

    started = start_execution(
        session,
        agent_id=agent_id,
        triggered_by="agent-execution@example.com",
        trigger_source="manual",
    )
    execution_id = started.execution.id
    assert started.execution.status == "RUNNING"
    assert started.events[0].event_type == "execution_started"

    custom_event = log_event(
        session,
        execution_id=execution_id,
        event_type="checkpoint_recorded",
        event_payload_json={"step": "validation", "sequence": 1},
    )
    assert custom_event.event_type == "checkpoint_recorded"

    completed = complete_execution(
        session,
        execution_id=execution_id,
        event_payload_json={"result": "ok"},
    )
    assert completed.execution.status == "COMPLETED"
    assert completed.execution.completed_at is not None
    assert completed.execution.execution_duration_ms is not None
    assert [row.event_type for row in completed.events] == [
        "execution_started",
        "checkpoint_recorded",
        "execution_completed",
    ]
    assert completed.events[-1].event_payload_json["status"] == "COMPLETED"
    assert completed.events[-1].event_payload_json["result"] == "ok"

    execution_rows = session.exec(
        select(AgentExecution)
        .where(AgentExecution.agent_id == agent_id)
        .order_by(AgentExecution.started_at.asc(), AgentExecution.id.asc())
    ).all()
    event_rows = session.exec(
        select(AgentExecutionEvent)
        .where(AgentExecutionEvent.execution_id == execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()
    assert len(execution_rows) == 1
    assert [row.event_type for row in event_rows] == [
        "execution_started",
        "checkpoint_recorded",
        "execution_completed",
    ]

    listing = client.get(
        "/api/v1/agent-executions?execution_status=COMPLETED&limit=20&offset=0",
        headers=auth_headers(token),
    )
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["data"]["items"]] == [execution_id]

    detail = client.get(f"/api/v1/agent-executions/{execution_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["execution"]["status"] == "COMPLETED"
    assert [row["event_type"] for row in detail_data["events"]] == [
        "execution_started",
        "checkpoint_recorded",
        "execution_completed",
    ]


def test_agent_execution_failure_is_terminal_and_history_remains_append_only(
    client: TestClient,
    session: Session,
) -> None:
    del client
    agent_id = _register_enabled_agent(session, code="failing_agent")
    started = start_execution(
        session,
        agent_id=agent_id,
        triggered_by="system:test",
        trigger_source="scheduler",
    )
    execution_id = started.execution.id

    failed = fail_execution(
        session,
        execution_id=execution_id,
        event_payload_json={"failure_reason": "timeout"},
    )
    assert failed.execution.status == "FAILED"
    assert [row.event_type for row in failed.events] == ["execution_started", "execution_failed"]
    assert failed.events[-1].event_payload_json["failure_reason"] == "timeout"

    for callback in (
        lambda: log_event(session, execution_id=execution_id, event_type="late_event", event_payload_json={}),
        lambda: complete_execution(session, execution_id=execution_id, event_payload_json={}),
        lambda: fail_execution(session, execution_id=execution_id, event_payload_json={}),
    ):
        try:
            callback()
        except HTTPException as exc:
            assert exc.status_code == 409
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected terminal execution mutation to be rejected.")

    refreshed = session.get(AgentExecution, execution_id)
    assert refreshed is not None
    assert refreshed.status == "FAILED"

    event_rows = session.exec(
        select(AgentExecutionEvent)
        .where(AgentExecutionEvent.execution_id == execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()
    assert [row.event_type for row in event_rows] == ["execution_started", "execution_failed"]


def test_disabled_agents_cannot_start_execution(
    client: TestClient,
    session: Session,
) -> None:
    del client
    existing = session.exec(select(AgentDefinition).where(AgentDefinition.code == "disabled_agent")).first()
    if existing is None:
        registered = register_agent(
            session,
            payload=AgentDefinitionCreate(
                code="disabled_agent",
                name="disabled agent",
                description="disabled execution guard",
                version="1.0.0",
                enabled=False,
                capabilities=[],
            ),
        )
    else:
        registered = existing

    try:
        start_execution(
            session,
            agent_id=int(registered.id or 0),
            triggered_by="system:test",
            trigger_source="manual",
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected disabled agent execution to be rejected.")
