from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    AutomationSchedule,
    AutomationTrigger,
    AutomationWorkflow,
    AutomationWorkflowExecution,
    AutomationWorkflowHistory,
    AutomationWorkflowIssue,
    AutomationWorkflowStep,
)
from app.schemas.automation_jobs import AutomationJobCreate
from app.schemas.automation_scheduling import (
    AutomationScheduleCreate,
    AutomationScheduleListResponse,
    AutomationScheduleRead,
    AutomationTriggerCreate,
    AutomationTriggerListResponse,
    AutomationTriggerRead,
    AutomationWorkflowExecutionListResponse,
    AutomationWorkflowExecutionRead,
    AutomationWorkflowHistoryListResponse,
    AutomationWorkflowHistoryRead,
    AutomationWorkflowIssueListResponse,
    AutomationWorkflowIssueRead,
    AutomationWorkflowListResponse,
    AutomationWorkflowRead,
    AutomationWorkflowStepRead,
)
from app.services.automation_jobs import create_automation_job, create_job_dependency

ENGINE_VERSION = "P41-03-v1"
_SCHEDULE_TYPES = {"ONE_TIME", "RECURRING", "INTERVAL", "EVENT_DRIVEN"}
_SCHEDULE_STATUSES = {"ACTIVE", "PAUSED", "DISABLED", "COMPLETED"}
_TRIGGER_TYPES = {
    "SCAN_COMPLETED",
    "REVIEW_COMPLETED",
    "REPLAY_COMPLETED",
    "AUTHENTICATION_COMPLETED",
    "FEED_GENERATED",
    "JOB_FAILED",
    "MANUAL_TRIGGER",
    "SYSTEM_TRIGGER",
}
_TRIGGER_STATUSES = {"PENDING", "PROCESSED", "FAILED", "SKIPPED"}
_WORKFLOW_CATEGORIES = {
    "SCAN_PIPELINE",
    "REVIEW_PIPELINE",
    "REPLAY_PIPELINE",
    "NOTIFICATION_PIPELINE",
    "MAINTENANCE_PIPELINE",
    "SYSTEM_PIPELINE",
}
_WORKFLOW_STATUSES = {"ACTIVE", "PAUSED", "DISABLED"}
_DEPENDENCY_MODES = {"STRICT_SEQUENCE", "PARALLEL_ALLOWED", "CONDITIONAL", "OPTIONAL"}
_EXECUTION_STATUSES = {"CREATED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "BLOCKED"}
_ARTIFACT_MEDIA_TYPES = {".json": "application/json", ".txt": "text/plain; charset=utf-8"}


@dataclass(frozen=True)
class _WorkflowStepBlueprint:
    step_rank: int
    step_key: str
    job_type: str
    dependency_mode: str
    delay_seconds: int | None = None
    required_success: bool = True
    metadata_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class _WorkflowBlueprint:
    workflow_name: str
    workflow_category: str
    steps: tuple[_WorkflowStepBlueprint, ...]


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    execution_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]
    execution_id: int | None = None


_WORKFLOW_BLUEPRINTS: dict[str, _WorkflowBlueprint] = {
    "scan_completed_feed_generation": _WorkflowBlueprint(
        workflow_name="Scan completed -> feed generation",
        workflow_category="SCAN_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "generate_feed", "FEED_GENERATION", "STRICT_SEQUENCE", metadata_json={"queue_key": "scan-pipeline", "queue_category": "SCAN_PIPELINE"}),
        ),
    ),
    "review_completed_authentication": _WorkflowBlueprint(
        workflow_name="Review completed -> authentication",
        workflow_category="REVIEW_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "run_authentication", "AUTHENTICATION_RUN", "STRICT_SEQUENCE", metadata_json={"queue_key": "review", "queue_category": "REVIEW"}),
        ),
    ),
    "replay_completed_audit_feed_update": _WorkflowBlueprint(
        workflow_name="Replay completed -> audit feed update",
        workflow_category="REPLAY_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "update_audit_feed", "FEED_GENERATION", "STRICT_SEQUENCE", metadata_json={"queue_key": "replay", "queue_category": "REPLAY"}),
        ),
    ),
    "job_failed_issue_workflow": _WorkflowBlueprint(
        workflow_name="Job failed -> issue workflow",
        workflow_category="NOTIFICATION_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "handle_failure", "SYSTEM_MAINTENANCE", "STRICT_SEQUENCE", metadata_json={"queue_key": "system", "queue_category": "SYSTEM"}),
        ),
    ),
    "maintenance_schedule_workflow": _WorkflowBlueprint(
        workflow_name="Scheduled maintenance workflow",
        workflow_category="MAINTENANCE_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "maintenance_job", "SYSTEM_MAINTENANCE", "STRICT_SEQUENCE", metadata_json={"queue_key": "maintenance", "queue_category": "MAINTENANCE"}),
        ),
    ),
    "manual_trigger_workflow": _WorkflowBlueprint(
        workflow_name="Manual trigger workflow",
        workflow_category="SYSTEM_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "manual_job", "FUTURE_RESERVED", "STRICT_SEQUENCE", metadata_json={"queue_key": "system", "queue_category": "SYSTEM"}),
        ),
    ),
    "blocked_test_workflow": _WorkflowBlueprint(
        workflow_name="Blocked workflow test",
        workflow_category="SYSTEM_PIPELINE",
        steps=(
            _WorkflowStepBlueprint(1, "blocked_job", "FUTURE_RESERVED", "CONDITIONAL", metadata_json={"condition_met": False, "queue_key": "system", "queue_category": "SYSTEM"}),
        ),
    ),
}
_TRIGGER_WORKFLOW_BY_TYPE = {
    "SCAN_COMPLETED": "scan_completed_feed_generation",
    "REVIEW_COMPLETED": "review_completed_authentication",
    "REPLAY_COMPLETED": "replay_completed_audit_feed_update",
    "JOB_FAILED": "job_failed_issue_workflow",
    "MANUAL_TRIGGER": "manual_trigger_workflow",
    "SYSTEM_TRIGGER": "maintenance_schedule_workflow",
}


