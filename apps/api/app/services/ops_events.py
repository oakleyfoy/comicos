import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import Session

from app.db.session import get_engine
from app.models import OpsEvent

LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def classify_failure_message(message: str, *, default_type: str = "parser_failure") -> str:
    normalized = " ".join(message.split()).lower()
    if "insufficient_quota" in normalized or "quota" in normalized:
        return "openai_quota_failure"
    if "unsupported provider" in normalized:
        return "unsupported_provider_skip"
    if "incomplete" in normalized or "invalid" in normalized or "validation" in normalized:
        return "parser_validation_failure"
    if "malformed" in normalized or "unable to parse" in normalized:
        return "malformed_receipt_failure"
    return default_type


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    return value


def record_ops_event(
    *,
    event_type: str,
    status: str,
    user_id: int | None = None,
    job_id: str | None = None,
    queue_name: str | None = None,
    gmail_account_id: int | None = None,
    draft_import_id: int | None = None,
    order_id: int | None = None,
    external_message_id: str | None = None,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        with Session(get_engine()) as session:
            session.add(
                OpsEvent(
                    event_type=event_type,
                    status=status,
                    user_id=user_id,
                    job_id=job_id,
                    queue_name=queue_name,
                    gmail_account_id=gmail_account_id,
                    draft_import_id=draft_import_id,
                    order_id=order_id,
                    external_message_id=external_message_id,
                    message=message,
                    details_json=_normalize_json_value(details or {}),
                    created_at=utc_now(),
                )
            )
            session.commit()
    except Exception:
        LOGGER.exception(
            "Failed to record ops event event_type=%s status=%s job_id=%s",
            event_type,
            status,
            job_id,
        )
