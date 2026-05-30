from __future__ import annotations

from app.models import WorkflowDefinition, WorkflowExecution, WorkflowStep, WorkflowStepExecution
from app.services.agent_execution import log_event


def record_workflow_started(
    session,
    *,
    agent_execution_id: int,
    workflow: WorkflowDefinition,
    workflow_execution: WorkflowExecution,
) -> None:
    log_event(
        session,
        execution_id=agent_execution_id,
        event_type="workflow_started",
        event_payload_json={
            "workflow_id": int(workflow.id or 0),
            "workflow_code": workflow.workflow_code,
            "workflow_execution_id": int(workflow_execution.id or 0),
            "workflow_status": workflow_execution.status,
        },
    )


def record_workflow_completed(
    session,
    *,
    agent_execution_id: int,
    workflow: WorkflowDefinition,
    workflow_execution: WorkflowExecution,
) -> None:
    log_event(
        session,
        execution_id=agent_execution_id,
        event_type="workflow_completed",
        event_payload_json={
            "workflow_id": int(workflow.id or 0),
            "workflow_code": workflow.workflow_code,
            "workflow_execution_id": int(workflow_execution.id or 0),
            "workflow_status": workflow_execution.status,
        },
    )


def record_workflow_failed(
    session,
    *,
    agent_execution_id: int,
    workflow: WorkflowDefinition,
    workflow_execution: WorkflowExecution,
    reason: str | None = None,
) -> None:
    log_event(
        session,
        execution_id=agent_execution_id,
        event_type="workflow_failed",
        event_payload_json={
            "workflow_id": int(workflow.id or 0),
            "workflow_code": workflow.workflow_code,
            "workflow_execution_id": int(workflow_execution.id or 0),
            "workflow_status": workflow_execution.status,
            "reason": reason,
        },
    )


def record_step_started(
    session,
    *,
    agent_execution_id: int,
    workflow_step: WorkflowStep,
    workflow_step_execution: WorkflowStepExecution,
) -> None:
    log_event(
        session,
        execution_id=agent_execution_id,
        event_type="step_started",
        event_payload_json={
            "workflow_step_id": int(workflow_step.id or 0),
            "step_code": workflow_step.step_code,
            "step_execution_id": int(workflow_step_execution.id or 0),
            "step_status": workflow_step_execution.status,
        },
    )


def record_step_completed(
    session,
    *,
    agent_execution_id: int,
    workflow_step: WorkflowStep,
    workflow_step_execution: WorkflowStepExecution,
) -> None:
    log_event(
        session,
        execution_id=agent_execution_id,
        event_type="step_completed",
        event_payload_json={
            "workflow_step_id": int(workflow_step.id or 0),
            "step_code": workflow_step.step_code,
            "step_execution_id": int(workflow_step_execution.id or 0),
            "step_status": workflow_step_execution.status,
        },
    )


def record_step_failed(
    session,
    *,
    agent_execution_id: int,
    workflow_step: WorkflowStep,
    workflow_step_execution: WorkflowStepExecution,
    reason: str | None = None,
) -> None:
    log_event(
        session,
        execution_id=agent_execution_id,
        event_type="step_failed",
        event_payload_json={
            "workflow_step_id": int(workflow_step.id or 0),
            "step_code": workflow_step.step_code,
            "step_execution_id": int(workflow_step_execution.id or 0),
            "step_status": workflow_step_execution.status,
            "reason": reason,
        },
    )
