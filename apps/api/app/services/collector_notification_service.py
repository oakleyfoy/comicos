"""P84 collector notifications."""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import CollectorNotification, utc_now
from app.schemas.p82_p84_collector_expansion import (
    CollectorNotificationDashboardRead,
    CollectorNotificationListResponse,
    CollectorNotificationRead,
    CollectorNotificationUpdate,
)
from app.services.collection_valuation_service import build_collection_risk
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p77_personalization_engine import load_personalization_context


def _to_read(row: CollectorNotification) -> CollectorNotificationRead:
    return CollectorNotificationRead(
        id=int(row.id or 0),
        notification_type=row.notification_type,
        priority=row.priority,  # type: ignore[arg-type]
        title=row.title,
        message=row.message,
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
        action_url=row.action_url,
        status=row.status,
        reasons=list(row.reasons_json or []),
        created_at=row.created_at,
        read_at=row.read_at,
        dismissed_at=row.dismissed_at,
    )


def _upsert_notification(
    session: Session,
    *,
    owner_user_id: int,
    notification_type: str,
    priority: str,
    title: str,
    message: str,
    action_url: str = "",
    related_entity_type: str = "",
    related_entity_id: int | None = None,
    reasons: list[str] | None = None,
) -> None:
    existing = session.exec(
        select(CollectorNotification).where(
            CollectorNotification.owner_user_id == owner_user_id,
            CollectorNotification.notification_type == notification_type,
            CollectorNotification.title == title,
            CollectorNotification.status != "DISMISSED",
        )
    ).first()
    if existing:
        return
    session.add(
        CollectorNotification(
            owner_user_id=owner_user_id,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            action_url=action_url,
            status="UNREAD",
            reasons_json=reasons or [],
            created_at=utc_now(),
        )
    )


def refresh_collector_notifications(session: Session, *, owner_user_id: int) -> int:
    created_before = len(
        list(session.exec(select(CollectorNotification).where(CollectorNotification.owner_user_id == owner_user_id)).all())
    )
    deals = list_acquisition_opportunities(session, owner_user_id=owner_user_id, recommendation="STRONG_BUY", limit=5, offset=0, refresh=True)
    for item in deals.items:
        _upsert_notification(
            session,
            owner_user_id=owner_user_id,
            notification_type="MARKETPLACE_DEAL",
            priority="HIGH",
            title=f"Marketplace deal: {item.title}",
            message=f"Score {item.opportunity_score:.0f} · {item.discount_to_fmv:.0f}% below FMV",
            action_url=f"/marketplace-opportunity/{item.id}",
            related_entity_type="marketplace_acquisition",
            related_entity_id=item.id,
            reasons=item.reasons[:3],
        )
    risk = build_collection_risk(session, owner_user_id=owner_user_id, persist=False)
    if risk.risk_category == "HIGH_RISK":
        _upsert_notification(
            session,
            owner_user_id=owner_user_id,
            notification_type="PORTFOLIO_RISK_ALERT",
            priority="CRITICAL",
            title="Portfolio risk elevated",
            message=f"Risk score {risk.risk_score:.0f} ({risk.risk_category})",
            action_url="/collection-risk",
            reasons=["Review concentration and liquidity"],
        )
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    if ctx.budget_state in {"RED", "YELLOW"}:
        _upsert_notification(
            session,
            owner_user_id=owner_user_id,
            notification_type="BUDGET_ALERT",
            priority="HIGH" if ctx.budget_state == "RED" else "NORMAL",
            title=f"Budget status: {ctx.budget_state}",
            message="Review spend before new acquisitions.",
            action_url="/collector-budget",
        )
    session.flush()
    created_after = len(
        list(session.exec(select(CollectorNotification).where(CollectorNotification.owner_user_id == owner_user_id)).all())
    )
    return max(0, created_after - created_before)


def list_collector_notifications(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
) -> CollectorNotificationListResponse:
    if refresh:
        refresh_collector_notifications(session, owner_user_id=owner_user_id)
    stmt = select(CollectorNotification).where(CollectorNotification.owner_user_id == owner_user_id)
    if status:
        stmt = stmt.where(CollectorNotification.status == status.strip().upper())
    rows = list(session.exec(stmt.order_by(CollectorNotification.created_at.desc())).all())
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    unread = sum(1 for r in rows if r.status == "UNREAD")
    page = [_to_read(r) for r in rows[off : off + lim]]
    return CollectorNotificationListResponse(items=page, total_items=len(rows), limit=lim, offset=off, unread_count=unread)


def update_collector_notification(
    session: Session,
    *,
    owner_user_id: int,
    notification_id: int,
    payload: CollectorNotificationUpdate,
) -> CollectorNotificationRead:
    row = session.get(CollectorNotification, notification_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Notification not found.")
    now = utc_now()
    if payload.status:
        row.status = payload.status
        if payload.status == "READ" and row.read_at is None:
            row.read_at = now
        if payload.status == "DISMISSED":
            row.dismissed_at = now
    session.add(row)
    session.flush()
    return _to_read(row)


def build_notification_dashboard(session: Session, *, owner_user_id: int, refresh: bool = True) -> CollectorNotificationDashboardRead:
    body = list_collector_notifications(session, owner_user_id=owner_user_id, limit=100, offset=0, refresh=refresh)
    items = body.items
    return CollectorNotificationDashboardRead(
        unread=[i for i in items if i.status == "UNREAD"][:20],
        critical=[i for i in items if i.priority == "CRITICAL"][:15],
        recent=items[:25],
    )
