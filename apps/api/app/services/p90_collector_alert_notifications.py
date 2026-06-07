"""P90 best-effort COLLECTOR_ALERT notifications."""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.models.p90_collector_alert import P90CollectorAlert

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "COLLECTOR_ALERT"


def notify_collector_alert_created(session: Session, *, row: P90CollectorAlert) -> None:
    try:
        from app.models.p82_p84_collector_expansion import CollectorNotification, utc_now
        from sqlmodel import select

        existing = session.exec(
            select(CollectorNotification).where(
                CollectorNotification.owner_user_id == row.owner_user_id,
                CollectorNotification.notification_type == NOTIFICATION_TYPE,
                CollectorNotification.related_entity_type == "p90_collector_alert",
                CollectorNotification.related_entity_id == int(row.id or 0),
            )
        ).first()
        if existing:
            return
        priority = "HIGH" if row.severity in {"HIGH", "CRITICAL"} else "NORMAL"
        session.add(
            CollectorNotification(
                owner_user_id=row.owner_user_id,
                notification_type=NOTIFICATION_TYPE,
                priority=priority,
                title=row.title,
                message=row.summary or row.reason,
                related_entity_type="p90_collector_alert",
                related_entity_id=int(row.id or 0),
                action_url=row.action_route or "/automation-center",
                status="UNREAD",
                reasons_json=[row.alert_type, row.source_system],
                created_at=utc_now(),
            )
        )
    except Exception as exc:  # noqa: BLE001 — best effort
        logger.debug("collector alert notification skipped: %s", exc)