def utc_now() -> datetime:
    from app.models.automation_schedules import utc_now as _utc_now

    return _utc_now()


def clamp_automation_scheduling_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _resolve_workflow_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_workflows_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation workflows storage path escapes configured root")
    return target


def _save_workflow_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_workflow_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _workflow_artifact_path(*, workflow_key: str, execution_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-workflows/{workflow_key}/{execution_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _record_workflow_history(session: Session, *, workflow_id: int, draft: _HistoryDraft) -> None:
    payload = {
        "workflow_id": workflow_id,
        "execution_id": draft.execution_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationWorkflowHistory(
            workflow_id=workflow_id,
            execution_id=draft.execution_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_workflow_issue(session: Session, *, workflow_id: int, draft: _IssueDraft) -> None:
    payload = {
        "workflow_id": workflow_id,
        "execution_id": draft.execution_id,
        "issue_type": draft.issue_type,
        "severity": draft.severity,
        "issue_message": draft.issue_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationWorkflowIssue(
            workflow_id=workflow_id,
            execution_id=draft.execution_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _infer_workflow_key(*, workflow_key: str | None, schedule_type: str | None = None, trigger_type: str | None = None) -> str:
    if workflow_key:
        return workflow_key
    if trigger_type:
        return _TRIGGER_WORKFLOW_BY_TYPE.get(trigger_type, "manual_trigger_workflow")
    if schedule_type in {"INTERVAL", "RECURRING", "ONE_TIME"}:
        return "maintenance_schedule_workflow"
    return "manual_trigger_workflow"


def _validate_schedule_create(payload: AutomationScheduleCreate) -> None:
    schedule_type = str(payload.schedule_type)
    if schedule_type not in _SCHEDULE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid schedule type.")
    if schedule_type in {"INTERVAL", "RECURRING"} and payload.interval_seconds is None and not payload.cron_expression:
        raise HTTPException(status_code=422, detail="Recurring schedules require interval_seconds or cron_expression.")


def _validate_trigger_create(payload: AutomationTriggerCreate) -> None:
    if str(payload.trigger_type) not in _TRIGGER_TYPES:
        raise HTTPException(status_code=422, detail="Invalid trigger type.")


def _default_schedule_next_run(payload: AutomationScheduleCreate) -> datetime | None:
    if payload.next_run_at is None:
        if str(payload.schedule_type) == "EVENT_DRIVEN":
            return None
        return utc_now()
    return _normalize_datetime(payload.next_run_at)


def _workflow_owner_filters(*, owner_user_id: int | None, organization_id: int | None) -> tuple[int | None, int | None]:
    return owner_user_id, organization_id


def _get_or_create_workflow(
    session: Session,
    *,
    owner_user_id: int | None,
    organization_id: int | None,
    workflow_key: str,
) -> AutomationWorkflow:
    workflow = session.exec(
        select(AutomationWorkflow).where(
            AutomationWorkflow.owner_user_id == owner_user_id,
            AutomationWorkflow.organization_id == organization_id,
            AutomationWorkflow.workflow_key == workflow_key,
        )
    ).first()
    if workflow is not None:
        return workflow
    blueprint = _WORKFLOW_BLUEPRINTS.get(workflow_key)
    if blueprint is None:
        raise HTTPException(status_code=404, detail=f"Unknown workflow key: {workflow_key}")
    workflow = AutomationWorkflow(
        owner_user_id=owner_user_id,
        organization_id=organization_id,
        workflow_key=workflow_key,
        workflow_name=blueprint.workflow_name,
        workflow_status="ACTIVE",
        workflow_category=blueprint.workflow_category,
        replay_safe=True,
        deterministic_ordering_enabled=True,
        metadata_json={},
    )
    session.add(workflow)
    session.flush()
    for step in blueprint.steps:
        session.add(
            AutomationWorkflowStep(
                workflow_id=int(workflow.id),
                step_rank=step.step_rank,
                step_key=step.step_key,
                job_type=step.job_type,
                dependency_mode=step.dependency_mode,
                delay_seconds=step.delay_seconds,
                required_success=step.required_success,
                metadata_json=_json_safe(step.metadata_json or {}),
            )
        )
    session.flush()
    _record_workflow_history(
        session,
        workflow_id=int(workflow.id),
        draft=_HistoryDraft(
            event_type="WORKFLOW_REGISTERED",
            event_message="Workflow definition registered.",
            metadata_json={"workflow_key": workflow_key},
        ),
    )
    return workflow


def _load_workflow_steps(session: Session, *, workflow_id: int) -> list[AutomationWorkflowStep]:
    return list(
        session.exec(
            select(AutomationWorkflowStep)
            .where(AutomationWorkflowStep.workflow_id == workflow_id)
            .order_by(col(AutomationWorkflowStep.step_rank), col(AutomationWorkflowStep.id))
        ).all()
    )


def resolve_workflow_dependencies(steps: list[AutomationWorkflowStep]) -> dict[int, list[int]]:
    by_key = {step.step_key: step for step in steps}
    deps: dict[int, list[int]] = {int(step.id or step.step_rank): [] for step in steps}
    ordered = sorted(steps, key=lambda step: (step.step_rank, step.id or 0))
    previous: AutomationWorkflowStep | None = None
    for step in ordered:
        node = int(step.id or step.step_rank)
        if step.dependency_mode == "STRICT_SEQUENCE" and previous is not None:
            deps[node].append(int(previous.id or previous.step_rank))
        depends_on_key = (step.metadata_json or {}).get("depends_on_step_key")
        if depends_on_key:
            target = by_key.get(str(depends_on_key))
            if target is None:
                raise HTTPException(status_code=422, detail="Workflow dependency references an unknown step.")
            deps[node].append(int(target.id or target.step_rank))
        previous = step

    seen: set[int] = set()
    visiting: set[int] = set()

    def visit(node: int) -> None:
        if node in visiting:
            raise HTTPException(status_code=422, detail="Cyclic workflow dependency detected.")
        if node in seen:
            return
        visiting.add(node)
        for dep in deps[node]:
            visit(dep)
        visiting.remove(node)
        seen.add(node)

    for node in list(deps):
        visit(node)
    return {node: sorted(set(dep_list)) for node, dep_list in deps.items()}


def build_workflow_manifest(
    *,
    workflow: AutomationWorkflow,
    steps: list[AutomationWorkflowStep],
    schedule: AutomationSchedule | None,
    trigger: AutomationTrigger | None,
    generated_jobs: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    artifact_refs: list[dict[str, Any]],
    execution_metadata: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "workflow": {
            "workflow_key": workflow.workflow_key,
            "workflow_name": workflow.workflow_name,
            "workflow_category": workflow.workflow_category,
            "workflow_status": workflow.workflow_status,
            "metadata_json": _json_safe(workflow.metadata_json),
        },
        "schedule_snapshot": _json_safe(schedule.model_dump() if schedule else None),
        "trigger_lineage": _json_safe(trigger.model_dump() if trigger else None),
        "step_graph": _json_safe(
            [
                {
                    "step_rank": step.step_rank,
                    "step_key": step.step_key,
                    "job_type": step.job_type,
                    "dependency_mode": step.dependency_mode,
                    "delay_seconds": step.delay_seconds,
                    "required_success": step.required_success,
                    "metadata_json": step.metadata_json,
                }
                for step in sorted(steps, key=lambda row: (row.step_rank, row.id or 0))
            ]
        ),
        "generated_jobs": _json_safe(sorted(generated_jobs, key=lambda row: ((row.get("step_rank") or 0), row.get("job_checksum") or ""))),
        "issues": _json_safe(sorted(issues, key=lambda row: ((row.get("severity") or ""), row.get("issue_type") or ""))),
        "artifact_refs": _json_safe(sorted(artifact_refs, key=lambda row: (row.get("artifact_type") or "", row.get("artifact_checksum") or ""))),
        "execution_metadata": _json_safe(execution_metadata),
    }
    return manifest, _hash_payload(manifest)


def create_schedule(
    session: Session,
    *,
    owner_user_id: int,
    payload: AutomationScheduleCreate,
) -> tuple[AutomationScheduleRead, bool]:
    _validate_schedule_create(payload)
    workflow_key = _infer_workflow_key(workflow_key=payload.workflow_key, schedule_type=str(payload.schedule_type))
    workflow = _get_or_create_workflow(session, owner_user_id=owner_user_id, organization_id=None, workflow_key=workflow_key)
    schedule_snapshot = {
        "owner_user_id": owner_user_id,
        "organization_id": None,
        "schedule_name": payload.schedule_name,
        "schedule_type": str(payload.schedule_type),
        "cron_expression": payload.cron_expression,
        "interval_seconds": payload.interval_seconds,
        "next_run_at": _default_schedule_next_run(payload),
        "workflow_key": workflow_key,
        "metadata_json": payload.metadata_json,
    }
    schedule_checksum = _hash_payload(schedule_snapshot)
    schedule_key = _hash_payload({"name": payload.schedule_name, "type": payload.schedule_type, "workflow_key": workflow_key, "checksum": schedule_checksum})[:24]
    existing = session.exec(
        select(AutomationSchedule).where(
            AutomationSchedule.owner_user_id == owner_user_id,
            AutomationSchedule.schedule_checksum == schedule_checksum,
        )
    ).first()
    if existing is not None:
        return AutomationScheduleRead.model_validate(existing), False
    row = AutomationSchedule(
        owner_user_id=owner_user_id,
        organization_id=None,
        schedule_key=schedule_key,
        schedule_name=payload.schedule_name,
        schedule_type=str(payload.schedule_type),
        schedule_status="ACTIVE",
        cron_expression=payload.cron_expression,
        interval_seconds=payload.interval_seconds,
        next_run_at=_default_schedule_next_run(payload),
        last_run_at=None,
        replay_safe=payload.replay_safe,
        deterministic_ordering_enabled=True,
        schedule_checksum=schedule_checksum,
        metadata_json=_json_safe({**payload.metadata_json, "workflow_key": workflow_key}),
    )
    session.add(row)
    session.flush()
    _record_workflow_history(
        session,
        workflow_id=int(workflow.id),
        draft=_HistoryDraft(
            event_type="SCHEDULE_CREATED",
            event_message="Automation schedule created.",
            metadata_json={"schedule_id": row.id, "schedule_checksum": schedule_checksum},
        ),
    )
    session.commit()
    return AutomationScheduleRead.model_validate(row), True


def create_trigger(
    session: Session,
    *,
    owner_user_id: int,
    payload: AutomationTriggerCreate,
) -> tuple[AutomationTriggerRead, bool]:
    _validate_trigger_create(payload)
    workflow_key = _infer_workflow_key(workflow_key=payload.workflow_key, trigger_type=str(payload.trigger_type))
    workflow = _get_or_create_workflow(session, owner_user_id=owner_user_id, organization_id=None, workflow_key=workflow_key)
    trigger_snapshot = {
        "owner_user_id": owner_user_id,
        "trigger_type": str(payload.trigger_type),
        "source_event_type": payload.source_event_type,
        "source_record_type": payload.source_record_type,
        "source_record_id": payload.source_record_id,
        "source_checksum": payload.source_checksum,
        "trigger_payload_json": payload.trigger_payload_json,
        "workflow_key": workflow_key,
        "metadata_json": payload.metadata_json,
    }
    trigger_checksum = _hash_payload(trigger_snapshot)
    existing = session.exec(
        select(AutomationTrigger).where(
            AutomationTrigger.owner_user_id == owner_user_id,
            AutomationTrigger.trigger_checksum == trigger_checksum,
        )
    ).first()
    if existing is not None:
        return AutomationTriggerRead.model_validate(existing), False
    row = AutomationTrigger(
        owner_user_id=owner_user_id,
        organization_id=None,
        trigger_key=_hash_payload({"trigger_type": payload.trigger_type, "trigger_checksum": trigger_checksum})[:24],
        trigger_type=str(payload.trigger_type),
        trigger_status="PENDING",
        source_event_type=payload.source_event_type,
        source_record_type=payload.source_record_type,
        source_record_id=payload.source_record_id,
        source_checksum=payload.source_checksum,
        trigger_payload_json=_json_safe(payload.trigger_payload_json),
        trigger_checksum=trigger_checksum,
        metadata_json=_json_safe({**payload.metadata_json, "workflow_key": workflow_key}),
    )
    session.add(row)
    session.flush()
    _record_workflow_history(
        session,
        workflow_id=int(workflow.id),
        draft=_HistoryDraft(
            event_type="TRIGGER_CREATED",
            event_message="Automation trigger created.",
            metadata_json={"trigger_id": row.id, "trigger_checksum": trigger_checksum},
        ),
    )
    session.commit()
    return AutomationTriggerRead.model_validate(row), True


def _activation_key(*, workflow: AutomationWorkflow, schedule: AutomationSchedule | None, trigger: AutomationTrigger | None) -> str:
    return _hash_payload(
        {
            "workflow_key": workflow.workflow_key,
            "schedule_checksum": schedule.schedule_checksum if schedule else None,
            "schedule_next_run_at": _normalize_datetime(schedule.next_run_at) if schedule else None,
            "trigger_checksum": trigger.trigger_checksum if trigger else None,
        }
    )


def execute_workflow(
    session: Session,
    settings: Settings,
    *,
    workflow_id: int,
    trigger_id: int | None = None,
    schedule_id: int | None = None,
) -> AutomationWorkflowExecutionRead:
    workflow = session.get(AutomationWorkflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Automation workflow not found.")
    steps = _load_workflow_steps(session, workflow_id=workflow_id)
    if not steps:
        raise HTTPException(status_code=409, detail="Workflow has no steps.")
    trigger = session.get(AutomationTrigger, trigger_id) if trigger_id is not None else None
    schedule = session.get(AutomationSchedule, schedule_id) if schedule_id is not None else None
    activation = _activation_key(workflow=workflow, schedule=schedule, trigger=trigger)
    existing = next(
        (
            row
            for row in session.exec(
                select(AutomationWorkflowExecution).where(AutomationWorkflowExecution.workflow_id == workflow_id)
            ).all()
            if str((row.metadata_json or {}).get("activation_key") or "") == activation
        ),
        None,
    )
    if existing is not None:
        return AutomationWorkflowExecutionRead.model_validate(existing)
    if workflow.owner_user_id is None:
        raise HTTPException(status_code=409, detail="Workflow is missing owner context.")

    dependency_map = resolve_workflow_dependencies(steps)
    execution = AutomationWorkflowExecution(
        workflow_id=workflow_id,
        trigger_id=trigger_id,
        schedule_id=schedule_id,
        execution_status="RUNNING",
        execution_checksum="pending",
        execution_manifest_json={},
        metadata_json={"activation_key": activation},
    )
    session.add(execution)
    session.flush()
    _record_workflow_history(
        session,
        workflow_id=workflow_id,
        draft=_HistoryDraft(
            event_type="WORKFLOW_EXECUTION_CREATED",
            event_message="Workflow execution created.",
            metadata_json={"execution_id": execution.id, "activation_key": activation},
            execution_id=int(execution.id),
        ),
    )

    generated_jobs: list[dict[str, Any]] = []
    issue_payloads: list[dict[str, Any]] = []
    job_id_by_step_key: dict[str, int] = {}
    execution_status = "COMPLETED"
    for step in sorted(steps, key=lambda row: (row.step_rank, row.id or 0)):
        step_id = int(step.id or step.step_rank)
        if step.dependency_mode == "CONDITIONAL" and not bool((step.metadata_json or {}).get("condition_met", False)):
            execution_status = "BLOCKED"
            issue = {
                "issue_type": "BLOCKED_WORKFLOW_STEP",
                "severity": "WARNING",
                "issue_message": f"Workflow step {step.step_key} was deterministically blocked.",
                "metadata_json": {"step_key": step.step_key, "step_rank": step.step_rank},
            }
            issue_payloads.append(issue)
            _record_workflow_issue(
                session,
                workflow_id=workflow_id,
                draft=_IssueDraft(
                    issue_type=issue["issue_type"],
                    severity=issue["severity"],
                    issue_message=issue["issue_message"],
                    metadata_json=issue["metadata_json"],
                    execution_id=int(execution.id),
                ),
            )
            continue

        queue_key = str((step.metadata_json or {}).get("queue_key") or workflow.workflow_key.replace("_workflow", "").replace("_", "-"))
        queue_category = str((step.metadata_json or {}).get("queue_category") or "SYSTEM")
        delay_seconds = int(step.delay_seconds or 0)
        base_time = _normalize_datetime(schedule.next_run_at) if schedule and schedule.next_run_at else utc_now()
        job_payload = AutomationJobCreate(
            queue_key=queue_key,
            queue_name=None,
            queue_category=queue_category,
            organization_id=workflow.organization_id,
            parent_job_id=None,
            job_key=f"{workflow.workflow_key}:{execution.id}:{step.step_key}",
            job_type=step.job_type,
            priority="NORMAL",
            payload_snapshot_json={
                "workflow_execution_id": execution.id,
                "workflow_key": workflow.workflow_key,
                "step_key": step.step_key,
                "step_rank": step.step_rank,
                "trigger_checksum": trigger.trigger_checksum if trigger else None,
                "schedule_checksum": schedule.schedule_checksum if schedule else None,
            },
            source_record_type="automation_workflow_execution",
            source_record_id=int(execution.id),
            source_checksum=trigger.trigger_checksum if trigger else schedule.schedule_checksum if schedule else None,
            available_at=(base_time + timedelta(seconds=delay_seconds)) if base_time else utc_now(),
            max_attempts=3,
            replay_safe=True,
            idempotency_key=f"{activation}:{step.step_key}",
            metadata_json={"dependency_mode": step.dependency_mode},
        )
        job_detail, _created = create_automation_job(session, settings, owner_user_id=int(workflow.owner_user_id), payload=job_payload)
        job_id_by_step_key[step.step_key] = int(job_detail.id)
        for dep_node in dependency_map.get(step_id, []):
            dep_step = next(candidate for candidate in steps if int(candidate.id or candidate.step_rank) == dep_node)
            depends_on_job_id = job_id_by_step_key.get(dep_step.step_key)
            if depends_on_job_id is not None:
                create_job_dependency(session, job_id=int(job_detail.id), depends_on_job_id=depends_on_job_id)
        generated_jobs.append(
            {
                "step_rank": step.step_rank,
                "step_key": step.step_key,
                "job_id": job_detail.id,
                "job_checksum": job_detail.job_checksum,
                "queue_key": job_detail.queue_key,
                "dependency_mode": step.dependency_mode,
            }
        )

    artifact_refs: list[dict[str, Any]] = []
    execution_metadata = {
        "activation_key": activation,
        "trigger_checksum": trigger.trigger_checksum if trigger else None,
        "schedule_checksum": schedule.schedule_checksum if schedule else None,
    }
    manifest, execution_checksum = build_workflow_manifest(
        workflow=workflow,
        steps=steps,
        schedule=schedule,
        trigger=trigger,
        generated_jobs=generated_jobs,
        issues=issue_payloads,
        artifact_refs=artifact_refs,
        execution_metadata=execution_metadata,
    )
    execution.execution_checksum = execution_checksum
    execution.execution_manifest_json = _json_safe(manifest)
    execution.execution_status = execution_status
    execution.completed_at = utc_now()

    for artifact_type, body in [
        ("WORKFLOW_EXECUTION_REPORT", _serialize_json_artifact({"execution_id": execution.id, "execution_status": execution_status, "generated_jobs": generated_jobs})),
        ("WORKFLOW_STEP_EXPORT", _serialize_json_artifact({"steps": [_json_safe(step.model_dump()) for step in steps]})),
        ("WORKFLOW_TRIGGER_EXPORT", _serialize_json_artifact({"trigger": _json_safe(trigger.model_dump()) if trigger else None, "schedule": _json_safe(schedule.model_dump()) if schedule else None})),
        ("WORKFLOW_MANIFEST", _serialize_json_artifact(manifest)),
        ("WORKFLOW_DEBUG_PREVIEW", _serialize_json_artifact({"execution_id": execution.id, "workflow_key": workflow.workflow_key, "activation_key": activation})),
    ]:
        storage_path = _workflow_artifact_path(workflow_key=workflow.workflow_key, execution_id=int(execution.id), artifact_type=artifact_type, ext=".json")
        _save_workflow_artifact_bytes(settings, relative_path=storage_path, body=body)
        artifact_refs.append(
            {
                "artifact_type": artifact_type,
                "storage_path": storage_path,
                "artifact_checksum": _sha256_bytes(body),
                "media_type": _ARTIFACT_MEDIA_TYPES[".json"],
            }
        )
    execution.execution_manifest_json = _json_safe({**manifest, "artifact_refs": artifact_refs})
    execution.execution_checksum = _hash_payload({**manifest, "artifact_refs": artifact_refs})
    if execution_status == "BLOCKED":
        _record_workflow_history(
            session,
            workflow_id=workflow_id,
            draft=_HistoryDraft(
                event_type="WORKFLOW_BLOCKED",
                event_message="Workflow execution completed with blocked steps.",
                metadata_json={"execution_id": execution.id, "blocked_step_count": len(issue_payloads)},
                execution_id=int(execution.id),
                from_status="RUNNING",
                to_status="BLOCKED",
            ),
        )
    else:
        _record_workflow_history(
            session,
            workflow_id=workflow_id,
            draft=_HistoryDraft(
                event_type="WORKFLOW_COMPLETED",
                event_message="Workflow execution completed.",
                metadata_json={"execution_id": execution.id, "generated_job_count": len(generated_jobs)},
                execution_id=int(execution.id),
                from_status="RUNNING",
                to_status=execution_status,
            ),
        )
    session.commit()
    session.refresh(execution)
    return AutomationWorkflowExecutionRead.model_validate(execution)


def process_due_schedules(session: Session, settings: Settings) -> AutomationWorkflowExecutionListResponse:
    now = utc_now()
    rows = list(session.exec(select(AutomationSchedule).where(AutomationSchedule.schedule_status == "ACTIVE")).all())
    due = [
        row
        for row in rows
        if (normalized := _normalize_datetime(row.next_run_at)) is not None and normalized <= now
    ]
    due.sort(key=lambda row: (_normalize_datetime(row.next_run_at) or now, row.created_at, row.id or 0))
    items: list[AutomationWorkflowExecutionRead] = []
    status_counts: dict[str, int] = {}
    for schedule in due:
        workflow_key = str(schedule.metadata_json.get("workflow_key") or _infer_workflow_key(workflow_key=None, schedule_type=schedule.schedule_type))
        workflow = _get_or_create_workflow(session, owner_user_id=schedule.owner_user_id, organization_id=schedule.organization_id, workflow_key=workflow_key)
        execution = execute_workflow(session, settings, workflow_id=int(workflow.id), schedule_id=int(schedule.id))
        items.append(execution)
        status_counts[execution.execution_status] = status_counts.get(execution.execution_status, 0) + 1
        schedule.last_run_at = now
        if schedule.schedule_type == "ONE_TIME":
            schedule.schedule_status = "COMPLETED"
            schedule.next_run_at = None
        elif schedule.interval_seconds:
            schedule.next_run_at = (_normalize_datetime(schedule.next_run_at) or now) + timedelta(seconds=int(schedule.interval_seconds))
        elif schedule.cron_expression:
            schedule.next_run_at = (_normalize_datetime(schedule.next_run_at) or now) + timedelta(days=1)
        _record_workflow_history(
            session,
            workflow_id=int(workflow.id),
            draft=_HistoryDraft(
                event_type="SCHEDULE_PROCESSED",
                event_message="Schedule converted into workflow execution.",
                metadata_json={"schedule_id": schedule.id, "execution_id": execution.id},
                execution_id=int(execution.id),
            ),
        )
    session.commit()
    return AutomationWorkflowExecutionListResponse(items=items, total_items=len(items), limit=len(items) or 1, offset=0, execution_status_counts=status_counts)


def process_triggers(session: Session, settings: Settings) -> AutomationWorkflowExecutionListResponse:
    rows = list(session.exec(select(AutomationTrigger).where(AutomationTrigger.trigger_status == "PENDING")).all())
    rows.sort(key=lambda row: (row.triggered_at, row.created_at, row.id or 0))
    items: list[AutomationWorkflowExecutionRead] = []
    status_counts: dict[str, int] = {}
    for trigger in rows:
        workflow_key = str(trigger.metadata_json.get("workflow_key") or _infer_workflow_key(workflow_key=None, trigger_type=trigger.trigger_type))
        workflow = _get_or_create_workflow(session, owner_user_id=trigger.owner_user_id, organization_id=trigger.organization_id, workflow_key=workflow_key)
        try:
            execution = execute_workflow(session, settings, workflow_id=int(workflow.id), trigger_id=int(trigger.id))
            trigger.trigger_status = "PROCESSED"
            items.append(execution)
            status_counts[execution.execution_status] = status_counts.get(execution.execution_status, 0) + 1
            _record_workflow_history(
                session,
                workflow_id=int(workflow.id),
                draft=_HistoryDraft(
                    event_type="TRIGGER_PROCESSED",
                    event_message="Trigger converted into workflow execution.",
                    metadata_json={"trigger_id": trigger.id, "execution_id": execution.id},
                    execution_id=int(execution.id),
                ),
            )
        except HTTPException as exc:
            trigger.trigger_status = "FAILED"
            _record_workflow_issue(
                session,
                workflow_id=int(workflow.id),
                draft=_IssueDraft(
                    issue_type="TRIGGER_PROCESSING_FAILURE",
                    severity="ERROR",
                    issue_message=str(exc.detail),
                    metadata_json={"trigger_id": trigger.id},
                ),
            )
    session.commit()
    return AutomationWorkflowExecutionListResponse(items=items, total_items=len(items), limit=len(items) or 1, offset=0, execution_status_counts=status_counts)


def _schedule_to_read(row: AutomationSchedule) -> AutomationScheduleRead:
    return AutomationScheduleRead.model_validate(row)


def _trigger_to_read(row: AutomationTrigger) -> AutomationTriggerRead:
    return AutomationTriggerRead.model_validate(row)


def _workflow_to_read(session: Session, *, workflow: AutomationWorkflow) -> AutomationWorkflowRead:
    steps = _load_workflow_steps(session, workflow_id=int(workflow.id))
    executions = list(
        session.exec(
            select(AutomationWorkflowExecution)
            .where(AutomationWorkflowExecution.workflow_id == workflow.id)
            .order_by(col(AutomationWorkflowExecution.created_at).desc(), col(AutomationWorkflowExecution.id).desc())
        ).all()
    )
    latest = executions[0] if executions else None
    blocked_steps = list(
        session.exec(
            select(AutomationWorkflowIssue).where(
                AutomationWorkflowIssue.workflow_id == workflow.id,
                AutomationWorkflowIssue.issue_type == "BLOCKED_WORKFLOW_STEP",
            )
        ).all()
    )
    pending_trigger_count = len(
        [
            row
            for row in session.exec(
                select(AutomationTrigger).where(
                    AutomationTrigger.owner_user_id == workflow.owner_user_id,
                    AutomationTrigger.trigger_status == "PENDING",
                )
            ).all()
            if str(row.metadata_json.get("workflow_key") or "") == workflow.workflow_key
        ]
    )
    return AutomationWorkflowRead(
        **workflow.model_dump(),
        steps=[AutomationWorkflowStepRead.model_validate(step) for step in steps],
        latest_execution=AutomationWorkflowExecutionRead.model_validate(latest) if latest else None,
        blocked_step_count=len(blocked_steps),
        pending_trigger_count=pending_trigger_count,
    )


def list_automation_schedules_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationScheduleListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationSchedule).where(AutomationSchedule.owner_user_id == owner_user_id).order_by(col(AutomationSchedule.created_at).desc(), col(AutomationSchedule.id).desc())).all())
    paged = rows[offset : offset + limit]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.schedule_status] = status_counts.get(row.schedule_status, 0) + 1
        type_counts[row.schedule_type] = type_counts.get(row.schedule_type, 0) + 1
    return AutomationScheduleListResponse(items=[_schedule_to_read(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts, type_counts=type_counts)


def get_automation_schedule_owner(session: Session, *, owner_user_id: int, schedule_id: int) -> AutomationScheduleRead:
    row = session.get(AutomationSchedule, schedule_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation schedule not found.")
    return _schedule_to_read(row)


def list_automation_triggers_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationTriggerListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationTrigger).where(AutomationTrigger.owner_user_id == owner_user_id).order_by(col(AutomationTrigger.triggered_at).desc(), col(AutomationTrigger.id).desc())).all())
    paged = rows[offset : offset + limit]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.trigger_status] = status_counts.get(row.trigger_status, 0) + 1
        type_counts[row.trigger_type] = type_counts.get(row.trigger_type, 0) + 1
    return AutomationTriggerListResponse(
        items=[_trigger_to_read(row) for row in paged],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        type_counts=type_counts,
        pending_trigger_count=status_counts.get("PENDING", 0),
    )


def list_automation_workflows_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationWorkflowListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkflow).where(AutomationWorkflow.owner_user_id == owner_user_id).order_by(col(AutomationWorkflow.created_at).desc(), col(AutomationWorkflow.id).desc())).all())
    paged = rows[offset : offset + limit]
    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    failed_execution_count = 0
    blocked_workflow_count = 0
    items: list[AutomationWorkflowRead] = []
    for row in rows:
        status_counts[row.workflow_status] = status_counts.get(row.workflow_status, 0) + 1
        category_counts[row.workflow_category] = category_counts.get(row.workflow_category, 0) + 1
    for row in paged:
        read = _workflow_to_read(session, workflow=row)
        items.append(read)
        failed_execution_count += 1 if read.latest_execution and read.latest_execution.execution_status == "FAILED" else 0
        blocked_workflow_count += 1 if read.blocked_step_count > 0 or (read.latest_execution and read.latest_execution.execution_status == "BLOCKED") else 0
    return AutomationWorkflowListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        category_counts=category_counts,
        blocked_workflow_count=blocked_workflow_count,
        failed_execution_count=failed_execution_count,
    )


