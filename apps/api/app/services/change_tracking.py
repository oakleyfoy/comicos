from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.schemas.data_integrity import AuditEventDetail
from app.services.audit_trail import get_audit_event, log_audit_event, log_change_record


def _normalized_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return {str(key): payload[key] for key in sorted(payload)}


def diff_payloads(before_payload: dict[str, Any] | None, after_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    before_normalized = _normalized_payload(before_payload)
    after_normalized = _normalized_payload(after_payload)
    fields = sorted(set(before_normalized) | set(after_normalized))
    changes: list[dict[str, Any]] = []
    for field_name in fields:
        before_value = before_normalized.get(field_name)
        after_value = after_normalized.get(field_name)
        if before_value == after_value:
            continue
        changes.append(
            {
                "field_name": field_name,
                "before_value_json": before_value,
                "after_value_json": after_value,
            }
        )
    return changes


def track_entity_change(
    session: Session,
    *,
    owner_user_id: int,
    actor_id: int | None,
    actor_type: str,
    action_type: str,
    entity_type: str,
    entity_id: int | None,
    source: str,
    before_payload: dict[str, Any] | None,
    after_payload: dict[str, Any] | None,
    event_payload_json: dict[str, Any] | None = None,
) -> AuditEventDetail:
    event = log_audit_event(
        session,
        owner_user_id=owner_user_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        event_payload_json=event_payload_json or {},
    )
    changes = diff_payloads(before_payload, after_payload)
    for change in changes:
        log_change_record(
            session,
            audit_event_id=event.id,
            field_name=change["field_name"],
            before_value_json=change["before_value_json"],
            after_value_json=change["after_value_json"],
        )
    return get_audit_event(session, owner_user_id=owner_user_id, audit_event_id=event.id)


def track_bulk_change(
    session: Session,
    *,
    owner_user_id: int,
    actor_id: int | None,
    actor_type: str,
    action_type: str,
    entity_type: str,
    source: str,
    changes: list[dict[str, Any]],
) -> list[AuditEventDetail]:
    results: list[AuditEventDetail] = []
    for change in changes:
        results.append(
            track_entity_change(
                session,
                owner_user_id=owner_user_id,
                actor_id=actor_id,
                actor_type=actor_type,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=change.get("entity_id"),
                source=source,
                before_payload=change.get("before_payload"),
                after_payload=change.get("after_payload"),
                event_payload_json=change.get("event_payload_json") or {},
            )
        )
    return results
