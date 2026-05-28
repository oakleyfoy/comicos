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
    AutomationNotification,
    AutomationNotificationDelivery,
    AutomationNotificationHistory,
    AutomationNotificationIssue,
    AutomationNotificationPreference,
    AutomationNotificationTemplate,
)
from app.schemas.automation_notifications import (
    AutomationAlertListResponse,
    AutomationAlertRead,
    AutomationNotificationArtifactRead,
    AutomationNotificationCreate,
    AutomationNotificationHistoryRead,
    AutomationNotificationDeliveryListResponse,
    AutomationNotificationDeliveryRead,
    AutomationNotificationIssueListResponse,
    AutomationNotificationIssueRead,
    AutomationNotificationListResponse,
    AutomationNotificationPreferenceListResponse,
    AutomationNotificationPreferenceRead,
    AutomationNotificationRead,
)

ENGINE_VERSION = "P41-06-v1"
_NOTIFICATION_TYPES = {
    "SYSTEM_ALERT",
    "WORKFLOW_FAILURE",
    "DEAD_LETTER_ALERT",
    "REPLAY_WARNING",
    "REVIEW_REQUIRED",
    "AUTHENTICATION_WARNING",
    "MAINTENANCE_RESULT",
    "QUEUE_WARNING",
    "BATCH_FAILURE",
    "OPS_NOTIFICATION",
}
_NOTIFICATION_STATUSES = {"CREATED", "QUEUED", "DELIVERED", "FAILED", "ACKNOWLEDGED", "SUPPRESSED"}
_DELIVERY_CHANNELS = {"IN_APP", "EMAIL_FUTURE", "SMS_FUTURE", "OPS_CONSOLE", "WEBHOOK_FUTURE"}
_ALERT_TYPES = {
    "WORKFLOW_FAILURE",
    "DEAD_LETTER_ALERT",
    "REPLAY_DRIFT",
    "CHECKSUM_FAILURE",
    "STORAGE_AUDIT_FAILURE",
    "QUEUE_HEALTH_ALERT",
    "WORKER_RUNTIME_ALERT",
    "SYSTEM_HEALTH_ALERT",
}
_ESCALATION_LEVELS = ("LEVEL_1", "LEVEL_2", "LEVEL_3")
_DEFAULT_CHANNEL_ORDER = ("IN_APP", "OPS_CONSOLE", "EMAIL_FUTURE", "SMS_FUTURE", "WEBHOOK_FUTURE")
_ROUTING_BY_NOTIFICATION_TYPE: dict[str, tuple[str, str, str]] = {
    "WORKFLOW_FAILURE": ("WORKFLOW_FAILURE", "ERROR", "LEVEL_2"),
    "DEAD_LETTER_ALERT": ("DEAD_LETTER_ALERT", "ERROR", "LEVEL_2"),
    "REPLAY_WARNING": ("REPLAY_DRIFT", "WARNING", "LEVEL_1"),
    "BATCH_FAILURE": ("CHECKSUM_FAILURE", "ERROR", "LEVEL_2"),
    "MAINTENANCE_RESULT": ("STORAGE_AUDIT_FAILURE", "WARNING", "LEVEL_1"),
    "QUEUE_WARNING": ("QUEUE_HEALTH_ALERT", "WARNING", "LEVEL_1"),
    "OPS_NOTIFICATION": ("SYSTEM_HEALTH_ALERT", "INFO", "LEVEL_1"),
}
_TEMPLATE_BLUEPRINTS: dict[str, dict[str, str]] = {
    "WORKFLOW_FAILURE": {
        "template_name": "Workflow failure",
        "template_category": "FAILURE",
        "subject_template": "Workflow failure: {source_event_type}",
        "body_template": "Automation workflow failure detected for {source_event_type}.",
    },
    "DEAD_LETTER_ALERT": {
        "template_name": "Dead letter alert",
        "template_category": "FAILURE",
        "subject_template": "Dead letter alert: {source_event_type}",
        "body_template": "A job was transferred to dead letter for {source_event_type}.",
    },
    "REPLAY_WARNING": {
        "template_name": "Replay warning",
        "template_category": "WARNING",
        "subject_template": "Replay warning: {source_event_type}",
        "body_template": "Replay drift or warning detected for {source_event_type}.",
    },
    "DEFAULT": {
        "template_name": "Operational notification",
        "template_category": "OPS",
        "subject_template": "Notification: {notification_type}",
        "body_template": "Operational notification {notification_type} for {source_event_type}.",
    },
}


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    notification_id: int | None = None
    alert_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]
    notification_id: int | None = None