def get_automation_workflow_owner(session: Session, *, owner_user_id: int, workflow_id: int) -> AutomationWorkflowRead:
    row = session.get(AutomationWorkflow, workflow_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation workflow not found.")
    return _workflow_to_read(session, workflow=row)


def list_automation_workflow_executions_owner(session: Session, *, owner_user_id: int, workflow_id: int, limit: int, offset: int) -> AutomationWorkflowExecutionListResponse:
    workflow = session.get(AutomationWorkflow, workflow_id)
    if workflow is None or workflow.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation workflow not found.")
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkflowExecution).where(AutomationWorkflowExecution.workflow_id == workflow_id).order_by(col(AutomationWorkflowExecution.created_at).desc(), col(AutomationWorkflowExecution.id).desc())).all())
    paged = rows[offset : offset + limit]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.execution_status] = counts.get(row.execution_status, 0) + 1
    return AutomationWorkflowExecutionListResponse(items=[AutomationWorkflowExecutionRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, execution_status_counts=counts)


def list_automation_workflow_history_owner(session: Session, *, owner_user_id: int, workflow_id: int, limit: int, offset: int) -> AutomationWorkflowHistoryListResponse:
    workflow = session.get(AutomationWorkflow, workflow_id)
    if workflow is None or workflow.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation workflow not found.")
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkflowHistory).where(AutomationWorkflowHistory.workflow_id == workflow_id).order_by(col(AutomationWorkflowHistory.created_at).desc(), col(AutomationWorkflowHistory.id).desc())).all())
    paged = rows[offset : offset + limit]
    return AutomationWorkflowHistoryListResponse(items=[AutomationWorkflowHistoryRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset)


def list_automation_schedules_ops(session: Session, *, limit: int, offset: int) -> AutomationScheduleListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationSchedule).order_by(col(AutomationSchedule.next_run_at), col(AutomationSchedule.created_at), col(AutomationSchedule.id))).all())
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.schedule_status] = status_counts.get(row.schedule_status, 0) + 1
        type_counts[row.schedule_type] = type_counts.get(row.schedule_type, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationScheduleListResponse(items=[_schedule_to_read(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts, type_counts=type_counts)


def list_automation_triggers_ops(session: Session, *, limit: int, offset: int) -> AutomationTriggerListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationTrigger).order_by(col(AutomationTrigger.triggered_at), col(AutomationTrigger.created_at), col(AutomationTrigger.id))).all())
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.trigger_status] = status_counts.get(row.trigger_status, 0) + 1
        type_counts[row.trigger_type] = type_counts.get(row.trigger_type, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationTriggerListResponse(items=[_trigger_to_read(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts, type_counts=type_counts, pending_trigger_count=status_counts.get("PENDING", 0))


def list_automation_workflows_ops(session: Session, *, limit: int, offset: int, blocked_only: bool) -> AutomationWorkflowListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkflow).order_by(col(AutomationWorkflow.created_at).desc(), col(AutomationWorkflow.id).desc())).all())
    all_reads = [_workflow_to_read(session, workflow=row) for row in rows]
    if blocked_only:
        all_reads = [row for row in all_reads if row.blocked_step_count > 0 or (row.latest_execution and row.latest_execution.execution_status == "BLOCKED")]
    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in all_reads:
        status_counts[row.workflow_status] = status_counts.get(row.workflow_status, 0) + 1
        category_counts[row.workflow_category] = category_counts.get(row.workflow_category, 0) + 1
    paged = all_reads[offset : offset + limit]
    return AutomationWorkflowListResponse(
        items=paged,
        total_items=len(all_reads),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        category_counts=category_counts,
        blocked_workflow_count=sum(1 for row in all_reads if row.blocked_step_count > 0 or (row.latest_execution and row.latest_execution.execution_status == "BLOCKED")),
        failed_execution_count=sum(1 for row in all_reads if row.latest_execution and row.latest_execution.execution_status == "FAILED"),
    )


def list_automation_workflow_issues_ops(session: Session, *, limit: int, offset: int) -> AutomationWorkflowIssueListResponse:
    limit, offset = clamp_automation_scheduling_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkflowIssue).order_by(col(AutomationWorkflowIssue.created_at).desc(), col(AutomationWorkflowIssue.id).desc())).all())
    paged = rows[offset : offset + limit]
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    return AutomationWorkflowIssueListResponse(items=[AutomationWorkflowIssueRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)
