from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    AutomationAlert,
    AutomationBatchRun,
    AutomationDeadLetterJob,
    AutomationJob,
    AutomationNotification,
    AutomationNotificationDelivery,
    AutomationQueue,
    AutomationRecoveryRun,
    AutomationRule,
    AutomationRuleAction,
    AutomationRuleArtifact,
    AutomationRuleEvaluation,
    AutomationRuleHistory,
    AutomationRuleIssue,
    AutomationRuleVersion,
    AutomationWorkflow,
    AutomationWorkflowExecution,
    AutomationWorker,
    ScanReplayIssue,
)
from app.schemas.automation_rules import (
    AutomationRuleActionRead,
    AutomationRuleCreate,
    AutomationRuleEvaluateCreate,
    AutomationRuleEvaluationRead,
    AutomationRuleIssueRead,
    AutomationRuleListResponse,
    AutomationRuleRead,
    AutomationRuleReadDetail,
    AutomationRuleVersionCreate,
    AutomationRuleVersionRead,
    AutomationSystemRuleEvaluateCreate,
)

ENGINE_VERSION = "P41-08-v1"
_RULE_CATEGORIES = {"WORKFLOW", "RECOVERY", "NOTIFICATION", "QUEUE", "REVIEW", "AUTHENTICATION", "REPLAY", "OPS"}
_RULE_STATUSES = {"ACTIVE", "PAUSED", "DISABLED", "ARCHIVED"}
_VERSION_STATUSES = {"DRAFT", "ACTIVE", "SUPERSEDED", "ARCHIVED"}
_EVALUATION_TYPES = {"WORKFLOW_TRIGGER", "QUEUE_RULE", "RECOVERY_RULE", "NOTIFICATION_RULE", "OPS_RULE", "SYSTEM_RULE"}
_EVALUATION_STATUSES = {"CREATED", "RUNNING", "MATCHED", "NOT_MATCHED", "FAILED", "SKIPPED"}
_ACTION_TYPES = {
    "CREATE_JOB",
    "CREATE_NOTIFICATION",
    "CREATE_ALERT",
    "EXECUTE_WORKFLOW",
    "PAUSE_QUEUE",
    "RESUME_QUEUE",
    "CREATE_RECOVERY_RUN",
    "CREATE_BATCH_JOB",
    "ACKNOWLEDGE_ALERT",
    "REPLAY_VERIFY",
}
_ACTION_STATUSES = {"CREATED", "EXECUTED", "FAILED", "SKIPPED", "BLOCKED"}
_SYSTEM_RULE_TYPE_BY_CATEGORY = {
    "QUEUE": "QUEUE_RULE",
    "RECOVERY": "RECOVERY_RULE",
    "NOTIFICATION": "NOTIFICATION_RULE",
    "OPS": "OPS_RULE",
    "REPLAY": "SYSTEM_RULE",
    "WORKFLOW": "WORKFLOW_TRIGGER",
}
_ALLOWED_COMPARE_NODES = (ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE)


@dataclass(frozen=True)
class _HistoryDraft:
    rule_id: int
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    rule_version_id: int | None = None
    evaluation_id: int | None = None
    action_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    rule_id: int
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]
    rule_version_id: int | None = None
    evaluation_id: int | None = None


@dataclass(frozen=True)
class _PlannedAction:
    action_rank: int
    action_type: str
    target_scope: str
    action_status: str
    action_payload_json: dict[str, Any]
    metadata_json: dict[str, Any]
    side_effect: dict[str, Any]


def utc_now() -> datetime:
    from app.models.automation_rules import utc_now as _utc_now

    return _utc_now()


def clamp_automation_rules_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _resolve_rules_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_rules_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation rules storage path escapes configured root")
    return target