def utc_now() -> datetime:
    from app.models.automation_notifications import utc_now as _utc_now

    return _utc_now()


def clamp_automation_notification_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_notification_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_notifications_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation notification storage path escapes configured root")
    return target


def _save_notification_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_notification_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _notification_artifact_path(*, notification_type: str, notification_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-notifications/{notification_type.lower()}/{notification_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _record_notification_history(session: Session, *, draft: _HistoryDraft) -> None:
    payload = {
        "notification_id": draft.notification_id,
        "alert_id": draft.alert_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationNotificationHistory(
            notification_id=draft.notification_id,
            alert_id=draft.alert_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_notification_issue(session: Session, *, draft: _IssueDraft) -> None:
    payload = {
        "notification_id": draft.notification_id,
        "issue_type": draft.issue_type,
        "severity": draft.severity,
        "issue_message": draft.issue_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationNotificationIssue(
            notification_id=draft.notification_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _ensure_template(session: Session, *, notification_type: str) -> AutomationNotificationTemplate:
    blueprint = _TEMPLATE_BLUEPRINTS.get(notification_type, _TEMPLATE_BLUEPRINTS["DEFAULT"])
    snapshot = {
        "template_name": blueprint["template_name"],
        "template_category": blueprint["template_category"],
        "subject_template": blueprint["subject_template"],
        "body_template": blueprint["body_template"],
        "notification_type": notification_type,
    }
    checksum = _hash_payload(snapshot)
    template_key = _hash_payload({"notification_type": notification_type, "checksum": checksum})[:24]
    existing = session.exec(select(AutomationNotificationTemplate).where(AutomationNotificationTemplate.template_checksum == checksum)).first()
    if existing is not None:
        return existing
    row = AutomationNotificationTemplate(
        template_key=template_key,
        template_name=blueprint["template_name"],
        template_category=blueprint["template_category"],
        template_status="ACTIVE",
        subject_template=blueprint["subject_template"],
        body_template=blueprint["body_template"],
        replay_safe=True,
        template_checksum=checksum,
        metadata_json={"notification_type": notification_type},
    )
    session.add(row)
    session.flush()
    return row


def resolve_notification_template(
    session: Session,
    *,
    notification_type: str,
    context: dict[str, Any],
) -> tuple[str, str, AutomationNotificationTemplate]:
    template = _ensure_template(session, notification_type=notification_type)
    if template.template_status != "ACTIVE":
        raise HTTPException(status_code=422, detail="Invalid notification template.")
    safe_context = {str(k): str(v) for k, v in _json_safe(context).items()}
    subject = template.subject_template.format_map({**safe_context, "notification_type": notification_type})
    body = template.body_template.format_map({**safe_context, "notification_type": notification_type})
    return subject, body, template


def process_notification_preferences(
    session: Session,
    *,
    owner_user_id: int,
    notification_type: str,
    channels: list[str],
) -> tuple[list[str], bool]:
    prefs = list(
        session.exec(
            select(AutomationNotificationPreference).where(AutomationNotificationPreference.owner_user_id == owner_user_id)
        ).all()
    )
    if not prefs:
        return channels, False
    enabled_channels: list[str] = []
    suppressed = False
    now = utc_now()
    for channel in channels:
        matching = [
            pref
            for pref in prefs
            if pref.notification_type == notification_type and pref.delivery_channel == channel
        ]
        if not matching:
            enabled_channels.append(channel)
            continue
        pref = matching[0]
        if not pref.enabled:
            continue
        quiet = pref.quiet_hours_json or {}
        if isinstance(quiet, dict) and quiet.get("start_hour") is not None and quiet.get("end_hour") is not None:
            hour = now.hour
            start_hour = int(quiet["start_hour"])
            end_hour = int(quiet["end_hour"])
            if start_hour <= end_hour and start_hour <= hour < end_hour:
                suppressed = True
                continue
            if start_hour > end_hour and (hour >= start_hour or hour < end_hour):
                suppressed = True
                continue
        enabled_channels.append(channel)
    return enabled_channels, suppressed


def build_notification_manifest(
    *,
    notification: AutomationNotification,
    template: AutomationNotificationTemplate | None,
    rendered: dict[str, str],
    deliveries: list[AutomationNotificationDelivery],
    alerts: list[AutomationAlert],
    issues: list[AutomationNotificationIssue],
    artifacts: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "notification_payload": _json_safe(notification.notification_payload_json),
        "template_lineage": _json_safe(template.model_dump() if template else None),
        "rendered": _json_safe(rendered),
        "delivery_lineage": _json_safe(
            sorted(
                [
                    {
                        "delivery_channel": row.delivery_channel,
                        "delivery_status": row.delivery_status,
                        "delivery_rank": row.delivery_rank,
                        "delivery_checksum": row.delivery_checksum,
                    }
                    for row in deliveries
                ],
                key=lambda row: (row["delivery_rank"], row["delivery_channel"]),
            )
        ),
        "alert_lineage": _json_safe(
            sorted(
                [
                    {
                        "alert_type": row.alert_type,
                        "alert_severity": row.alert_severity,
                        "escalation_level": row.escalation_level,
                        "alert_checksum": row.alert_checksum,
                    }
                    for row in alerts
                ],
                key=lambda row: (row["alert_severity"], row["alert_type"]),
            )
        ),
        "issues": _json_safe(
            [
                {"issue_type": row.issue_type, "severity": row.severity, "issue_checksum": row.issue_checksum}
                for row in sorted(issues, key=lambda issue: (issue.severity, issue.issue_type))
            ]
        ),
        "artifacts": _json_safe(sorted(artifacts, key=lambda row: (row["artifact_type"], row["artifact_checksum"]))),
    }
    return manifest, _hash_payload(manifest)


def queue_notification_delivery(
    session: Session,
    *,
    notification: AutomationNotification,
    channels: list[str],
    owner_user_id: int,
) -> list[AutomationNotificationDelivery]:
    ordered_channels = [channel for channel in _DEFAULT_CHANNEL_ORDER if channel in channels]
    for channel in channels:
        if channel not in ordered_channels:
            ordered_channels.append(channel)
    rows: list[AutomationNotificationDelivery] = []
    for rank, channel in enumerate(ordered_channels, start=1):
        destination_key = f"owner:{owner_user_id}" if channel == "IN_APP" else f"ops:{channel.lower()}"
        payload = {
            "notification_id": notification.id,
            "delivery_channel": channel,
            "delivery_rank": rank,
            "destination_key": destination_key,
        }
        checksum = _hash_payload(payload)
        existing = session.exec(
            select(AutomationNotificationDelivery).where(
                AutomationNotificationDelivery.notification_id == notification.id,
                AutomationNotificationDelivery.delivery_checksum == checksum,
            )
        ).first()
        if existing is not None:
            rows.append(existing)
            continue
        row = AutomationNotificationDelivery(
            notification_id=int(notification.id),
            delivery_channel=channel,
            delivery_status="PENDING",
            delivery_rank=rank,
            destination_key=destination_key,
            delivery_checksum=checksum,
            metadata_json={},
        )
        session.add(row)
        session.flush()
        rows.append(row)
    return rows


def _execute_deliveries(session: Session, *, notification: AutomationNotification, deliveries: list[AutomationNotificationDelivery]) -> None:
    now = utc_now()
    force_fail_channels = notification.metadata_json.get("force_failed_channels", [])
    fail_set = {str(channel) for channel in force_fail_channels} if isinstance(force_fail_channels, list) else set()
    for delivery in sorted(deliveries, key=lambda row: (row.delivery_rank, row.created_at, row.id or 0)):
        delivery.attempted_at = now
        if delivery.delivery_channel in fail_set or delivery.delivery_channel in {"EMAIL_FUTURE", "SMS_FUTURE", "WEBHOOK_FUTURE"}:
            delivery.delivery_status = "SKIPPED" if delivery.delivery_channel in {"EMAIL_FUTURE", "SMS_FUTURE", "WEBHOOK_FUTURE"} else "FAILED"
            if delivery.delivery_status == "FAILED":
                delivery.failure_reason = "Deterministic delivery failure."
                _record_notification_issue(
                    session,
                    draft=_IssueDraft(
                        notification_id=int(notification.id),
                        issue_type="DELIVERY_FAILURE",
                        severity="ERROR",
                        issue_message="Notification delivery failed.",
                        metadata_json={"delivery_channel": delivery.delivery_channel},
                    ),
                )
        else:
            delivery.delivery_status = "DELIVERED"
            delivery.delivered_at = now
        session.add(delivery)


def create_alert(
    session: Session,
    *,
    notification: AutomationNotification,
    alert_type: str,
    alert_severity: str,
    escalation_level: str,
) -> AutomationAlert:
    if alert_type not in _ALERT_TYPES:
        raise HTTPException(status_code=422, detail="Invalid alert type.")
    if escalation_level not in _ESCALATION_LEVELS:
        escalation_level = "LEVEL_1"
    snapshot = {
        "notification_id": notification.id,
        "alert_type": alert_type,
        "alert_severity": alert_severity,
        "escalation_level": escalation_level,
        "source_checksum": notification.source_checksum,
    }
    checksum = _hash_payload(snapshot)
    alert_key = _hash_payload({"alert_type": alert_type, "notification_id": notification.id, "checksum": checksum})[:24]
    existing = session.exec(select(AutomationAlert).where(AutomationAlert.alert_checksum == checksum)).first()
    if existing is not None:
        return existing
    alert = AutomationAlert(
        alert_key=alert_key,
        alert_type=alert_type,
        alert_severity=alert_severity,
        alert_status="ACTIVE",
        source_notification_id=int(notification.id),
        escalation_level=escalation_level,
        alert_checksum=checksum,
        replay_safe=notification.replay_safe,
        metadata_json={"notification_type": notification.notification_type},
    )
    session.add(alert)
    session.flush()
    _record_notification_history(
        session,
        draft=_HistoryDraft(
            notification_id=int(notification.id),
            alert_id=int(alert.id),
            event_type="ALERT_CREATED",
            event_message="Automation alert created.",
            metadata_json={"alert_type": alert_type, "escalation_level": escalation_level},
            to_status="ACTIVE",
        ),
    )
    return alert


def acknowledge_alert(session: Session, *, alert_id: int, metadata_json: dict[str, Any] | None = None) -> AutomationAlertRead:
    alert = session.get(AutomationAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Automation alert not found.")
    if alert.alert_status in {"ACKNOWLEDGED", "RESOLVED"}:
        return AutomationAlertRead.model_validate(alert)
    from_status = alert.alert_status
    alert.alert_status = "ACKNOWLEDGED"
    alert.acknowledged_at = utc_now()
    session.add(alert)
    _record_notification_history(
        session,
        draft=_HistoryDraft(
            notification_id=alert.source_notification_id,
            alert_id=int(alert.id),
            event_type="ALERT_ACKNOWLEDGED",
            event_message="Automation alert acknowledged.",
            metadata_json=_json_safe(metadata_json or {}),
            from_status=from_status,
            to_status="ACKNOWLEDGED",
        ),
    )
    session.commit()
    session.refresh(alert)
    return AutomationAlertRead.model_validate(alert)


def _write_notification_artifacts(
    settings: Settings,
    *,
    notification: AutomationNotification,
    manifest: dict[str, Any],
    deliveries: list[AutomationNotificationDelivery],
    alerts: list[AutomationAlert],
) -> list[dict[str, Any]]:
    artifact_refs: list[dict[str, Any]] = []
    payloads = [
        ("NOTIFICATION_EXPORT", _serialize_json_artifact(notification.notification_payload_json)),
        ("DELIVERY_EXPORT", _serialize_json_artifact([row.model_dump() for row in deliveries])),
        ("ALERT_REPORT", _serialize_json_artifact([row.model_dump() for row in alerts])),
        ("NOTIFICATION_MANIFEST", _serialize_json_artifact(manifest)),
        ("NOTIFICATION_DEBUG_PREVIEW", _serialize_json_artifact({"notification_id": notification.id, "notification_type": notification.notification_type})),
    ]
    for artifact_type, body in payloads:
        storage_path = _notification_artifact_path(
            notification_type=notification.notification_type,
            notification_id=int(notification.id),
            artifact_type=artifact_type,
            ext=".json",
        )
        _save_notification_artifact_bytes(settings, relative_path=storage_path, body=body)
        artifact_refs.append(
            {
                "artifact_type": artifact_type,
                "storage_path": storage_path,
                "artifact_checksum": _sha256_bytes(body),
            }
        )
    return artifact_refs


def create_notification(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: AutomationNotificationCreate,
) -> tuple[AutomationNotificationRead, bool]:
    if str(payload.notification_type) not in _NOTIFICATION_TYPES:
        raise HTTPException(status_code=422, detail="Invalid notification type.")
    effective_owner_user_id = int(payload.owner_user_id or owner_user_id)
    snapshot = {
        "owner_user_id": effective_owner_user_id,
        "notification_type": str(payload.notification_type),
        "source_event_type": payload.source_event_type,
        "source_record_type": payload.source_record_type,
        "source_record_id": payload.source_record_id,
        "source_checksum": payload.source_checksum,
        "notification_payload_json": payload.notification_payload_json,
        "replay_safe": payload.replay_safe,
        "metadata_json": payload.metadata_json,
    }
    base_checksum = _hash_payload(snapshot)
    notification_key = _hash_payload({"notification_type": payload.notification_type, "checksum": base_checksum})[:24]
    existing = session.exec(
        select(AutomationNotification).where(
            AutomationNotification.owner_user_id == effective_owner_user_id,
            AutomationNotification.notification_key == notification_key,
        )
    ).first()
    if existing is not None:
        return _notification_to_read(session, notification=existing), False

    render_context = {
        "notification_type": payload.notification_type,
        "source_event_type": payload.source_event_type,
        **{str(k): v for k, v in payload.notification_payload_json.items()},
    }
    subject, body, template = resolve_notification_template(session, notification_type=str(payload.notification_type), context=render_context)

    default_channels = ["IN_APP", "OPS_CONSOLE"]
    if str(payload.notification_type) in {"OPS_NOTIFICATION", "WORKFLOW_FAILURE", "DEAD_LETTER_ALERT"}:
        default_channels = ["IN_APP", "OPS_CONSOLE"]
    channels, suppressed_by_quiet = process_notification_preferences(
        session,
        owner_user_id=effective_owner_user_id,
        notification_type=str(payload.notification_type),
        channels=default_channels,
    )
    status = "SUPPRESSED" if suppressed_by_quiet or payload.metadata_json.get("force_suppress") else "QUEUED"
    row = AutomationNotification(
        owner_user_id=effective_owner_user_id,
        organization_id=None,
        notification_key=notification_key,
        notification_type=str(payload.notification_type),
        notification_status=status,
        source_event_type=payload.source_event_type,
        source_record_type=payload.source_record_type,
        source_record_id=payload.source_record_id,
        source_checksum=payload.source_checksum,
        notification_payload_json=_json_safe(payload.notification_payload_json),
        notification_checksum=base_checksum,
        replay_safe=payload.replay_safe,
        metadata_json=_json_safe({**payload.metadata_json, "rendered_subject": subject, "rendered_body": body}),
    )
    session.add(row)
    session.flush()

    if not channels and status != "SUPPRESSED":
        status = "SUPPRESSED"
        row.notification_status = "SUPPRESSED"
        _record_notification_issue(
            session,
            draft=_IssueDraft(
                notification_id=int(row.id),
                issue_type="SUPPRESSED_NOTIFICATION",
                severity="INFO",
                issue_message="All delivery channels disabled by preferences.",
                metadata_json={},
            ),
        )

    deliveries: list[AutomationNotificationDelivery] = []
    alerts: list[AutomationAlert] = []
    issues: list[AutomationNotificationIssue] = []
    if status == "QUEUED":
        deliveries = queue_notification_delivery(session, notification=row, channels=channels, owner_user_id=effective_owner_user_id)
        _execute_deliveries(session, notification=row, deliveries=deliveries)
        routing = _ROUTING_BY_NOTIFICATION_TYPE.get(str(payload.notification_type))
        if routing:
            alert_type, severity, escalation = routing
            if payload.metadata_json.get("escalation_level") in _ESCALATION_LEVELS:
                escalation = str(payload.metadata_json["escalation_level"])
            alerts.append(create_alert(session, notification=row, alert_type=alert_type, alert_severity=severity, escalation_level=escalation))
        delivered_count = sum(1 for delivery in deliveries if delivery.delivery_status == "DELIVERED")
        if delivered_count == len(deliveries) and deliveries:
            row.notification_status = "DELIVERED"
            row.delivered_at = utc_now()
        elif any(delivery.delivery_status == "FAILED" for delivery in deliveries):
            row.notification_status = "FAILED"

    issues = list(session.exec(select(AutomationNotificationIssue).where(AutomationNotificationIssue.notification_id == row.id)).all())
    artifact_refs: list[dict[str, Any]] = []
    manifest, manifest_checksum = build_notification_manifest(
        notification=row,
        template=template,
        rendered={"subject": subject, "body": body},
        deliveries=deliveries,
        alerts=alerts,
        issues=issues,
        artifacts=artifact_refs,
    )
    artifact_refs = _write_notification_artifacts(settings, notification=row, manifest=manifest, deliveries=deliveries, alerts=alerts)
    manifest, manifest_checksum = build_notification_manifest(
        notification=row,
        template=template,
        rendered={"subject": subject, "body": body},
        deliveries=deliveries,
        alerts=alerts,
        issues=issues,
        artifacts=artifact_refs,
    )
    row.notification_checksum = manifest_checksum
    row.metadata_json = _json_safe(
        {
            **row.metadata_json,
            "notification_manifest_json": manifest,
            "artifacts": artifact_refs,
        }
    )
    session.add(row)
    _record_notification_history(
        session,
        draft=_HistoryDraft(
            notification_id=int(row.id),
            event_type="NOTIFICATION_CREATED",
            event_message="Automation notification created.",
            metadata_json={"notification_checksum": manifest_checksum},
            to_status=row.notification_status,
        ),
    )
    session.commit()
    return _notification_to_read(session, notification=row), True


def _notification_to_read(session: Session, *, notification: AutomationNotification) -> AutomationNotificationRead:
    deliveries = list(
        session.exec(
            select(AutomationNotificationDelivery)
            .where(AutomationNotificationDelivery.notification_id == notification.id)
            .order_by(col(AutomationNotificationDelivery.delivery_rank), col(AutomationNotificationDelivery.id))
        ).all()
    )
    alerts = list(
        session.exec(select(AutomationAlert).where(AutomationAlert.source_notification_id == notification.id).order_by(col(AutomationAlert.created_at), col(AutomationAlert.id))).all()
    )
    issues = list(
        session.exec(select(AutomationNotificationIssue).where(AutomationNotificationIssue.notification_id == notification.id).order_by(col(AutomationNotificationIssue.created_at), col(AutomationNotificationIssue.id))).all()
    )
    history = list(
        session.exec(select(AutomationNotificationHistory).where(AutomationNotificationHistory.notification_id == notification.id).order_by(col(AutomationNotificationHistory.created_at), col(AutomationNotificationHistory.id))).all()
    )
    meta = notification.metadata_json or {}
    artifacts_raw = meta.get("artifacts", [])
    artifacts = [artifact for artifact in artifacts_raw if isinstance(artifact, dict)] if isinstance(artifacts_raw, list) else []
    base = AutomationNotificationRead.model_validate(notification)
    return base.model_copy(
        update={
            "rendered_subject": str(meta.get("rendered_subject") or ""),
            "rendered_body": str(meta.get("rendered_body") or ""),
            "notification_manifest_json": meta.get("notification_manifest_json") if isinstance(meta.get("notification_manifest_json"), dict) else {},
            "deliveries": [AutomationNotificationDeliveryRead.model_validate(row) for row in deliveries],
            "alerts": [AutomationAlertRead.model_validate(row) for row in alerts],
            "issues": [AutomationNotificationIssueRead.model_validate(row) for row in issues],
            "history": [AutomationNotificationHistoryRead.model_validate(entry) for entry in history],
            "artifacts": [AutomationNotificationArtifactRead.model_validate(artifact) for artifact in artifacts],
        }
    )


def get_automation_notification_owner(session: Session, *, owner_user_id: int, notification_id: int) -> AutomationNotificationRead:
    row = session.get(AutomationNotification, notification_id)
    if row is None or int(row.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation notification not found.")
    read = _notification_to_read(session, notification=row)
    return read


def list_automation_notifications_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationNotificationListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = [row for row in session.exec(select(AutomationNotification).order_by(col(AutomationNotification.created_at).desc(), col(AutomationNotification.id).desc())).all() if int(row.owner_user_id or 0) == owner_user_id]
    return _list_response(session, rows=rows, limit=limit, offset=offset)


def list_automation_notifications_ops(session: Session, *, limit: int, offset: int) -> AutomationNotificationListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationNotification).order_by(col(AutomationNotification.created_at).desc(), col(AutomationNotification.id).desc())).all())
    return _list_response(session, rows=rows, limit=limit, offset=offset)


def _list_response(session: Session, *, rows: list[AutomationNotification], limit: int, offset: int) -> AutomationNotificationListResponse:
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.notification_status] = status_counts.get(row.notification_status, 0) + 1
        type_counts[row.notification_type] = type_counts.get(row.notification_type, 0) + 1
    alerts = list(session.exec(select(AutomationAlert)).all())
    deliveries = list(session.exec(select(AutomationNotificationDelivery)).all())
    items = [_notification_to_read(session, notification=row) for row in rows[offset : offset + limit]]
    return AutomationNotificationListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        type_counts=type_counts,
        queued_count=status_counts.get("QUEUED", 0),
        failed_delivery_count=len([row for row in deliveries if row.delivery_status == "FAILED"]),
        active_alert_count=len([row for row in alerts if row.alert_status == "ACTIVE"]),
        critical_alert_count=len([row for row in alerts if row.alert_severity == "CRITICAL" and row.alert_status == "ACTIVE"]),
    )


def list_automation_alerts_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationAlertListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    notification_ids = [row.id for row in session.exec(select(AutomationNotification).where(AutomationNotification.owner_user_id == owner_user_id)).all()]
    rows = list(
        session.exec(
            select(AutomationAlert)
            .where(col(AutomationAlert.source_notification_id).in_(notification_ids or [-1]))
            .order_by(col(AutomationAlert.created_at).desc(), col(AutomationAlert.id).desc())
        ).all()
    )
    return _alert_list(rows, limit=limit, offset=offset)


def list_automation_alerts_ops(session: Session, *, limit: int, offset: int, critical_only: bool = False) -> AutomationAlertListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationAlert).order_by(col(AutomationAlert.created_at).desc(), col(AutomationAlert.id).desc())).all())
    if critical_only:
        rows = [row for row in rows if row.alert_severity == "CRITICAL"]
    return _alert_list(rows, limit=limit, offset=offset)


