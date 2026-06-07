"""P90-03 Collector Advisor notifications (best effort)."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "COLLECTOR_ADVISOR"


def notify_collector_advisor_ready(session: Session, *, owner_user_id: int, snapshot_id: int) -> None:
    try:
        from app.models.p82_p84_collector_expansion import CollectorNotification, utc_now

        day_key = utc_now().date().isoformat()
        existing = session.exec(
            select(CollectorNotification).where(
                CollectorNotification.owner_user_id == owner_user_id,
                CollectorNotification.notification_type == NOTIFICATION_TYPE,
                CollectorNotification.related_entity_type == "p90_collector_advisor_snapshot",
                CollectorNotification.related_entity_id == snapshot_id,
            )
        ).first()
        if existing:
            return
        session.add(
            CollectorNotification(
                owner_user_id=owner_user_id,
                notification_type=NOTIFICATION_TYPE,
                priority="NORMAL",
                title="Today's Collector Advisor plan is ready.",
                message=f"Your daily action plan for {day_key} is available in the Automation Center.",
                related_entity_type="p90_collector_advisor_snapshot",
                related_entity_id=snapshot_id,
                action_url="/automation-center",
                status="UNREAD",
                reasons_json=["COLLECTOR_ADVISOR"],
                created_at=utc_now(),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("collector advisor notification skipped: %s", exc)