def _save_rules_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_rules_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _rule_artifact_path(*, rule_key: str, evaluation_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-rules/{rule_key}/{evaluation_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _slugify_rule_key(*, rule_category: str, rule_name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{rule_category}-{rule_name}".lower()).strip("-")
    return base[:160] or "rule"


def _record_rule_history(session: Session, *, draft: _HistoryDraft) -> None:
    payload = {
        "rule_id": draft.rule_id,
        "rule_version_id": draft.rule_version_id,
        "evaluation_id": draft.evaluation_id,
        "action_id": draft.action_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationRuleHistory(
            rule_id=draft.rule_id,
            rule_version_id=draft.rule_version_id,
            evaluation_id=draft.evaluation_id,
            action_id=draft.action_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _persist_rule_issues(session: Session, *, drafts: list[_IssueDraft]) -> list[AutomationRuleIssue]:
    rows: list[AutomationRuleIssue] = []
    for draft in drafts:
        payload = {
            "rule_id": draft.rule_id,
            "rule_version_id": draft.rule_version_id,
            "evaluation_id": draft.evaluation_id,
            "issue_type": draft.issue_type,
            "severity": draft.severity,
            "issue_message": draft.issue_message,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationRuleIssue(
            rule_id=draft.rule_id,
            rule_version_id=draft.rule_version_id,
            evaluation_id=draft.evaluation_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _validate_expression(expression: str) -> ast.Expression:
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid rule expression: {exc.msg}") from exc

    for node in ast.walk(parsed):
        if isinstance(node, (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Name, ast.Load, ast.Constant)):
            continue
        if isinstance(node, _ALLOWED_COMPARE_NODES):
            continue
        raise HTTPException(status_code=422, detail=f"Invalid rule expression node: {type(node).__name__}")
    return parsed


def _compare_values(left: Any, op: ast.cmpop, right: Any) -> bool:
    if isinstance(op, ast.Eq):
        return left == right
    if isinstance(op, ast.NotEq):
        return left != right
    if left is None or right is None:
        return False
    if isinstance(op, ast.Gt):
        return left > right
    if isinstance(op, ast.GtE):
        return left >= right
    if isinstance(op, ast.Lt):
        return left < right
    if isinstance(op, ast.LtE):
        return left <= right
    raise ValueError(f"Unsupported comparator: {type(op).__name__}")


def _eval_expression_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_expression_node(node.body, context)
    if isinstance(node, ast.BoolOp):
        values = [_eval_expression_node(value, context) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(value) for value in values)
        if isinstance(node.op, ast.Or):
            return any(bool(value) for value in values)
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = _eval_expression_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_expression_node(comparator, context)
            if not _compare_values(left, op, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        return context.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def _normalize_action_definitions(action_definition_json: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, action in enumerate(action_definition_json, start=1):
        if not isinstance(action, dict):
            raise HTTPException(status_code=422, detail="Action definition entries must be objects.")
        action_type = str(action.get("action_type") or "").upper()
        if action_type not in _ACTION_TYPES:
            raise HTTPException(status_code=422, detail=f"Unsupported action_type: {action_type or '<missing>'}")
        target_scope = str(action.get("target_scope") or "system")
        action_rank = int(action.get("action_rank") or (index * 10))
        payload = action.get("action_payload_json")
        metadata = action.get("metadata_json")
        normalized.append(
            {
                "action_type": action_type,
                "action_rank": action_rank,
                "target_scope": target_scope,
                "action_payload_json": _json_safe(payload if isinstance(payload, dict) else {}),
                "metadata_json": _json_safe(metadata if isinstance(metadata, dict) else {}),
            }
        )
    normalized.sort(key=lambda row: (int(row["action_rank"]), str(row["action_type"]), str(row["target_scope"])))
    return normalized


def _system_counts(session: Session, *, owner_user_id: int | None) -> dict[str, Any]:
    queue_rows = list(session.exec(select(AutomationQueue).order_by(col(AutomationQueue.queue_key), col(AutomationQueue.id))).all())
    job_query = select(AutomationJob)
    if owner_user_id is not None:
        job_query = job_query.where(AutomationJob.owner_user_id == owner_user_id)
    jobs = list(session.exec(job_query).all())
    queue_depth = len([row for row in jobs if row.job_status in {"QUEUED", "RESERVED", "RUNNING"}])
    failed_jobs = len([row for row in jobs if row.job_status == "FAILED"])
    dead_letters = list(session.exec(select(AutomationDeadLetterJob)).all())
    if owner_user_id is not None:
        owner_job_ids = {row.id for row in jobs if row.id is not None}
        dead_letters = [row for row in dead_letters if row.original_job_id in owner_job_ids]
    worker_rows = list(session.exec(select(AutomationWorker)).all())
    notification_rows = list(session.exec(select(AutomationNotification)).all())
    if owner_user_id is not None:
        notification_rows = [row for row in notification_rows if int(row.owner_user_id or 0) == owner_user_id]
    notification_ids = [row.id for row in notification_rows if row.id is not None]
    failed_deliveries = list(
        session.exec(
            select(AutomationNotificationDelivery).where(
                col(AutomationNotificationDelivery.notification_id).in_(notification_ids or [-1])
            )
        ).all()
    )
    replay_issues = list(session.exec(select(ScanReplayIssue)).all())
    batch_failures = list(
        session.exec(
            select(AutomationBatchRun).where(col(AutomationBatchRun.batch_status).in_(("FAILED", "PARTIALLY_COMPLETED")))
        ).all()
    )
    return {
        "queue_depth": queue_depth,
        "dead_letter_count": len(dead_letters),
        "replay_warning_count": len([row for row in replay_issues if row.severity in {"WARNING", "ERROR", "CRITICAL"}]),
        "worker_error_count": len([row for row in worker_rows if row.worker_status == "ERROR"]),
        "active_worker_count": len([row for row in worker_rows if row.worker_status == "ACTIVE"]),
        "batch_failure_count": len(batch_failures),
        "notification_failure_count": len([row for row in failed_deliveries if row.delivery_status == "FAILED"]),
        "failed_jobs": failed_jobs,
        "queue_statuses": [row.queue_status for row in queue_rows],
    }


def _plan_rule_actions(
    session: Session,
    *,
    rule: AutomationRule,
    version: AutomationRuleVersion,
    evaluation_type: str,
    evaluation_scope: str,
    action_definition_json: list[dict[str, Any]],
) -> tuple[list[_PlannedAction], list[_IssueDraft]]:
    planned: list[_PlannedAction] = []
    issues: list[_IssueDraft] = []
    seen_action_keys: set[tuple[int, str, str]] = set()

    for action in _normalize_action_definitions(action_definition_json):
        action_rank = int(action["action_rank"])
        action_type = str(action["action_type"])
        target_scope = str(action["target_scope"])
        action_payload = dict(action["action_payload_json"])
        metadata_json = dict(action["metadata_json"])

        action_key = (action_rank, action_type, target_scope)
        if action_key in seen_action_keys:
            issues.append(
                _IssueDraft(
                    rule_id=int(rule.id or 0),
                    rule_version_id=int(version.id or 0),
                    issue_type="DUPLICATE_RULE_ACTION",
                    severity="WARNING",
                    issue_message="Duplicate deterministic action encountered.",
                    metadata_json={"action_rank": action_rank, "action_type": action_type, "target_scope": target_scope},
                )
            )
        seen_action_keys.add(action_key)

        status = "EXECUTED"
        payload_out: dict[str, Any] = {
            "evaluation_type": evaluation_type,
            "evaluation_scope": evaluation_scope,
            "requested_payload": _json_safe(action_payload),
        }
        side_effect: dict[str, Any] = {"kind": "none"}

        if action_type == "PAUSE_QUEUE":
            queue = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == target_scope)).first()
            if queue is None:
                status = "FAILED"
                payload_out["reason"] = "queue_not_found"
                issues.append(
                    _IssueDraft(
                        rule_id=int(rule.id or 0),
                        rule_version_id=int(version.id or 0),
                        issue_type="ACTION_EXECUTION_FAILURE",
                        severity="ERROR",
                        issue_message=f"Queue `{target_scope}` not found for pause action.",
                        metadata_json={"action_type": action_type, "target_scope": target_scope},
                    )
                )
            else:
                payload_out["previous_queue_status"] = queue.queue_status
                payload_out["queue_status"] = "PAUSED"
                side_effect = {"kind": "queue_status", "queue_id": int(queue.id or 0), "new_status": "PAUSED"}
        elif action_type == "RESUME_QUEUE":
            queue = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == target_scope)).first()
            if queue is None:
                status = "FAILED"
                payload_out["reason"] = "queue_not_found"
                issues.append(
                    _IssueDraft(
                        rule_id=int(rule.id or 0),
                        rule_version_id=int(version.id or 0),
                        issue_type="ACTION_EXECUTION_FAILURE",
                        severity="ERROR",
                        issue_message=f"Queue `{target_scope}` not found for resume action.",
                        metadata_json={"action_type": action_type, "target_scope": target_scope},
                    )
                )
            else:
                payload_out["previous_queue_status"] = queue.queue_status
                payload_out["queue_status"] = "ACTIVE"
                side_effect = {"kind": "queue_status", "queue_id": int(queue.id or 0), "new_status": "ACTIVE"}
        elif action_type == "EXECUTE_WORKFLOW":
            workflow = session.exec(select(AutomationWorkflow).where(AutomationWorkflow.workflow_key == target_scope)).first()
            if workflow is None:
                status = "FAILED"
                payload_out["reason"] = "workflow_not_found"
            else:
                payload_out["workflow_status"] = workflow.workflow_status
                side_effect = {"kind": "workflow_execution", "workflow_id": int(workflow.id or 0)}
        elif action_type == "CREATE_NOTIFICATION":
            notification_key = f"{rule.rule_key}:{action_rank}:notification"
            payload_out["notification_key"] = notification_key
            payload_out["notification_type"] = str(action_payload.get("notification_type") or "OPS_NOTIFICATION")
            side_effect = {"kind": "notification_create", "notification_key": notification_key, "payload": payload_out}
        elif action_type == "CREATE_ALERT":
            alert_key = f"{rule.rule_key}:{action_rank}:alert"
            payload_out["alert_key"] = alert_key
            payload_out["alert_type"] = str(action_payload.get("alert_type") or "SYSTEM_HEALTH_ALERT")
            side_effect = {"kind": "alert_create", "alert_key": alert_key, "payload": payload_out}
        elif action_type == "CREATE_BATCH_JOB":
            batch_key = f"{rule.rule_key}:{action_rank}:batch"
            payload_out["batch_key"] = batch_key
            side_effect = {"kind": "batch_create", "batch_key": batch_key, "payload": payload_out}
        elif action_type == "CREATE_JOB":
            queue = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == target_scope)).first()
            if queue is None:
                status = "FAILED"
                payload_out["reason"] = "queue_not_found"
            else:
                job_key = f"{rule.rule_key}:{action_rank}:job"
                payload_out["job_key"] = job_key
                side_effect = {"kind": "job_create", "queue_id": int(queue.id or 0), "job_key": job_key, "payload": payload_out}
        elif action_type == "CREATE_RECOVERY_RUN":
            job_key = str(action_payload.get("job_key") or "")
            job = session.exec(select(AutomationJob).where(AutomationJob.job_key == job_key)).first() if job_key else None
            if job is None:
                status = "FAILED"
                payload_out["reason"] = "job_not_found"
            else:
                side_effect = {"kind": "recovery_create", "job_id": int(job.id or 0), "payload": payload_out}
        elif action_type == "ACKNOWLEDGE_ALERT":
            alert = session.exec(select(AutomationAlert).where(AutomationAlert.alert_key == target_scope)).first()
            if alert is None:
                status = "FAILED"
                payload_out["reason"] = "alert_not_found"
            else:
                payload_out["previous_alert_status"] = alert.alert_status
                payload_out["alert_status"] = "ACKNOWLEDGED"
                side_effect = {"kind": "alert_ack", "alert_id": int(alert.id or 0)}
        elif action_type == "REPLAY_VERIFY":
            payload_out["verified"] = True
            side_effect = {"kind": "none"}
        else:
            status = "BLOCKED"
            issues.append(
                _IssueDraft(
                    rule_id=int(rule.id or 0),
                    rule_version_id=int(version.id or 0),
                    issue_type="INVALID_ACTION_SEQUENCE",
                    severity="ERROR",
                    issue_message=f"Action `{action_type}` is not supported.",
                    metadata_json={"target_scope": target_scope},
                )
            )

        planned.append(
            _PlannedAction(
                action_rank=action_rank,
                action_type=action_type,
                target_scope=target_scope,
                action_status=status,
                action_payload_json=payload_out,
                metadata_json=metadata_json,
                side_effect=side_effect,
            )
        )

    planned.sort(key=lambda row: (row.action_rank, row.action_type, row.target_scope))
    return planned, issues


def _apply_planned_side_effects(
    session: Session,
    *,
    rule: AutomationRule,
    planned_actions: list[_PlannedAction],
) -> None:
    for planned in planned_actions:
        if planned.action_status != "EXECUTED":
            continue
        side_effect = planned.side_effect
        kind = str(side_effect.get("kind") or "none")
        if kind == "queue_status":
            queue = session.get(AutomationQueue, int(side_effect["queue_id"]))
            if queue is not None:
                queue.queue_status = str(side_effect["new_status"])
                session.add(queue)
        elif kind == "workflow_execution":
            workflow_id = int(side_effect["workflow_id"])
            session.add(
                AutomationWorkflowExecution(
                    workflow_id=workflow_id,
                    execution_status="QUEUED",
                    execution_checksum=_hash_payload({"workflow_id": workflow_id, "rule_key": rule.rule_key, "kind": kind}),
                    execution_manifest_json={"rule_key": rule.rule_key, "execution_source": "automation_rule"},
                    metadata_json={"rule_key": rule.rule_key},
                )
            )
        elif kind == "notification_create":
            payload = dict(side_effect["payload"])
            session.add(
                AutomationNotification(
                    owner_user_id=rule.owner_user_id,
                    organization_id=rule.organization_id,
                    notification_key=str(side_effect["notification_key"]),
                    notification_type=str(payload.get("notification_type") or "OPS_NOTIFICATION"),
                    notification_status="QUEUED",
                    source_event_type="AUTOMATION_RULE",
                    source_record_type="AutomationRule",
                    source_record_id=rule.id,
                    source_checksum=_hash_payload({"rule_id": rule.id, "notification_key": side_effect["notification_key"]}),
                    notification_payload_json=_json_safe(payload),
                    notification_checksum=_hash_payload({"notification_key": side_effect["notification_key"], "payload": payload}),
                    metadata_json={"rule_key": rule.rule_key},
                )
            )
        elif kind == "alert_create":
            payload = dict(side_effect["payload"])
            session.add(
                AutomationAlert(
                    alert_key=str(side_effect["alert_key"]),
                    alert_type=str(payload.get("alert_type") or "SYSTEM_HEALTH_ALERT"),
                    alert_severity=str(payload.get("requested_payload", {}).get("severity") or "WARNING"),
                    alert_status="ACTIVE",
                    escalation_level="LEVEL_1",
                    alert_checksum=_hash_payload({"alert_key": side_effect["alert_key"], "payload": payload}),
                    metadata_json={"rule_key": rule.rule_key},
                )
            )
        elif kind == "batch_create":
            payload = dict(side_effect["payload"])
            session.add(
                AutomationBatchRun(
                    owner_user_id=rule.owner_user_id,
                    organization_id=rule.organization_id,
                    batch_key=str(side_effect["batch_key"]),
                    batch_type=str(payload.get("requested_payload", {}).get("batch_type") or "SYSTEM_MAINTENANCE"),
                    batch_status="QUEUED",
                    source_scope=str(payload.get("requested_payload", {}).get("source_scope") or "automation-rule"),
                    deterministic_partitioning_enabled=True,
                    replay_safe=True,
                    total_item_count=int(payload.get("requested_payload", {}).get("total_item_count") or 0),
                    completed_item_count=0,
                    failed_item_count=0,
                    batch_checksum=_hash_payload({"batch_key": side_effect["batch_key"], "payload": payload}),
                    manifest_json={"rule_key": rule.rule_key, "action": "CREATE_BATCH_JOB"},
                    metadata_json={"rule_key": rule.rule_key},
                )
            )
        elif kind == "job_create":
            payload = dict(side_effect["payload"])
            session.add(
                AutomationJob(
                    owner_user_id=rule.owner_user_id,
                    organization_id=rule.organization_id,
                    queue_id=int(side_effect["queue_id"]),
                    job_key=str(side_effect["job_key"]),
                    job_type=str(payload.get("requested_payload", {}).get("job_type") or "AUTOMATION_RULE_JOB"),
                    job_status="QUEUED",
                    priority=str(payload.get("requested_payload", {}).get("priority") or "NORMAL"),
                    deterministic_rank=int(planned.action_rank),
                    payload_snapshot_json=_json_safe(payload),
                    payload_checksum=_hash_payload(payload),
                    source_record_type="AutomationRule",
                    source_record_id=rule.id,
                    source_checksum=_hash_payload({"rule_id": rule.id, "job_key": side_effect["job_key"]}),
                    replay_safe=True,
                    idempotency_key=str(side_effect["job_key"]),
                    job_checksum=_hash_payload({"job_key": side_effect["job_key"], "payload": payload}),
                    metadata_json={"rule_key": rule.rule_key},
                )
            )
        elif kind == "recovery_create":
            job_id = int(side_effect["job_id"])
            payload = dict(side_effect["payload"])
            session.add(
                AutomationRecoveryRun(
                    owner_user_id=rule.owner_user_id,
                    organization_id=rule.organization_id,
                    job_id=job_id,
                    recovery_status="QUEUED",
                    recovery_type=str(payload.get("requested_payload", {}).get("recovery_type") or "RULE_TRIGGERED"),
                    recovery_rank=int(planned.action_rank),
                    recovery_checksum=_hash_payload({"job_id": job_id, "rule_key": rule.rule_key, "payload": payload}),
                    recovery_manifest_json={"rule_key": rule.rule_key, "action": "CREATE_RECOVERY_RUN"},
                    metadata_json={"rule_key": rule.rule_key},
                )
            )
        elif kind == "alert_ack":
            alert = session.get(AutomationAlert, int(side_effect["alert_id"]))
            if alert is not None:
                alert.alert_status = "ACKNOWLEDGED"
                alert.acknowledged_at = utc_now()
                session.add(alert)


def build_rule_manifest(
    *,
    rule: AutomationRule,
    version: AutomationRuleVersion,
    evaluation_input_json: dict[str, Any],
    evaluation_result_json: dict[str, Any],
    planned_actions: list[_PlannedAction],
    issues: list[_IssueDraft],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return _json_safe(
        {
            "engine_version": ENGINE_VERSION,
            "rule_snapshot": {
                "rule_id": rule.id,
                "rule_key": rule.rule_key,
                "rule_category": rule.rule_category,
                "rule_status": rule.rule_status,
            },
            "rule_version_snapshot": {
                "rule_version_id": version.id,
                "version_number": version.version_number,
                "version_status": version.version_status,
                "version_checksum": version.version_checksum,
            },
            "evaluation_input": evaluation_input_json,
            "evaluation_result": evaluation_result_json,
            "executed_actions": [
                {
                    "action_rank": row.action_rank,
                    "action_type": row.action_type,
                    "action_status": row.action_status,
                    "target_scope": row.target_scope,
                    "action_checksum": _hash_payload(
                        {
                            "action_rank": row.action_rank,
                            "action_type": row.action_type,
                            "target_scope": row.target_scope,
                            "action_status": row.action_status,
                            "action_payload_json": row.action_payload_json,
                        }
                    ),
                }
                for row in planned_actions
            ],
            "issues": [
                {
                    "issue_type": row.issue_type,
                    "severity": row.severity,
                    "issue_message": row.issue_message,
                    "issue_checksum": _hash_payload(
                        {
                            "rule_id": row.rule_id,
                            "rule_version_id": row.rule_version_id,
                            "evaluation_id": row.evaluation_id,
                            "issue_type": row.issue_type,
                            "severity": row.severity,
                            "issue_message": row.issue_message,
                            "metadata_json": row.metadata_json,
                        }
                    ),
                }
                for row in issues
            ],
            "artifacts": artifacts,
            "replay_lineage": {
                "rule_version_checksum": version.version_checksum,
                "evaluation_input_checksum": _hash_payload(evaluation_input_json),
                "evaluation_result_checksum": _hash_payload(evaluation_result_json),
            },
        }
    )


def _write_rule_artifacts(
    session: Session,
    settings: Settings,
    *,
    rule: AutomationRule,
    evaluation: AutomationRuleEvaluation,
    manifest: dict[str, Any],
) -> list[AutomationRuleArtifact]:
    assert evaluation.id is not None
    specs = [
        ("RULE_EVALUATION_REPORT", {"evaluation_id": evaluation.id, "result": evaluation.evaluation_result_json}),
        ("RULE_ACTION_EXPORT", {"evaluation_id": evaluation.id, "actions": manifest.get("executed_actions", [])}),
        ("RULE_MATCH_EXPORT", {"matched": evaluation.matched, "evaluation_status": evaluation.evaluation_status}),
        ("RULE_MANIFEST", manifest),
        ("RULE_DEBUG_PREVIEW", {"rule_key": rule.rule_key, "evaluation_checksum": evaluation.evaluation_checksum}),
    ]
    rows: list[AutomationRuleArtifact] = []
    for artifact_type, payload in specs:
        body = _serialize_json_artifact(payload)
        relative = _rule_artifact_path(rule_key=rule.rule_key, evaluation_id=evaluation.id, artifact_type=artifact_type, ext=".json")
        _save_rules_artifact_bytes(settings, relative_path=relative, body=body)
        row = AutomationRuleArtifact(
            evaluation_id=evaluation.id,
            artifact_type=artifact_type,
            storage_path=relative,
            artifact_checksum=_hash_payload({"path": relative, "body_sha256": hashlib.sha256(body).hexdigest()}),
            metadata_json={"byte_length": len(body)},
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _rule_to_read_detail(session: Session, *, rule: AutomationRule) -> AutomationRuleReadDetail:
    current_version = session.get(AutomationRuleVersion, rule.current_version_id) if rule.current_version_id else None
    base = AutomationRuleRead.model_validate(rule)
    return AutomationRuleReadDetail(
        **base.model_dump(),
        current_version=AutomationRuleVersionRead.model_validate(current_version) if current_version is not None else None,
    )


def _validate_rule_basics(*, rule_category: str, rule_status: str) -> None:
    if rule_category not in _RULE_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Unsupported rule_category: {rule_category}")
    if rule_status not in _RULE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported rule_status: {rule_status}")


def create_rule(
    session: Session,
    *,
    payload: AutomationRuleCreate,
) -> tuple[AutomationRuleReadDetail, bool]:
    rule_category = str(payload.rule_category).upper()
    rule_status = str(payload.rule_status).upper()
    _validate_rule_basics(rule_category=rule_category, rule_status=rule_status)
    _validate_expression(payload.condition_expression)
    normalized_actions = _normalize_action_definitions(payload.action_definition_json)
    rule_key = str(payload.rule_key or _slugify_rule_key(rule_category=rule_category, rule_name=payload.rule_name))

    existing = session.exec(
        select(AutomationRule).where(
            AutomationRule.owner_user_id == payload.owner_user_id,
            AutomationRule.rule_key == rule_key,
        )
    ).first()
    if existing is not None:
        return _rule_to_read_detail(session, rule=existing), False

    rule = AutomationRule(
        owner_user_id=payload.owner_user_id,
        rule_key=rule_key,
        rule_name=payload.rule_name,
        rule_category=rule_category,
        rule_status=rule_status,
        replay_safe=payload.replay_safe,
        deterministic_ordering_enabled=True,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(rule)
    session.flush()
    assert rule.id is not None

    version_checksum = _hash_payload(
        {
            "rule_key": rule_key,
            "version_number": 1,
            "version_status": "ACTIVE",
            "condition_expression": payload.condition_expression,
            "action_definition_json": normalized_actions,
            "evaluation_scope": payload.evaluation_scope,
            "replay_safe": payload.replay_safe,
        }
    )
    version = AutomationRuleVersion(
        rule_id=rule.id,
        version_number=1,
        version_status="ACTIVE",
        condition_expression=payload.condition_expression,
        action_definition_json=normalized_actions,
        evaluation_scope=payload.evaluation_scope,
        replay_safe=payload.replay_safe,
        version_checksum=version_checksum,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(version)
    session.flush()
    assert version.id is not None
    rule.current_version_id = version.id
    session.add(rule)

    _record_rule_history(
        session,
        draft=_HistoryDraft(
            rule_id=rule.id,
            rule_version_id=version.id,
            event_type="RULE_CREATED",
            event_message=f"Rule `{rule.rule_key}` created.",
            metadata_json={"replay_key": payload.replay_key, "engine_version": ENGINE_VERSION},
            to_status=rule.rule_status,
        ),
    )
    _record_rule_history(
        session,
        draft=_HistoryDraft(
            rule_id=rule.id,
            rule_version_id=version.id,
            event_type="RULE_VERSION_CREATED",
            event_message="Initial rule version created.",
            metadata_json={"version_number": 1, "version_checksum": version.version_checksum},
            to_status=version.version_status,
        ),
    )
    session.commit()
    session.refresh(rule)
    return _rule_to_read_detail(session, rule=rule), True


def create_rule_version(
    session: Session,
    *,
    rule_id: int,
    payload: AutomationRuleVersionCreate,
) -> tuple[AutomationRuleVersionRead, bool]:
    rule = session.get(AutomationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Automation rule not found.")

    version_status = str(payload.version_status).upper()
    if version_status not in _VERSION_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported version_status: {version_status}")
    _validate_expression(payload.condition_expression)
    normalized_actions = _normalize_action_definitions(payload.action_definition_json)

    existing_versions = list(
        session.exec(
            select(AutomationRuleVersion)
            .where(AutomationRuleVersion.rule_id == rule_id)
            .order_by(col(AutomationRuleVersion.version_number), col(AutomationRuleVersion.id))
        ).all()
    )
    next_version_number = (existing_versions[-1].version_number if existing_versions else 0) + 1
    checksum = _hash_payload(
        {
            "rule_id": rule_id,
            "version_number": next_version_number,
            "version_status": version_status,
            "condition_expression": payload.condition_expression,
            "action_definition_json": normalized_actions,
            "evaluation_scope": payload.evaluation_scope,
            "replay_safe": payload.replay_safe,
        }
    )
    existing = session.exec(select(AutomationRuleVersion).where(AutomationRuleVersion.version_checksum == checksum)).first()
    if existing is not None:
        return AutomationRuleVersionRead.model_validate(existing), False

    version = AutomationRuleVersion(
        rule_id=rule_id,
        version_number=next_version_number,
        version_status=version_status,
        condition_expression=payload.condition_expression,
        action_definition_json=normalized_actions,
        evaluation_scope=payload.evaluation_scope,
        replay_safe=payload.replay_safe,
        version_checksum=checksum,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(version)
    session.flush()
    assert version.id is not None
    if version_status == "ACTIVE":
        rule.current_version_id = version.id
        session.add(rule)

    _record_rule_history(
        session,
        draft=_HistoryDraft(
            rule_id=rule_id,
            rule_version_id=version.id,
            event_type="RULE_VERSION_CREATED",
            event_message=f"Rule version {next_version_number} created.",
            metadata_json={"replay_key": payload.replay_key, "version_checksum": checksum},
            to_status=version.version_status,
        ),
    )
    session.commit()
    session.refresh(version)
    return AutomationRuleVersionRead.model_validate(version), True


def evaluate_rule(
    session: Session,
    settings: Settings,
    *,
    rule_id: int,
    payload: AutomationRuleEvaluateCreate,
) -> tuple[AutomationRuleEvaluationRead, bool]:
    rule = session.get(AutomationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Automation rule not found.")
    version = session.get(AutomationRuleVersion, payload.rule_version_id or rule.current_version_id or 0)
    if version is None or version.rule_id != rule_id:
        raise HTTPException(status_code=404, detail="Automation rule version not found.")

    evaluation_type = str(payload.evaluation_type).upper()
    if evaluation_type not in _EVALUATION_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported evaluation_type: {evaluation_type}")

    parsed = _validate_expression(version.condition_expression)
    evaluation_input_json = _json_safe(payload.evaluation_input_json)
    issues: list[_IssueDraft] = []
    try:
        matched = bool(_eval_expression_node(parsed, evaluation_input_json))
        evaluation_status = "MATCHED" if matched else "NOT_MATCHED"
        evaluation_result_json = {
            "condition_expression": version.condition_expression,
            "matched": matched,
            "input_keys": sorted(str(key) for key in evaluation_input_json.keys()),
        }
    except Exception as exc:
        matched = False
        evaluation_status = "FAILED"
        evaluation_result_json = {
            "condition_expression": version.condition_expression,
            "matched": False,
            "error": str(exc),
        }
        issues.append(
            _IssueDraft(
                rule_id=rule_id,
                rule_version_id=int(version.id or 0),
                issue_type="INVALID_RULE_EXPRESSION",
                severity="ERROR",
                issue_message="Rule expression failed during evaluation.",
                metadata_json={"error": str(exc)},
            )
        )

    planned_actions: list[_PlannedAction] = []
    action_issues: list[_IssueDraft] = []
    if matched:
        planned_actions, action_issues = _plan_rule_actions(
            session,
            rule=rule,
            version=version,
            evaluation_type=evaluation_type,
            evaluation_scope=payload.evaluation_scope,
            action_definition_json=version.action_definition_json,
        )
    issues.extend(action_issues)

    manifest = build_rule_manifest(
        rule=rule,
        version=version,
        evaluation_input_json=evaluation_input_json,
        evaluation_result_json=evaluation_result_json,
        planned_actions=planned_actions,
        issues=issues,
        artifacts=[],
    )
    evaluation_checksum = _hash_payload(
        {
            "rule_version_checksum": version.version_checksum,
            "evaluation_type": evaluation_type,
            "evaluation_scope": payload.evaluation_scope,
            "evaluation_rank": payload.evaluation_rank,
            "evaluation_input": evaluation_input_json,
            "replay_key": payload.replay_key,
        }
    )
    existing = session.exec(
        select(AutomationRuleEvaluation).where(
            AutomationRuleEvaluation.rule_version_id == version.id,
            AutomationRuleEvaluation.evaluation_checksum == evaluation_checksum,
        )
    ).first()
    if existing is not None:
        return AutomationRuleEvaluationRead.model_validate(existing), False

    evaluation = AutomationRuleEvaluation(
        rule_id=rule_id,
        rule_version_id=int(version.id),
        evaluation_type=evaluation_type,
        evaluation_status=evaluation_status,
        evaluation_scope=payload.evaluation_scope,
        evaluation_input_json=evaluation_input_json,
        evaluation_result_json=_json_safe(evaluation_result_json),
        matched=matched,
        evaluation_rank=payload.evaluation_rank,
        evaluation_checksum=evaluation_checksum,
        replay_safe=payload.replay_safe,
        started_at=utc_now(),
        completed_at=utc_now(),
        metadata_json=_json_safe(payload.metadata_json | {"replay_key": payload.replay_key}),
    )
    session.add(evaluation)
    session.flush()
    assert evaluation.id is not None

    action_rows: list[AutomationRuleAction] = []
    if planned_actions:
        _apply_planned_side_effects(session, rule=rule, planned_actions=planned_actions)
        for planned in planned_actions:
            action_row = AutomationRuleAction(
                evaluation_id=evaluation.id,
                action_type=planned.action_type,
                action_status=planned.action_status,
                action_rank=planned.action_rank,
                target_scope=planned.target_scope,
                action_payload_json=_json_safe(planned.action_payload_json),
                action_checksum=_hash_payload(
                    {
                        "evaluation_id": evaluation.id,
                        "action_rank": planned.action_rank,
                        "action_type": planned.action_type,
                        "target_scope": planned.target_scope,
                        "action_status": planned.action_status,
                        "action_payload_json": planned.action_payload_json,
                    }
                ),
                replay_safe=True,
                metadata_json=_json_safe(planned.metadata_json),
            )
            session.add(action_row)
            session.flush()
            assert action_row.id is not None
            action_rows.append(action_row)
            _record_rule_history(
                session,
                draft=_HistoryDraft(
                    rule_id=rule_id,
                    rule_version_id=int(version.id),
                    evaluation_id=evaluation.id,
                    action_id=action_row.id,
                    event_type="RULE_ACTION_EXECUTED",
                    event_message=f"Rule action `{planned.action_type}` recorded as `{planned.action_status}`.",
                    metadata_json={"target_scope": planned.target_scope},
                    to_status=planned.action_status,
                ),
            )

    issue_rows = _persist_rule_issues(
        session,
        drafts=[
            _IssueDraft(
                rule_id=draft.rule_id,
                rule_version_id=draft.rule_version_id,
                evaluation_id=evaluation.id,
                issue_type=draft.issue_type,
                severity=draft.severity,
                issue_message=draft.issue_message,
                metadata_json=draft.metadata_json,
            )
            for draft in issues
        ],
    )

    manifest = build_rule_manifest(
        rule=rule,
        version=version,
        evaluation_input_json=evaluation_input_json,
        evaluation_result_json=evaluation_result_json,
        planned_actions=planned_actions,
        issues=issues,
        artifacts=[],
    )
    artifact_rows = _write_rule_artifacts(session, settings, rule=rule, evaluation=evaluation, manifest=manifest)
    manifest = build_rule_manifest(
        rule=rule,
        version=version,
        evaluation_input_json=evaluation_input_json,
        evaluation_result_json=evaluation_result_json,
        planned_actions=planned_actions,
        issues=issues,
        artifacts=[
            {
                "artifact_type": row.artifact_type,
                "artifact_checksum": row.artifact_checksum,
                "storage_path": row.storage_path,
            }
            for row in artifact_rows
        ],
    )
    evaluation.evaluation_result_json = _json_safe(dict(evaluation_result_json, manifest=manifest))
    session.add(evaluation)

    _record_rule_history(
        session,
        draft=_HistoryDraft(
            rule_id=rule_id,
            rule_version_id=int(version.id),
            evaluation_id=evaluation.id,
            event_type="RULE_EVALUATED",
            event_message=f"Rule evaluated with status `{evaluation.evaluation_status}`.",
            metadata_json={"matched": matched, "evaluation_checksum": evaluation.evaluation_checksum},
            to_status=evaluation.evaluation_status,
        ),
    )
    session.commit()
    session.refresh(evaluation)
    return AutomationRuleEvaluationRead.model_validate(evaluation), True


def evaluate_system_rules(
    session: Session,
    settings: Settings,
    *,
    payload: AutomationSystemRuleEvaluateCreate,
) -> AutomationRuleListResponse:
    counts = _system_counts(session, owner_user_id=payload.owner_user_id)
    rules = list(
        session.exec(
            select(AutomationRule)
            .where(col(AutomationRule.rule_status).in_(("ACTIVE", "PAUSED")))
            .order_by(col(AutomationRule.rule_category), col(AutomationRule.rule_key), col(AutomationRule.id))
        ).all()
    )
    if payload.owner_user_id is not None:
        rules = [row for row in rules if int(row.owner_user_id or 0) == payload.owner_user_id]
    evaluations: list[AutomationRuleEvaluationRead] = []
    for index, rule in enumerate(rules, start=1):
        evaluation_type = _SYSTEM_RULE_TYPE_BY_CATEGORY.get(rule.rule_category, "SYSTEM_RULE")
        evaluation, _ = evaluate_rule(
            session,
            settings,
            rule_id=int(rule.id or 0),
            payload=AutomationRuleEvaluateCreate(
                evaluation_type=evaluation_type,
                evaluation_scope=payload.evaluation_scope,
                evaluation_input_json=counts,
                evaluation_rank=index * 10,
                replay_safe=True,
                metadata_json=payload.metadata_json,
                replay_key=f"{payload.replay_key}:{rule.rule_key}",
            ),
        )
        evaluations.append(evaluation)
    failed_count = len([row for row in evaluations if row.evaluation_status == "FAILED"])
    return AutomationRuleListResponse(
        items=evaluations,
        total_items=len(evaluations),
        limit=len(evaluations),
        offset=0,
        failed_evaluation_count=failed_count,
        replay_drift_count=len([row for row in evaluations if row.evaluation_status == "FAILED" and row.evaluation_type == "SYSTEM_RULE"]),
    )


def get_automation_rule_owner(session: Session, *, owner_user_id: int, rule_id: int) -> AutomationRuleReadDetail:
    row = session.get(AutomationRule, rule_id)
    if row is None or int(row.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation rule not found.")
    return _rule_to_read_detail(session, rule=row)


def _rule_list_response(*, items: list[Any], rows: list[AutomationRule], limit: int, offset: int, evaluations: list[AutomationRuleEvaluation], issues: list[AutomationRuleIssue], actions: list[AutomationRuleAction]) -> AutomationRuleListResponse:
    return AutomationRuleListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        active_rule_count=len([row for row in rows if row.rule_status == "ACTIVE"]),
        failed_evaluation_count=len([row for row in evaluations if row.evaluation_status == "FAILED"]),
        replay_drift_count=len([row for row in issues if row.issue_type in {"REPLAY_RULE_DRIFT", "RULE_CHECKSUM_MISMATCH"}]),
        action_failure_count=len([row for row in actions if row.action_status == "FAILED"]),
        paused_rule_count=len([row for row in rows if row.rule_status == "PAUSED"]),
    )


def list_automation_rules_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationRuleListResponse:
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationRule)
            .where(AutomationRule.owner_user_id == owner_user_id)
            .order_by(col(AutomationRule.rule_category), col(AutomationRule.rule_key), col(AutomationRule.id))
        ).all()
    )
    evaluation_rows = list(session.exec(select(AutomationRuleEvaluation).where(AutomationRuleEvaluation.rule_id.in_([row.id for row in rows] or [-1]))).all())
    issue_rows = list(session.exec(select(AutomationRuleIssue).where(AutomationRuleIssue.rule_id.in_([row.id for row in rows] or [-1]))).all())
    action_rows = list(
        session.exec(
            select(AutomationRuleAction).where(AutomationRuleAction.evaluation_id.in_([row.id for row in evaluation_rows] or [-1]))
        ).all()
    )
    items = [_rule_to_read_detail(session, rule=row) for row in rows[offset : offset + limit]]
    return _rule_list_response(items=items, rows=rows, limit=limit, offset=offset, evaluations=evaluation_rows, issues=issue_rows, actions=action_rows)


def list_automation_rules_ops(session: Session, *, limit: int, offset: int) -> AutomationRuleListResponse:
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationRule).order_by(col(AutomationRule.rule_category), col(AutomationRule.rule_key), col(AutomationRule.id))).all())
    evaluation_rows = list(session.exec(select(AutomationRuleEvaluation)).all())
    issue_rows = list(session.exec(select(AutomationRuleIssue)).all())
    action_rows = list(session.exec(select(AutomationRuleAction)).all())
    items = [_rule_to_read_detail(session, rule=row) for row in rows[offset : offset + limit]]
    return _rule_list_response(items=items, rows=rows, limit=limit, offset=offset, evaluations=evaluation_rows, issues=issue_rows, actions=action_rows)


def list_automation_rule_versions_owner(session: Session, *, owner_user_id: int, rule_id: int, limit: int, offset: int) -> AutomationRuleListResponse:
    _ = get_automation_rule_owner(session, owner_user_id=owner_user_id, rule_id=rule_id)
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationRuleVersion)
            .where(AutomationRuleVersion.rule_id == rule_id)
            .order_by(col(AutomationRuleVersion.version_number), col(AutomationRuleVersion.id))
        ).all()
    )
    return AutomationRuleListResponse(items=[AutomationRuleVersionRead.model_validate(row) for row in rows[offset : offset + limit]], total_items=len(rows), limit=limit, offset=offset)


def list_automation_rule_evaluations_owner(session: Session, *, owner_user_id: int, rule_id: int, limit: int, offset: int) -> AutomationRuleListResponse:
    _ = get_automation_rule_owner(session, owner_user_id=owner_user_id, rule_id=rule_id)
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationRuleEvaluation)
            .where(AutomationRuleEvaluation.rule_id == rule_id)
            .order_by(col(AutomationRuleEvaluation.evaluation_rank), col(AutomationRuleEvaluation.created_at), col(AutomationRuleEvaluation.id))
        ).all()
    )
    failed = len([row for row in rows if row.evaluation_status == "FAILED"])
    return AutomationRuleListResponse(
        items=[AutomationRuleEvaluationRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        failed_evaluation_count=failed,
    )


def list_automation_rule_actions_owner(session: Session, *, owner_user_id: int, rule_id: int, limit: int, offset: int) -> AutomationRuleListResponse:
    _ = get_automation_rule_owner(session, owner_user_id=owner_user_id, rule_id=rule_id)
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    evaluation_ids = [int(row) for row in session.exec(select(AutomationRuleEvaluation.id).where(AutomationRuleEvaluation.rule_id == rule_id)).all()]
    rows = list(
        session.exec(
            select(AutomationRuleAction)
            .where(col(AutomationRuleAction.evaluation_id).in_(evaluation_ids or [-1]))
            .order_by(col(AutomationRuleAction.action_rank), col(AutomationRuleAction.action_type), col(AutomationRuleAction.created_at), col(AutomationRuleAction.id))
        ).all()
    )
    failures = len([row for row in rows if row.action_status == "FAILED"])
    return AutomationRuleListResponse(
        items=[AutomationRuleActionRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        action_failure_count=failures,
    )


def list_automation_rule_issues_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationRuleListResponse:
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rule_ids = [int(row) for row in session.exec(select(AutomationRule.id).where(AutomationRule.owner_user_id == owner_user_id)).all()]
    rows = list(
        session.exec(
            select(AutomationRuleIssue)
            .where(col(AutomationRuleIssue.rule_id).in_(rule_ids or [-1]))
            .order_by(col(AutomationRuleIssue.created_at).desc(), col(AutomationRuleIssue.id).desc())
        ).all()
    )
    replay_drift_count = len([row for row in rows if row.issue_type in {"REPLAY_RULE_DRIFT", "RULE_CHECKSUM_MISMATCH"}])
    return AutomationRuleListResponse(
        items=[AutomationRuleIssueRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        replay_drift_count=replay_drift_count,
    )


def list_automation_rule_failures_ops(session: Session, *, limit: int, offset: int) -> AutomationRuleListResponse:
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationRuleEvaluation)
            .where(col(AutomationRuleEvaluation.evaluation_status).in_(("FAILED",)))
            .order_by(col(AutomationRuleEvaluation.created_at).desc(), col(AutomationRuleEvaluation.id).desc())
        ).all()
    )
    return AutomationRuleListResponse(
        items=[AutomationRuleEvaluationRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        failed_evaluation_count=len(rows),
    )


def list_automation_rule_issues_ops(session: Session, *, limit: int, offset: int) -> AutomationRuleListResponse:
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationRuleIssue)
            .order_by(col(AutomationRuleIssue.created_at).desc(), col(AutomationRuleIssue.id).desc())
        ).all()
    )
    return AutomationRuleListResponse(
        items=[AutomationRuleIssueRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        replay_drift_count=len([row for row in rows if row.issue_type in {"REPLAY_RULE_DRIFT", "RULE_CHECKSUM_MISMATCH"}]),
    )


def list_automation_rule_drift_ops(session: Session, *, limit: int, offset: int) -> AutomationRuleListResponse:
    limit, offset = clamp_automation_rules_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationRuleIssue)
            .where(col(AutomationRuleIssue.issue_type).in_(("REPLAY_RULE_DRIFT", "RULE_CHECKSUM_MISMATCH", "RULE_VERSION_CONFLICT")))
            .order_by(col(AutomationRuleIssue.created_at).desc(), col(AutomationRuleIssue.id).desc())
        ).all()
    )
    return AutomationRuleListResponse(
        items=[AutomationRuleIssueRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        replay_drift_count=len(rows),
    )