def _alert_list(rows: list[AutomationAlert], *, limit: int, offset: int) -> AutomationAlertListResponse:
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.alert_status] = status_counts.get(row.alert_status, 0) + 1
        severity_counts[row.alert_severity] = severity_counts.get(row.alert_severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationAlertListResponse(
        items=[AutomationAlertRead.model_validate(row) for row in paged],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        severity_counts=severity_counts,
    )


def list_automation_notification_preferences_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationNotificationPreferenceListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationNotificationPreference)
            .where(AutomationNotificationPreference.owner_user_id == owner_user_id)
            .order_by(col(AutomationNotificationPreference.created_at).desc(), col(AutomationNotificationPreference.id).desc())
        ).all()
    )
    return AutomationNotificationPreferenceListResponse(
        items=[AutomationNotificationPreferenceRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def list_automation_notification_issues_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationNotificationIssueListResponse:
    notification_ids = [row.id for row in session.exec(select(AutomationNotification).where(AutomationNotification.owner_user_id == owner_user_id)).all()]
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationNotificationIssue)
            .where(col(AutomationNotificationIssue.notification_id).in_(notification_ids or [-1]))
            .order_by(col(AutomationNotificationIssue.created_at).desc(), col(AutomationNotificationIssue.id).desc())
        ).all()
    )
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    return AutomationNotificationIssueListResponse(
        items=[AutomationNotificationIssueRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
    )


def list_automation_notification_issues_ops(session: Session, *, limit: int, offset: int) -> AutomationNotificationIssueListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationNotificationIssue).order_by(col(AutomationNotificationIssue.created_at).desc(), col(AutomationNotificationIssue.id).desc())).all())
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    return AutomationNotificationIssueListResponse(
        items=[AutomationNotificationIssueRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
    )


def list_automation_delivery_failures_ops(session: Session, *, limit: int, offset: int) -> AutomationNotificationDeliveryListResponse:
    limit, offset = clamp_automation_notification_pagination(limit=limit, offset=offset)
    rows = list(
        session.exec(
            select(AutomationNotificationDelivery)
            .where(AutomationNotificationDelivery.delivery_status == "FAILED")
            .order_by(col(AutomationNotificationDelivery.created_at).desc(), col(AutomationNotificationDelivery.id).desc())
        ).all()
    )
    status_counts = {"FAILED": len(rows)}
    return AutomationNotificationDeliveryListResponse(
        items=[AutomationNotificationDeliveryRead.model_validate(row) for row in rows[offset : offset + limit]],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
    )
