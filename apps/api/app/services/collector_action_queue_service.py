"""P90 daily action queue from stored collector alerts."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.p90_collector_alert import P90CollectorAlert
from app.schemas.p90_automation import P90ActionQueueItemRead

DEFAULT_QUEUE_LIMIT = 10
_ACTIVE_STATUSES = ("NEW", "ACKNOWLEDGED")


def _action_type(alert_type: str) -> str:
    mapping = {
        "BUY_OPPORTUNITY": "BUY",
        "SELL_OPPORTUNITY": "SELL",
        "GRADE_OPPORTUNITY": "GRADE",
        "COLLECTION_GAP": "COLLECTION",
        "PRICE_DROP": "BUY",
        "RELEASE_ALERT": "RELEASE",
        "WATCHLIST_MATCH": "BUY",
        "PORTFOLIO_ACTION": "PORTFOLIO",
    }
    return mapping.get(alert_type, "ALERT")


def build_action_queue(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = DEFAULT_QUEUE_LIMIT,
) -> list[P90ActionQueueItemRead]:
    rows = list(
        session.exec(
            select(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == owner_user_id)
            .where(P90CollectorAlert.status.in_(_ACTIVE_STATUSES))  # type: ignore[attr-defined]
            .order_by(P90CollectorAlert.priority_score.desc(), P90CollectorAlert.updated_at.desc())
            .limit(limit)
        ).all()
    )
    items: list[P90ActionQueueItemRead] = []
    for idx, row in enumerate(rows, start=1):
        items.append(
            P90ActionQueueItemRead(
                rank=idx,
                title=row.title,
                detail=row.summary or row.reason,
                action_type=_action_type(row.alert_type),
                priority_score=float(row.priority_score),
                confidence=row.confidence,
                action_route=row.action_route or "/automation-center",
                alert_id=int(row.id or 0),
            )
        )
    return items


def count_actions_generated(session: Session, *, owner_user_id: int) -> int:
    return len(build_action_queue(session, owner_user_id=owner_user_id, limit=DEFAULT_QUEUE_LIMIT))
