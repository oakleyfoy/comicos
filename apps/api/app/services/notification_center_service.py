"""P65-04 Notification center — inbox from intelligence outputs."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.collector_experience import (
    NOTIF_STATUS_ARCHIVED,
    NOTIF_STATUS_READ,
    NOTIF_STATUS_UNREAD,
    NotificationItem,
    NotificationSnapshot,
    utc_now,
)
from app.services.collector_assistant_context_service import load_collector_assistant_context
from app.services.collector_assistant_orchestrator import get_latest_alert_snapshot, list_alerts_for_snapshot

TYPE_BUY = "BUY_ALERT"
TYPE_SELL = "SELL_ALERT"
TYPE_GRADE = "GRADE_ALERT"
TYPE_ACQUISITION = "ACQUISITION_ALERT"
TYPE_FOC = "FOC_ALERT"
TYPE_WATCH = "WATCH_ALERT"

READINESS_SUCCESS = "SUCCESS"
READINESS_NOT_READY = "NOT_READY"

_ALERT_TYPE_MAP = {
    "BUY": TYPE_BUY,
    "SELL": TYPE_SELL,
    "GRADE": TYPE_GRADE,
    "ACQUIRE": TYPE_ACQUISITION,
    "FOC": TYPE_FOC,
    "WATCH": TYPE_WATCH,
}


def get_latest_notification_snapshot(session: Session, *, owner_user_id: int) -> NotificationSnapshot | None:
    return session.exec(
        select(NotificationSnapshot)
        .where(NotificationSnapshot.owner_user_id == owner_user_id)
        .order_by(NotificationSnapshot.generated_at.desc(), NotificationSnapshot.id.desc())
    ).first()


def list_notification_items(session: Session, *, snapshot_id: int, limit: int = 100) -> list[NotificationItem]:
    return list(
        session.exec(
            select(NotificationItem)
            .where(NotificationItem.snapshot_id == snapshot_id)
            .order_by(NotificationItem.created_at.desc(), NotificationItem.id.desc())
            .limit(limit)
        ).all()
    )


def _prior_status_by_provenance(session: Session, *, owner_user_id: int) -> dict[str, str]:
    prev = get_latest_notification_snapshot(session, owner_user_id=owner_user_id)
    if not prev:
        return {}
    out: dict[str, str] = {}
    for item in list_notification_items(session, snapshot_id=int(prev.id or 0), limit=300):
        key = str(item.provenance_json or {})
        out[key] = item.status
    return out


def build_notifications(session: Session, *, owner_user_id: int) -> NotificationSnapshot:
    ctx = load_collector_assistant_context(session, owner_user_id=owner_user_id)
    prior = _prior_status_by_provenance(session, owner_user_id=owner_user_id)
    drafts: list[dict] = []

    alert_snap = get_latest_alert_snapshot(session, owner_user_id=owner_user_id)
    if alert_snap:
        for alert in list_alerts_for_snapshot(session, alert_snapshot_id=int(alert_snap.id or 0)):
            ntype = _ALERT_TYPE_MAP.get(str(alert.alert_type or "").upper(), TYPE_BUY)
            drafts.append(
                {
                    "notification_type": ntype,
                    "title": alert.title,
                    "message": alert.message,
                    "deep_link": alert.action_deep_link or "/collector-workspace",
                    "provenance_json": alert.provenance_json or {"alert_id": int(alert.id or 0)},
                }
            )

    for row in ctx.foc_items[:15]:
        drafts.append(
            {
                "notification_type": TYPE_FOC,
                "title": str(getattr(row, "title", "") or "FOC reminder"),
                "message": str(getattr(row, "message", "") or "FOC deadline approaching."),
                "deep_link": "/foc-dashboard",
                "provenance_json": {"foc_item_id": int(getattr(row, "id", 0) or 0)},
            }
        )

    for row in ctx.sell_items[:10]:
        drafts.append(
            {
                "notification_type": TYPE_SELL,
                "title": str(getattr(row, "title", "") or "Sell signal"),
                "message": str(getattr(row, "reason", "") or "Review sell candidate."),
                "deep_link": "/sell-candidates",
                "provenance_json": {"sell_signal_item_id": int(getattr(row, "id", 0) or 0)},
            }
        )

    for row in ctx.acquisition_items[:10]:
        drafts.append(
            {
                "notification_type": TYPE_ACQUISITION,
                "title": str(getattr(row, "title", "") or "Acquisition"),
                "message": str(getattr(row, "reason", "") or "Acquisition opportunity."),
                "deep_link": "/acquisition-opportunities",
                "provenance_json": {"acquisition_item_id": int(getattr(row, "id", 0) or 0)},
            }
        )

    for row in ctx.buy_queue_items[:8]:
        drafts.append(
            {
                "notification_type": TYPE_BUY,
                "title": str(getattr(row, "title", "") or "Buy alert"),
                "message": str(getattr(row, "explanation", "") or "Buy queue item."),
                "deep_link": "/collector-workspace",
                "provenance_json": {"buy_queue_item_id": int(getattr(row, "id", 0) or 0)},
            }
        )

    snap = NotificationSnapshot(
        owner_user_id=owner_user_id,
        total_items=len(drafts),
        unread_count=0,
        metadata_json={"fingerprint": ctx.fingerprint},
    )
    session.add(snap)
    session.flush()

    unread = 0
    for d in drafts:
        prov_key = str(d["provenance_json"])
        status = prior.get(prov_key, NOTIF_STATUS_UNREAD)
        if status == NOTIF_STATUS_ARCHIVED:
            continue
        if status == NOTIF_STATUS_UNREAD:
            unread += 1
        session.add(
            NotificationItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                notification_type=d["notification_type"],
                status=status,
                title=d["title"],
                message=d["message"],
                deep_link=d["deep_link"],
                provenance_json=d["provenance_json"],
            )
        )
    snap.unread_count = unread
    snap.total_items = len(drafts)
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def get_notification_item(session: Session, *, owner_user_id: int, item_id: int) -> NotificationItem | None:
    row = session.get(NotificationItem, item_id)
    if row is None or row.owner_user_id != owner_user_id:
        return None
    return row


def update_notification_status(
    session: Session,
    *,
    owner_user_id: int,
    item_id: int,
    status: str,
) -> NotificationItem | None:
    row = get_notification_item(session, owner_user_id=owner_user_id, item_id=item_id)
    if row is None:
        return None
    row.status = status
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
