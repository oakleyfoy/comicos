from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    AutomationAlert,
    AutomationAnalyticsArtifact,
    AutomationAnalyticsComparison,
    AutomationAnalyticsHistory,
    AutomationAnalyticsIssue,
    AutomationAnalyticsMetric,
    AutomationAnalyticsSnapshot,
    AutomationAnalyticsTrend,
    AutomationBatchRun,
    AutomationDeadLetterJob,
    AutomationJob,
    AutomationNotification,
    AutomationNotificationDelivery,
    AutomationQueue,
    AutomationRecoveryRun,
    AutomationRuleEvaluation,
    AutomationWorkflow,
    AutomationWorkflowExecution,
    AutomationWorker,
    ScanReplayIssue,
)
from app.schemas.automation_analytics import (
    AutomationAnalyticsComparisonRead,
    AutomationAnalyticsIssueRead,
    AutomationAnalyticsListResponse,
    AutomationAnalyticsMetricRead,
    AutomationAnalyticsSnapshotCreate,
    AutomationAnalyticsSnapshotRead,
    AutomationAnalyticsSystemIntelligenceRead,
    AutomationAnalyticsTrendRead,
)

ENGINE_VERSION = "P41-09-v1"
_ANALYTICS_TYPES = {
    "QUEUE_ANALYTICS",
    "WORKER_ANALYTICS",
    "WORKFLOW_ANALYTICS",
    "RECOVERY_ANALYTICS",
    "REPLAY_ANALYTICS",
    "BATCH_ANALYTICS",
    "NOTIFICATION_ANALYTICS",
    "SYSTEM_ANALYTICS",
}
_TREND_TYPES = {
    "QUEUE_GROWTH",
    "FAILURE_RATE",
    "RECOVERY_RATE",
    "REPLAY_WARNING_RATE",
    "WORKER_UTILIZATION",
    "BATCH_GROWTH",
    "ALERT_VOLUME",
    "WORKFLOW_THROUGHPUT",
}
_COMPARISON_TYPES = {
    "DAY_OVER_DAY",
    "WEEK_OVER_WEEK",
    "SNAPSHOT_COMPARE",
    "REPLAY_COMPARE",
    "FAILURE_COMPARE",
    "UTILIZATION_COMPARE",
}
@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    snapshot_id: int | None = None
    comparison_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _MetricDraft:
    metric_key: str
    metric_category: str
    metric_value: str
    metric_delta: str | None
    metric_status: str
    metric_rank: int
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _TrendDraft:
    trend_key: str
    trend_type: str
    trend_direction: str
    historical_window: int
    trend_value: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _ComparisonDraft:
    comparison_key: str
    comparison_type: str
    baseline_snapshot_id: int | None
    comparison_result_json: dict[str, Any]
    metadata_json: dict[str, Any]


def utc_now() -> datetime:
    from app.models.automation_analytics import utc_now as _utc_now

    return _utc_now()


def clamp_automation_analytics_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_analytics_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_analytics_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation analytics storage path escapes configured root")
    return target


