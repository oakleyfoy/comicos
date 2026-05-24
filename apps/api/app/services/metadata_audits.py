from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models import MetadataAudit, User
from app.schemas.ops import OpsMetadataAuditRow

SECRET_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "refresh",
)


def _looks_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS)


def _normalize_json_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return _normalize_json_value(value.model_dump(mode="json"))
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if _looks_secret_key(str(key)):
                continue
            compact = _normalize_json_value(item)
            if compact is None:
                continue
            if compact == {} or compact == []:
                continue
            normalized[str(key)] = compact
        return normalized
    if isinstance(value, (list, tuple, set)):
        normalized_items = [_normalize_json_value(item) for item in value]
        return [item for item in normalized_items if item is not None and item != {} and item != []]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def safe_json_snapshot(value: Any) -> dict[str, Any] | None:
    normalized = _normalize_json_value(value)
    if normalized in (None, {}, []):
        return None
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


def record_metadata_audit(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    before_snapshot: Any = None,
    after_snapshot: Any = None,
    reason: str | None = None,
    actor_user_id: int | None = None,
) -> MetadataAudit:
    audit = MetadataAudit(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_snapshot=safe_json_snapshot(before_snapshot),
        after_snapshot=safe_json_snapshot(after_snapshot),
        reason=reason,
        actor_user_id=actor_user_id,
    )
    session.add(audit)
    session.flush()
    return audit


def _user_email_map(session: Session, user_ids: Iterable[int | None]) -> dict[int, str]:
    normalized_ids = sorted({user_id for user_id in user_ids if user_id is not None})
    if not normalized_ids:
        return {}
    rows = session.exec(select(User).where(User.id.in_(normalized_ids))).all()
    return {row.id: row.email for row in rows if row.id is not None}


def list_recent_metadata_audits(
    session: Session,
    *,
    limit: int = 25,
    entity_type: str | None = None,
    action: str | None = None,
) -> list[OpsMetadataAuditRow]:
    stmt = select(MetadataAudit).order_by(MetadataAudit.created_at.desc(), MetadataAudit.id.desc())
    if entity_type:
        stmt = stmt.where(MetadataAudit.entity_type == entity_type)
    if action:
        stmt = stmt.where(MetadataAudit.action == action)
    audits = session.exec(stmt.limit(limit)).all()
    emails = _user_email_map(session, (audit.actor_user_id for audit in audits))
    return [
        OpsMetadataAuditRow(
            id=audit.id,
            entity_type=audit.entity_type,
            entity_id=audit.entity_id,
            action=audit.action,
            before_snapshot=audit.before_snapshot,
            after_snapshot=audit.after_snapshot,
            reason=audit.reason,
            actor_user_id=audit.actor_user_id,
            actor_email=(
                emails.get(audit.actor_user_id)
                if audit.actor_user_id is not None
                else None
            ),
            created_at=audit.created_at,
        )
        for audit in audits
        if audit.id is not None
    ]
