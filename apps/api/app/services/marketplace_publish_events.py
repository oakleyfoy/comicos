from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.models.marketplace_publish import MarketplacePublishEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _log(session: Session, *, publish_job_id: int, event_type: str, event_payload_json: dict[str, Any]) -> MarketplacePublishEvent:
    row = MarketplacePublishEvent(
        publish_job_id=publish_job_id,
        event_type=event_type,
        event_payload_json=event_payload_json,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def log_job_created(session: Session, *, publish_job_id: int, listing_id: int, requested_by: int) -> MarketplacePublishEvent:
    return _log(
        session,
        publish_job_id=publish_job_id,
        event_type="publish_job_created",
        event_payload_json={"listing_id": listing_id, "requested_by": requested_by},
    )


def log_validation_failed(session: Session, *, publish_job_id: int, issue_count: int) -> MarketplacePublishEvent:
    return _log(
        session,
        publish_job_id=publish_job_id,
        event_type="publish_validation_failed",
        event_payload_json={"issue_count": issue_count},
    )


def log_plan_created(session: Session, *, publish_job_id: int, target_count: int) -> MarketplacePublishEvent:
    return _log(
        session,
        publish_job_id=publish_job_id,
        event_type="publish_plan_created",
        event_payload_json={"target_count": target_count},
    )


def log_job_ready(session: Session, *, publish_job_id: int) -> MarketplacePublishEvent:
    return _log(session, publish_job_id=publish_job_id, event_type="publish_job_ready", event_payload_json={})


def log_job_completed(session: Session, *, publish_job_id: int) -> MarketplacePublishEvent:
    return _log(session, publish_job_id=publish_job_id, event_type="publish_job_completed", event_payload_json={})


def log_job_failed(session: Session, *, publish_job_id: int, reason: str | None = None) -> MarketplacePublishEvent:
    return _log(
        session,
        publish_job_id=publish_job_id,
        event_type="publish_job_failed",
        event_payload_json={"reason": reason or ""},
    )