def _save_analytics_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_analytics_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _analytics_artifact_path(*, analytics_type: str, snapshot_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-analytics/{analytics_type.lower()}/{snapshot_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _record_history(session: Session, *, draft: _HistoryDraft) -> None:
    payload = {
        "snapshot_id": draft.snapshot_id,
        "comparison_id": draft.comparison_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationAnalyticsHistory(
            snapshot_id=draft.snapshot_id,
            comparison_id=draft.comparison_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_issues(session: Session, *, drafts: list[_IssueDraft]) -> list[AutomationAnalyticsIssue]:
    rows: list[AutomationAnalyticsIssue] = []
    for draft in drafts:
        payload = {
            "snapshot_id": draft.metadata_json.get("snapshot_id"),
            "issue_type": draft.issue_type,
            "severity": draft.severity,
            "issue_message": draft.issue_message,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationAnalyticsIssue(
            snapshot_id=int(draft.metadata_json["snapshot_id"]),
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


def _analytics_counts(session: Session, *, owner_user_id: int | None) -> dict[str, Any]:
    queue_query = select(AutomationQueue)
    job_query = select(AutomationJob)
    if owner_user_id is not None:
        job_query = job_query.where(AutomationJob.owner_user_id == owner_user_id)
    jobs = list(session.exec(job_query).all())
    queue_depth = len([row for row in jobs if row.job_status in {"QUEUED", "RESERVED", "RUNNING"}])
    total_jobs = len(jobs)
    failed_jobs = len([row for row in jobs if row.job_status == "FAILED"])

    workers = list(session.exec(select(AutomationWorker)).all())
    active_workers = len([row for row in workers if row.worker_status == "ACTIVE"])
    total_workers = len(workers)

    workflows = list(session.exec(select(AutomationWorkflow)).all())
    workflow_executions = list(session.exec(select(AutomationWorkflowExecution)).all())
    recovery_runs = list(session.exec(select(AutomationRecoveryRun)).all())

    batch_runs_query = select(AutomationBatchRun)
    if owner_user_id is not None:
        batch_runs_query = batch_runs_query.where(AutomationBatchRun.owner_user_id == owner_user_id)
    batch_runs = list(session.exec(batch_runs_query).all())

    notifications_query = select(AutomationNotification)
    if owner_user_id is not None:
        notifications_query = notifications_query.where(AutomationNotification.owner_user_id == owner_user_id)
    notifications = list(session.exec(notifications_query).all())
    notification_ids = [row.id for row in notifications if row.id is not None]
    deliveries = list(
        session.exec(
            select(AutomationNotificationDelivery).where(col(AutomationNotificationDelivery.notification_id).in_(notification_ids or [-1]))
        ).all()
    )

    dead_letters = list(session.exec(select(AutomationDeadLetterJob)).all())
    if owner_user_id is not None:
        owner_job_ids = {row.id for row in jobs if row.id is not None}
        dead_letters = [row for row in dead_letters if row.original_job_id in owner_job_ids]

    replay_issues = list(session.exec(select(ScanReplayIssue)).all())
    alerts = list(session.exec(select(AutomationAlert)).all())
    rule_evaluations = list(session.exec(select(AutomationRuleEvaluation)).all())
    rule_failed = len([row for row in rule_evaluations if row.evaluation_status == "FAILED"])
    queue_rows = list(session.exec(queue_query).all())

    return {
        "queue_depth": queue_depth,
        "total_jobs": total_jobs,
        "failed_jobs": failed_jobs,
        "active_workers": active_workers,
        "total_workers": total_workers,
        "workflow_throughput": len([row for row in workflow_executions if row.execution_status in {"COMPLETED", "SUCCEEDED"}]),
        "recovery_success": len([row for row in recovery_runs if row.recovery_status == "COMPLETED"]),
        "batch_completed": len([row for row in batch_runs if row.batch_status == "COMPLETED"]),
        "batch_total": len(batch_runs),
        "notification_delivered": len([row for row in deliveries if row.delivery_status == "DELIVERED"]),
        "notification_total": len(notifications),
        "dead_letter_count": len(dead_letters),
        "replay_warning_count": len([row for row in replay_issues if row.severity in {"WARNING", "ERROR", "CRITICAL"}]),
        "alert_volume": len(alerts),
        "rule_failed": rule_failed,
        "queue_statuses": [row.queue_status for row in queue_rows],
    }


def _analytics_status(counts: dict[str, Any]) -> str:
    if counts["failed_jobs"] > 10 or counts["dead_letter_count"] > 10 or counts["replay_warning_count"] > 10:
        return "CRITICAL"
    if counts["failed_jobs"] > 0 or counts["dead_letter_count"] > 0 or counts["replay_warning_count"] > 0:
        return "DEGRADED"
    if counts["batch_completed"] == 0 or counts["notification_delivered"] == 0:
        return "WARNING"
    return "HEALTHY"


def aggregate_analytics_metrics(session: Session, *, counts: dict[str, Any], previous_counts: dict[str, Any] | None = None) -> list[_MetricDraft]:
    def delta_value(current: int, previous: int | None) -> str | None:
        if previous is None:
            return None
        return str(current - previous)

    def pct(current: int, total: int) -> str:
        if total <= 0:
            return "0.000000"
        return f"{current / total:.6f}"

    previous_counts = previous_counts or {}
    drafts = [
        _MetricDraft("queue_throughput", "THROUGHPUT", str(counts["queue_depth"]), delta_value(counts["queue_depth"], previous_counts.get("queue_depth")), "WARNING" if counts["queue_depth"] > 100 else "NORMAL", 10, {}),
        _MetricDraft("workflow_throughput", "THROUGHPUT", str(counts["workflow_throughput"]), delta_value(counts["workflow_throughput"], previous_counts.get("workflow_throughput")), "NORMAL", 20, {}),
        _MetricDraft("worker_utilization", "UTILIZATION", pct(counts["active_workers"], counts["total_workers"]), None if previous_counts.get("total_workers") is None else pct(previous_counts.get("active_workers", 0), previous_counts.get("total_workers", 0)), "WARNING" if counts["active_workers"] == 0 else "NORMAL", 10, {}),
        _MetricDraft("failure_rate", "FAILURE", pct(counts["failed_jobs"], counts["total_jobs"]), None if previous_counts.get("total_jobs") is None else pct(previous_counts.get("failed_jobs", 0), previous_counts.get("total_jobs", 0)), "CRITICAL" if counts["failed_jobs"] > 5 else "WARNING" if counts["failed_jobs"] > 0 else "NORMAL", 10, {}),
        _MetricDraft("recovery_success_rate", "RECOVERY", pct(counts["recovery_success"], counts["batch_total"] or 1), None, "NORMAL", 10, {}),
        _MetricDraft("replay_warning_count", "REPLAY", str(counts["replay_warning_count"]), delta_value(counts["replay_warning_count"], previous_counts.get("replay_warning_count")), "WARNING" if counts["replay_warning_count"] else "NORMAL", 10, {}),
        _MetricDraft("dead_letter_growth", "FAILURE", str(counts["dead_letter_count"]), delta_value(counts["dead_letter_count"], previous_counts.get("dead_letter_count")), "WARNING" if counts["dead_letter_count"] else "NORMAL", 20, {}),
        _MetricDraft("batch_completion_rate", "THROUGHPUT", pct(counts["batch_completed"], counts["batch_total"] or 1), None, "NORMAL", 30, {}),
        _MetricDraft("notification_delivery_rate", "THROUGHPUT", pct(counts["notification_delivered"], counts["notification_total"] or 1), None, "NORMAL", 40, {}),
        _MetricDraft("alert_volume", "SYSTEM", str(counts["alert_volume"]), delta_value(counts["alert_volume"], previous_counts.get("alert_volume")), "NORMAL", 10, {}),
    ]
    drafts.sort(key=lambda row: (row.metric_category, row.metric_rank, row.metric_key))
    return drafts


def _previous_counts_from_metrics(metrics: list[AutomationAnalyticsMetric]) -> dict[str, Any]:
    mapping = {row.metric_key: row.metric_value for row in metrics}

    def integer(metric_key: str) -> int | None:
        value = mapping.get(metric_key)
        if value is None:
            return None
        try:
            return int(float(str(value)))
        except ValueError:
            return None

    return {
        "queue_depth": integer("queue_throughput"),
        "workflow_throughput": integer("workflow_throughput"),
        "replay_warning_count": integer("replay_warning_count"),
        "dead_letter_count": integer("dead_letter_growth"),
        "alert_volume": integer("alert_volume"),
        "active_workers": 1 if mapping.get("worker_utilization") is not None else None,
        "total_workers": 1 if mapping.get("worker_utilization") is not None else None,
        "failed_jobs": integer("failure_rate"),
        "total_jobs": 1 if mapping.get("failure_rate") is not None else None,
    }


def build_analytics_trends(session: Session, *, snapshot: AutomationAnalyticsSnapshot, metrics: list[AutomationAnalyticsMetric], previous_snapshot: AutomationAnalyticsSnapshot | None) -> list[_TrendDraft]:
    current = {row.metric_key: row for row in metrics}
    previous_metrics = {}
    if previous_snapshot is not None:
        previous_metrics = {
            row.metric_key: row
            for row in session.exec(select(AutomationAnalyticsMetric).where(AutomationAnalyticsMetric.snapshot_id == previous_snapshot.id)).all()
        }

    def trend(key: str, trend_type: str, current_value: float, previous_value: float | None, window: int) -> _TrendDraft:
        delta = 0.0 if previous_value is None else current_value - previous_value
        direction = "STABLE"
        if delta > 0:
            direction = "UP"
        elif delta < 0:
            direction = "DOWN"
        return _TrendDraft(
            trend_key=key,
            trend_type=trend_type,
            trend_direction=direction,
            historical_window=window,
            trend_value=f"{delta:.6f}",
            metadata_json={
                "current": f"{current_value:.6f}",
                "previous": None if previous_value is None else f"{previous_value:.6f}",
                "snapshot_id": snapshot.id,
            },
        )

    queue_depth = float(current["queue_throughput"].metric_value)
    previous_queue_depth = float(previous_metrics["queue_throughput"].metric_value) if "queue_throughput" in previous_metrics else None
    failure_rate = float(current["failure_rate"].metric_value)
    previous_failure_rate = float(previous_metrics["failure_rate"].metric_value) if "failure_rate" in previous_metrics else None
    worker_utilization = float(current["worker_utilization"].metric_value)
    previous_worker_utilization = float(previous_metrics["worker_utilization"].metric_value) if "worker_utilization" in previous_metrics else None
    replay_warnings = float(current["replay_warning_count"].metric_value)
    previous_replay_warnings = float(previous_metrics["replay_warning_count"].metric_value) if "replay_warning_count" in previous_metrics else None
    batch_completion = float(current["batch_completion_rate"].metric_value)
    previous_batch_completion = float(previous_metrics["batch_completion_rate"].metric_value) if "batch_completion_rate" in previous_metrics else None
    alert_volume = float(current["alert_volume"].metric_value)
    previous_alert_volume = float(previous_metrics["alert_volume"].metric_value) if "alert_volume" in previous_metrics else None
    workflow_throughput = float(current["workflow_throughput"].metric_value)
    previous_workflow_throughput = float(previous_metrics["workflow_throughput"].metric_value) if "workflow_throughput" in previous_metrics else None

    drafts = [
        trend("queue_growth", "QUEUE_GROWTH", queue_depth, previous_queue_depth, 7),
        trend("failure_rate", "FAILURE_RATE", failure_rate, previous_failure_rate, 7),
        trend("worker_utilization", "WORKER_UTILIZATION", worker_utilization, previous_worker_utilization, 7),
        trend("replay_warning_rate", "REPLAY_WARNING_RATE", replay_warnings, previous_replay_warnings, 7),
        trend("batch_growth", "BATCH_GROWTH", batch_completion, previous_batch_completion, 7),
        trend("alert_volume", "ALERT_VOLUME", alert_volume, previous_alert_volume, 7),
        trend("workflow_throughput", "WORKFLOW_THROUGHPUT", workflow_throughput, previous_workflow_throughput, 7),
    ]
    drafts.sort(key=lambda row: (row.trend_type, row.historical_window, row.trend_key))
    return drafts


def generate_analytics_comparisons(
    session: Session,
    *,
    snapshot: AutomationAnalyticsSnapshot,
    baseline_snapshot: AutomationAnalyticsSnapshot | None,
) -> list[_ComparisonDraft]:
    metrics = {
        row.metric_key: row
        for row in session.exec(select(AutomationAnalyticsMetric).where(AutomationAnalyticsMetric.snapshot_id == snapshot.id)).all()
    }
    baseline_metrics = {}
    if baseline_snapshot is not None:
        baseline_metrics = {
            row.metric_key: row
            for row in session.exec(select(AutomationAnalyticsMetric).where(AutomationAnalyticsMetric.snapshot_id == baseline_snapshot.id)).all()
        }

    comparisons: list[_ComparisonDraft] = []
    for comparison_type in sorted(_COMPARISON_TYPES):
        current_queue = float(metrics["queue_throughput"].metric_value)
        baseline_queue = float(baseline_metrics["queue_throughput"].metric_value) if "queue_throughput" in baseline_metrics else None
        current_failure = float(metrics["failure_rate"].metric_value)
        baseline_failure = float(baseline_metrics["failure_rate"].metric_value) if "failure_rate" in baseline_metrics else None
        current_util = float(metrics["worker_utilization"].metric_value)
        baseline_util = float(baseline_metrics["worker_utilization"].metric_value) if "worker_utilization" in baseline_metrics else None
        result = {
            "comparison_type": comparison_type,
            "current_snapshot_id": snapshot.id,
            "baseline_snapshot_id": None if baseline_snapshot is None else baseline_snapshot.id,
            "deltas": {
                "queue_throughput": None if baseline_queue is None else round(current_queue - baseline_queue, 6),
                "failure_rate": None if baseline_failure is None else round(current_failure - baseline_failure, 6),
                "worker_utilization": None if baseline_util is None else round(current_util - baseline_util, 6),
            },
            "status": "NO_BASELINE" if baseline_snapshot is None else "COMPARED",
        }
        comparisons.append(
            _ComparisonDraft(
                comparison_key=f"{comparison_type.lower()}:{snapshot.id}",
                comparison_type=comparison_type,
                baseline_snapshot_id=None if baseline_snapshot is None else baseline_snapshot.id,
                comparison_result_json=result,
                metadata_json={"snapshot_id": snapshot.id},
            )
        )
    return sorted(comparisons, key=lambda row: (row.comparison_type, row.comparison_key))


def build_analytics_manifest(
    *,
    snapshot: AutomationAnalyticsSnapshot,
    metrics: list[AutomationAnalyticsMetric],
    trends: list[AutomationAnalyticsTrend],
    comparisons: list[AutomationAnalyticsComparison],
    issues: list[AutomationAnalyticsIssue],
    artifacts: list[AutomationAnalyticsArtifact],
) -> dict[str, Any]:
    return _json_safe(
        {
            "engine_version": ENGINE_VERSION,
            "snapshot": {
                "id": snapshot.id,
                "snapshot_key": snapshot.snapshot_key,
                "analytics_type": snapshot.analytics_type,
                "analytics_status": snapshot.analytics_status,
                "snapshot_checksum": snapshot.snapshot_checksum,
            },
            "metric_lineage": [
                {"metric_key": row.metric_key, "metric_category": row.metric_category, "metric_rank": row.metric_rank, "metric_checksum": row.metric_checksum}
                for row in sorted(metrics, key=lambda item: (item.metric_category, item.metric_rank, item.metric_key))
            ],
            "trend_lineage": [
                {"trend_key": row.trend_key, "trend_type": row.trend_type, "trend_direction": row.trend_direction, "trend_checksum": row.trend_checksum}
                for row in sorted(trends, key=lambda item: (item.trend_type, item.historical_window, item.trend_key))
            ],
            "comparison_lineage": [
                {"comparison_key": row.comparison_key, "comparison_type": row.comparison_type, "comparison_checksum": row.comparison_checksum}
                for row in sorted(comparisons, key=lambda item: (item.comparison_type, item.comparison_key))
            ],
            "issues": [
                {"issue_type": row.issue_type, "severity": row.severity, "issue_checksum": row.issue_checksum}
                for row in sorted(issues, key=lambda item: (item.severity, item.issue_type))
            ],
            "artifacts": [
                {"artifact_type": row.artifact_type, "artifact_checksum": row.artifact_checksum, "storage_path": row.storage_path}
                for row in sorted(artifacts, key=lambda item: (item.artifact_type, item.storage_path))
            ],
        }
    )


def _persist_metrics(session: Session, *, snapshot_id: int, drafts: list[_MetricDraft]) -> list[AutomationAnalyticsMetric]:
    rows: list[AutomationAnalyticsMetric] = []
    for draft in drafts:
        payload = {
            "snapshot_id": snapshot_id,
            "metric_key": draft.metric_key,
            "metric_category": draft.metric_category,
            "metric_value": draft.metric_value,
            "metric_delta": draft.metric_delta,
            "metric_status": draft.metric_status,
            "metric_rank": draft.metric_rank,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationAnalyticsMetric(
            snapshot_id=snapshot_id,
            metric_key=draft.metric_key,
            metric_category=draft.metric_category,
            metric_value=draft.metric_value,
            metric_delta=draft.metric_delta,
            metric_status=draft.metric_status,
            metric_rank=draft.metric_rank,
            metric_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _persist_trends(session: Session, *, snapshot_id: int, drafts: list[_TrendDraft]) -> list[AutomationAnalyticsTrend]:
    rows: list[AutomationAnalyticsTrend] = []
    for draft in drafts:
        payload = {
            "snapshot_id": snapshot_id,
            "trend_key": draft.trend_key,
            "trend_type": draft.trend_type,
            "trend_direction": draft.trend_direction,
            "historical_window": draft.historical_window,
            "trend_value": draft.trend_value,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationAnalyticsTrend(
            snapshot_id=snapshot_id,
            trend_key=draft.trend_key,
            trend_type=draft.trend_type,
            trend_direction=draft.trend_direction,
            historical_window=draft.historical_window,
            trend_value=draft.trend_value,
            trend_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _persist_comparisons(session: Session, *, snapshot_id: int, drafts: list[_ComparisonDraft]) -> list[AutomationAnalyticsComparison]:
    rows: list[AutomationAnalyticsComparison] = []
    for draft in drafts:
        payload = {
            "snapshot_id": snapshot_id,
            "comparison_key": draft.comparison_key,
            "comparison_type": draft.comparison_type,
            "baseline_snapshot_id": draft.baseline_snapshot_id,
            "comparison_result_json": draft.comparison_result_json,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationAnalyticsComparison(
            snapshot_id=snapshot_id,
            comparison_key=draft.comparison_key,
            comparison_type=draft.comparison_type,
            baseline_snapshot_id=draft.baseline_snapshot_id,
            comparison_result_json=_json_safe(draft.comparison_result_json),
            comparison_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _write_analytics_artifacts(
    settings: Settings,
    session: Session,
    *,
    snapshot: AutomationAnalyticsSnapshot,
    manifest: dict[str, Any],
) -> list[AutomationAnalyticsArtifact]:
    assert snapshot.id is not None
    artifacts: list[AutomationAnalyticsArtifact] = []
    specs = [
        ("ANALYTICS_REPORT", {"summary": manifest.get("snapshot"), "metadata": snapshot.metadata_json}),
        ("TREND_EXPORT", {"trend_lineage": manifest.get("trend_lineage")}),
        ("COMPARISON_EXPORT", {"comparison_lineage": manifest.get("comparison_lineage")}),
        ("ANALYTICS_MANIFEST", manifest),
        ("ANALYTICS_DEBUG_PREVIEW", {"snapshot_id": snapshot.id, "engine_version": ENGINE_VERSION}),
    ]
    for artifact_type, payload in specs:
        body = _serialize_json_artifact(payload)
        relative = _analytics_artifact_path(analytics_type=snapshot.analytics_type, snapshot_id=snapshot.id, artifact_type=artifact_type, ext=".json")
        _save_analytics_artifact_bytes(settings, relative_path=relative, body=body)
        row = AutomationAnalyticsArtifact(
            snapshot_id=snapshot.id,
            artifact_type=artifact_type,
            storage_path=relative,
            artifact_checksum=_hash_payload({"path": relative, "body_sha256": hashlib.sha256(body).hexdigest()}),
            metadata_json={"byte_length": len(body)},
        )
        session.add(row)
        artifacts.append(row)
    session.flush()
    return artifacts


def _snapshot_to_read(snapshot: AutomationAnalyticsSnapshot) -> AutomationAnalyticsSnapshotRead:
    return AutomationAnalyticsSnapshotRead.model_validate(snapshot)


def _snapshot_ids_for_owner(session: Session, *, owner_user_id: int) -> list[int]:
    return [
        int(row.id)
        for row in session.exec(select(AutomationAnalyticsSnapshot).where(AutomationAnalyticsSnapshot.owner_user_id == owner_user_id)).all()
        if row.id is not None
    ]


def _latest_baseline_snapshot(
    session: Session,
    *,
    owner_user_id: int | None,
    analytics_type: str,
    exclude_snapshot_id: int | None = None,
) -> AutomationAnalyticsSnapshot | None:
    query = select(AutomationAnalyticsSnapshot).where(
        AutomationAnalyticsSnapshot.analytics_type == analytics_type,
    )
    if exclude_snapshot_id is not None:
        query = query.where(AutomationAnalyticsSnapshot.id != exclude_snapshot_id)
    if owner_user_id is not None:
        query = query.where(AutomationAnalyticsSnapshot.owner_user_id == owner_user_id)
    rows = list(session.exec(query.order_by(col(AutomationAnalyticsSnapshot.created_at).desc(), col(AutomationAnalyticsSnapshot.id).desc())).all())
    return rows[0] if rows else None


def create_analytics_snapshot(
    session: Session,
    settings: Settings,
    *,
    payload: AutomationAnalyticsSnapshotCreate,
) -> tuple[AutomationAnalyticsSnapshotRead, bool]:
    analytics_type = str(payload.analytics_type).upper()
    if analytics_type not in _ANALYTICS_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported analytics_type: {analytics_type}")

    snapshot_key = f"{payload.owner_user_id or 0}:{analytics_type}:{payload.replay_key}"
    existing = session.exec(
        select(AutomationAnalyticsSnapshot).where(
            AutomationAnalyticsSnapshot.owner_user_id == payload.owner_user_id,
            AutomationAnalyticsSnapshot.snapshot_key == snapshot_key,
        )
    ).first()
    if existing is not None:
        return _snapshot_to_read(existing), False

    counts = _analytics_counts(session, owner_user_id=payload.owner_user_id)
    previous_snapshot = _latest_baseline_snapshot(session, owner_user_id=payload.owner_user_id, analytics_type=analytics_type)
    previous_counts = None
    if previous_snapshot is not None:
        previous_metric_rows = list(session.exec(select(AutomationAnalyticsMetric).where(AutomationAnalyticsMetric.snapshot_id == previous_snapshot.id)).all())
        previous_counts = _previous_counts_from_metrics(previous_metric_rows)

    metric_drafts = aggregate_analytics_metrics(session, counts=counts, previous_counts=previous_counts)
    snapshot_status = _analytics_status(counts)

    pre_checksum = _hash_payload(
        {
            "snapshot_key": snapshot_key,
            "analytics_type": analytics_type,
            "analytics_scope": payload.analytics_scope,
            "counts": counts,
            "metrics": [draft.__dict__ for draft in metric_drafts],
            "metadata_json": payload.metadata_json,
        }
    )

    snapshot = AutomationAnalyticsSnapshot(
        owner_user_id=payload.owner_user_id,
        snapshot_key=snapshot_key,
        analytics_type=analytics_type,
        analytics_scope=payload.analytics_scope,
        analytics_status=snapshot_status,
        replay_safe=True,
        deterministic_ordering_enabled=True,
        snapshot_checksum=pre_checksum,
        snapshot_manifest_json={},
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None

    metrics = _persist_metrics(session, snapshot_id=snapshot.id, drafts=metric_drafts)
    baseline_snapshot = _latest_baseline_snapshot(session, owner_user_id=payload.owner_user_id, analytics_type=analytics_type, exclude_snapshot_id=snapshot.id)
    trend_drafts = build_analytics_trends(session, snapshot=snapshot, metrics=metrics, previous_snapshot=baseline_snapshot)
    trends = _persist_trends(session, snapshot_id=snapshot.id, drafts=trend_drafts)
    comparison_drafts = generate_analytics_comparisons(session, snapshot=snapshot, baseline_snapshot=baseline_snapshot)
    comparisons = _persist_comparisons(session, snapshot_id=snapshot.id, drafts=comparison_drafts)

    issue_drafts: list[_IssueDraft] = []
    if counts["replay_warning_count"] > 0:
        issue_drafts.append(_IssueDraft("REPLAY_ANALYTICS_DRIFT", "WARNING", "Replay warning trend detected.", {"snapshot_id": snapshot.id}))
    if counts["failed_jobs"] > 0:
        issue_drafts.append(_IssueDraft("FAILURE_RATE_WARNING", "WARNING", "Failure rate elevated.", {"snapshot_id": snapshot.id}))
    if counts["active_workers"] == 0:
        issue_drafts.append(_IssueDraft("UTILIZATION_WARNING", "WARNING", "Worker utilization is low.", {"snapshot_id": snapshot.id}))
    if baseline_snapshot is not None and baseline_snapshot.snapshot_key == snapshot.snapshot_key:
        issue_drafts.append(_IssueDraft("ANALYTICS_BASELINE_CONFLICT", "INFO", "Baseline snapshot matches current snapshot key.", {"snapshot_id": snapshot.id}))

    issues = _record_issues(session, drafts=issue_drafts)
    manifest = build_analytics_manifest(snapshot=snapshot, metrics=metrics, trends=trends, comparisons=comparisons, issues=issues, artifacts=[])
    snapshot.snapshot_manifest_json = manifest
    snapshot.snapshot_checksum = _hash_payload({"manifest_checksum": _hash_payload(manifest), "snapshot_key": snapshot_key})

    artifacts = _write_analytics_artifacts(settings, session, snapshot=snapshot, manifest=manifest)
    manifest = build_analytics_manifest(snapshot=snapshot, metrics=metrics, trends=trends, comparisons=comparisons, issues=issues, artifacts=artifacts)
    snapshot.snapshot_manifest_json = manifest
    snapshot.snapshot_checksum = _hash_payload(
        {
            "manifest_checksum": _hash_payload(manifest),
            "snapshot_key": snapshot_key,
            "artifact_checksums": [row.artifact_checksum for row in artifacts],
        }
    )

    _record_history(
        session,
        draft=_HistoryDraft(
            event_type="ANALYTICS_SNAPSHOT_CREATED",
            event_message=f"Analytics snapshot {analytics_type} created.",
            metadata_json={"snapshot_key": snapshot_key, "engine_version": ENGINE_VERSION},
            snapshot_id=snapshot.id,
            to_status=snapshot.analytics_status,
        ),
    )
    session.commit()
    session.refresh(snapshot)
    return _snapshot_to_read(snapshot), True


def get_automation_analytics_snapshot_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> AutomationAnalyticsSnapshotRead:
    row = session.get(AutomationAnalyticsSnapshot, snapshot_id)
    if row is None or int(row.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation analytics snapshot not found.")
    return _snapshot_to_read(row)


def _snapshot_list_response(session: Session, *, rows: list[AutomationAnalyticsSnapshot], limit: int, offset: int) -> AutomationAnalyticsListResponse:
    items = [_snapshot_to_read(row) for row in rows[offset : offset + limit]]
    issue_rows = list(session.exec(select(AutomationAnalyticsIssue)).all())
    return AutomationAnalyticsListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        replay_drift_count=len([row for row in issue_rows if row.issue_type == "REPLAY_ANALYTICS_DRIFT"]),
        failure_warning_count=len([row for row in issue_rows if row.issue_type == "FAILURE_RATE_WARNING"]),
        utilization_warning_count=len([row for row in issue_rows if row.issue_type == "UTILIZATION_WARNING"]),
    )


def list_automation_analytics_snapshots_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationAnalyticsListResponse:
    limit, offset = clamp_automation_analytics_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationAnalyticsSnapshot)
            .where(AutomationAnalyticsSnapshot.owner_user_id == owner_user_id)
            .order_by(col(AutomationAnalyticsSnapshot.analytics_type), col(AutomationAnalyticsSnapshot.created_at), col(AutomationAnalyticsSnapshot.id))
        ).all()
    )
    return _snapshot_list_response(session, rows=rows, limit=limit, offset=offset)


def list_automation_analytics_snapshots_ops(session: Session, *, limit: int, offset: int) -> AutomationAnalyticsListResponse:
    limit, offset = clamp_automation_analytics_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationAnalyticsSnapshot).order_by(col(AutomationAnalyticsSnapshot.analytics_type), col(AutomationAnalyticsSnapshot.created_at), col(AutomationAnalyticsSnapshot.id))).all())
    return _snapshot_list_response(session, rows=rows, limit=limit, offset=offset)


def _metric_list_response(session: Session, *, rows: list[AutomationAnalyticsMetric], limit: int, offset: int) -> AutomationAnalyticsListResponse:
    warnings = len([row for row in rows if row.metric_status == "WARNING"])
    return AutomationAnalyticsListResponse(
        items=[AutomationAnalyticsMetricRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        failure_warning_count=warnings,
    )


def list_automation_analytics_metrics(session: Session, *, owner_user_id: int | None, snapshot_id: int | None, limit: int, offset: int) -> AutomationAnalyticsListResponse:
    limit, offset = clamp_automation_analytics_pagination(limit=limit, offset=offset)
    query = select(AutomationAnalyticsMetric)
    if snapshot_id is not None:
        query = query.where(AutomationAnalyticsMetric.snapshot_id == snapshot_id)
    rows = list(session.exec(query.order_by(col(AutomationAnalyticsMetric.metric_category), col(AutomationAnalyticsMetric.metric_rank), col(AutomationAnalyticsMetric.metric_key), col(AutomationAnalyticsMetric.id))).all())
    if owner_user_id is not None:
        snapshot_ids = _snapshot_ids_for_owner(session, owner_user_id=owner_user_id)
        rows = [row for row in rows if row.snapshot_id in snapshot_ids]
    return _metric_list_response(session, rows=rows, limit=limit, offset=offset)


def _trend_list_response(rows: list[AutomationAnalyticsTrend], limit: int, offset: int) -> AutomationAnalyticsListResponse:
    return AutomationAnalyticsListResponse(
        items=[AutomationAnalyticsTrendRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def list_automation_analytics_trends(session: Session, *, owner_user_id: int | None, snapshot_id: int | None, limit: int, offset: int) -> AutomationAnalyticsListResponse:
    limit, offset = clamp_automation_analytics_pagination(limit=limit, offset=offset)
    query = select(AutomationAnalyticsTrend)
    if snapshot_id is not None:
        query = query.where(AutomationAnalyticsTrend.snapshot_id == snapshot_id)
    rows = list(session.exec(query.order_by(col(AutomationAnalyticsTrend.trend_type), col(AutomationAnalyticsTrend.historical_window), col(AutomationAnalyticsTrend.trend_key), col(AutomationAnalyticsTrend.id))).all())
    if owner_user_id is not None:
        snapshot_ids = _snapshot_ids_for_owner(session, owner_user_id=owner_user_id)
        rows = [row for row in rows if row.snapshot_id in snapshot_ids]
    return _trend_list_response(rows, limit=limit, offset=offset)


def _comparison_list_response(rows: list[AutomationAnalyticsComparison], limit: int, offset: int) -> AutomationAnalyticsListResponse:
    return AutomationAnalyticsListResponse(
        items=[AutomationAnalyticsComparisonRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def list_automation_analytics_comparisons(session: Session, *, owner_user_id: int | None, snapshot_id: int | None, limit: int, offset: int) -> AutomationAnalyticsListResponse:
    limit, offset = clamp_automation_analytics_pagination(limit=limit, offset=offset)
    query = select(AutomationAnalyticsComparison)
    if snapshot_id is not None:
        query = query.where(AutomationAnalyticsComparison.snapshot_id == snapshot_id)
    rows = list(session.exec(query.order_by(col(AutomationAnalyticsComparison.comparison_type), col(AutomationAnalyticsComparison.comparison_key), col(AutomationAnalyticsComparison.id))).all())
    if owner_user_id is not None:
        snapshot_ids = _snapshot_ids_for_owner(session, owner_user_id=owner_user_id)
        rows = [row for row in rows if row.snapshot_id in snapshot_ids]
    return _comparison_list_response(rows, limit=limit, offset=offset)


def _issue_list_response(rows: list[AutomationAnalyticsIssue], limit: int, offset: int) -> AutomationAnalyticsListResponse:
    warnings = len([row for row in rows if row.severity == "WARNING"])
    return AutomationAnalyticsListResponse(
        items=[AutomationAnalyticsIssueRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        replay_drift_count=len([row for row in rows if row.issue_type == "REPLAY_ANALYTICS_DRIFT"]),
        failure_warning_count=len([row for row in rows if row.issue_type == "FAILURE_RATE_WARNING"]),
        utilization_warning_count=len([row for row in rows if row.issue_type == "UTILIZATION_WARNING"]),
    )


def list_automation_analytics_issues(session: Session, *, owner_user_id: int | None, snapshot_id: int | None, limit: int, offset: int) -> AutomationAnalyticsListResponse:
    limit, offset = clamp_automation_analytics_pagination(limit=limit, offset=offset)
    query = select(AutomationAnalyticsIssue)
    if snapshot_id is not None:
        query = query.where(AutomationAnalyticsIssue.snapshot_id == snapshot_id)
    rows = list(session.exec(query.order_by(col(AutomationAnalyticsIssue.created_at).desc(), col(AutomationAnalyticsIssue.id).desc())).all())
    if owner_user_id is not None:
        snapshot_ids = _snapshot_ids_for_owner(session, owner_user_id=owner_user_id)
        rows = [row for row in rows if row.snapshot_id in snapshot_ids]
    return _issue_list_response(rows, limit=limit, offset=offset)


def get_automation_analytics_system_intelligence(session: Session, *, owner_user_id: int | None) -> AutomationAnalyticsSystemIntelligenceRead:
    snapshots = list_automation_analytics_snapshots_owner(session, owner_user_id=owner_user_id, limit=1, offset=0) if owner_user_id is not None else list_automation_analytics_snapshots_ops(session, limit=1, offset=0)
    latest = snapshots.items[0] if snapshots.items else None
    counts = _analytics_counts(session, owner_user_id=owner_user_id)
    analytics_status = _analytics_status(counts)
    return AutomationAnalyticsSystemIntelligenceRead(
        analytics_status=analytics_status,
        queue_throughput=counts["queue_depth"],
        worker_utilization=f"{0 if counts['total_workers'] == 0 else counts['active_workers'] / counts['total_workers']:.6f}",
        failure_rate=f"{0 if counts['total_jobs'] == 0 else counts['failed_jobs'] / counts['total_jobs']:.6f}",
        replay_warning_trend_count=counts["replay_warning_count"],
        dead_letter_growth=counts["dead_letter_count"],
        workflow_throughput=counts["workflow_throughput"],
        notification_delivery_rate=f"{0 if counts['notification_total'] == 0 else counts['notification_delivered'] / counts['notification_total']:.6f}",
        batch_completion_rate=f"{0 if counts['batch_total'] == 0 else counts['batch_completed'] / counts['batch_total']:.6f}",
        latest_snapshot_id=latest.id if latest is not None else None,
        latest_snapshot_checksum=latest.snapshot_checksum if latest is not None else None,
    )
