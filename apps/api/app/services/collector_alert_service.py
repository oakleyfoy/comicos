"""P90 collector alert read/update and dashboard aggregation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.p90_collector_alert import P90CollectorAlert, utc_now
from app.schemas.p90_automation import (
    P90AutomationDashboardRead,
    P90AutomationSummaryRead,
    P90CollectorAlertListResponse,
    P90CollectorAlertRead,
    P90CollectorAlertUpdate,
)
from app.services.collector_action_queue_service import build_action_queue
from app.services.p90_safe_reads import p90_safe_call


def _empty_automation_dashboard() -> P90AutomationDashboardRead:
    now = datetime.now(timezone.utc)
    return P90AutomationDashboardRead(
        status="EMPTY",
        todays_actions=[],
        buy_alerts=[],
        sell_alerts=[],
        grade_alerts=[],
        collection_gaps=[],
        release_alerts=[],
        generated_at=now,
    )

def _to_read(row: P90CollectorAlert) -> P90CollectorAlertRead:
    return P90CollectorAlertRead(
        id=int(row.id or 0),
        alert_type=row.alert_type,
        severity=row.severity,
        priority_score=float(row.priority_score),
        title=row.title,
        summary=row.summary,
        source_system=row.source_system,
        entity_type=row.entity_type,
        entity_id=int(row.entity_id),
        status=row.status,
        confidence=row.confidence,
        reason=row.reason,
        action_route=row.action_route,
        created_at=row.created_at,
        updated_at=row.updated_at,
        acknowledged_at=row.acknowledged_at,
        dismissed_at=row.dismissed_at,
    )


def list_collector_alerts(
    session: Session,
    *,
    owner_user_id: int,
    alert_type: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> P90CollectorAlertListResponse:
    base = select(P90CollectorAlert).where(P90CollectorAlert.owner_user_id == owner_user_id)
    count_q = select(func.count()).select_from(P90CollectorAlert).where(P90CollectorAlert.owner_user_id == owner_user_id)
    if alert_type:
        base = base.where(P90CollectorAlert.alert_type == alert_type)
        count_q = count_q.where(P90CollectorAlert.alert_type == alert_type)
    if status:
        base = base.where(P90CollectorAlert.status == status)
        count_q = count_q.where(P90CollectorAlert.status == status)
    if severity:
        base = base.where(P90CollectorAlert.severity == severity)
        count_q = count_q.where(P90CollectorAlert.severity == severity)
    total = int(session.exec(count_q).one() or 0)
    rows = list(
        session.exec(
            base.order_by(P90CollectorAlert.priority_score.desc(), P90CollectorAlert.id.desc()).offset(offset).limit(limit)
        ).all()
    )
    return P90CollectorAlertListResponse(items=[_to_read(r) for r in rows], total=total)


def update_collector_alert(
    session: Session,
    *,
    owner_user_id: int,
    alert_id: int,
    payload: P90CollectorAlertUpdate,
) -> P90CollectorAlertRead:
    row = session.get(P90CollectorAlert, alert_id)
    if row is None or row.owner_user_id != owner_user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Alert not found")
    status = payload.status.upper()
    if status not in {"ACKNOWLEDGED", "DISMISSED", "COMPLETED", "NEW"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid alert status")
    now = utc_now()
    row.status = status
    row.updated_at = now
    if status == "ACKNOWLEDGED":
        row.acknowledged_at = now
    elif status in {"DISMISSED", "COMPLETED"}:
        row.dismissed_at = now
    session.add(row)
    session.flush()
    return _to_read(row)


def _count_type(session: Session, *, owner_user_id: int, alert_type: str, status: str = "NEW") -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == owner_user_id)
            .where(P90CollectorAlert.alert_type == alert_type)
            .where(P90CollectorAlert.status == status)
        ).one()
        or 0
    )


def build_automation_briefing_summary(session: Session, *, owner_user_id: int) -> dict:
    def _top(alert_type: str) -> str | None:
        row = session.exec(
            select(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == owner_user_id)
            .where(P90CollectorAlert.alert_type == alert_type)
            .where(P90CollectorAlert.status.in_(("NEW", "ACKNOWLEDGED")))  # type: ignore[attr-defined]
            .order_by(P90CollectorAlert.priority_score.desc())
            .limit(1)
        ).first()
        return row.title if row else None

    return {
        "top_buy_alert": _top("BUY_OPPORTUNITY") or _top("PRICE_DROP") or _top("WATCHLIST_MATCH"),
        "top_sell_alert": _top("SELL_OPPORTUNITY"),
        "top_grade_alert": _top("GRADE_OPPORTUNITY"),
        "top_collection_gap": _top("COLLECTION_GAP"),
        "new_alerts": int(
            session.exec(
                select(func.count())
                .select_from(P90CollectorAlert)
                .where(P90CollectorAlert.owner_user_id == owner_user_id)
                .where(P90CollectorAlert.status == "NEW")
            ).one()
            or 0
        ),
    }


def build_automation_summary(session: Session, *, owner_user_id: int) -> P90AutomationSummaryRead:
    now = datetime.now(timezone.utc)
    actions = build_action_queue(session, owner_user_id=owner_user_id)
    return P90AutomationSummaryRead(
        buy_alerts_count=_count_type(session, owner_user_id=owner_user_id, alert_type="BUY_OPPORTUNITY")
        + _count_type(session, owner_user_id=owner_user_id, alert_type="PRICE_DROP")
        + _count_type(session, owner_user_id=owner_user_id, alert_type="WATCHLIST_MATCH"),
        sell_alerts_count=_count_type(session, owner_user_id=owner_user_id, alert_type="SELL_OPPORTUNITY"),
        grade_alerts_count=_count_type(session, owner_user_id=owner_user_id, alert_type="GRADE_OPPORTUNITY"),
        collection_gap_count=_count_type(session, owner_user_id=owner_user_id, alert_type="COLLECTION_GAP"),
        release_alerts_count=_count_type(session, owner_user_id=owner_user_id, alert_type="RELEASE_ALERT"),
        new_alerts_count=int(
            session.exec(
                select(func.count())
                .select_from(P90CollectorAlert)
                .where(P90CollectorAlert.owner_user_id == owner_user_id)
                .where(P90CollectorAlert.status == "NEW")
            ).one()
            or 0
        ),
        todays_actions=actions,
        briefing_summary=build_automation_briefing_summary(session, owner_user_id=owner_user_id),
        generated_at=now,
    )


def _section_alerts(session: Session, *, owner_user_id: int, alert_types: tuple[str, ...], limit: int = 12) -> list[P90CollectorAlertRead]:
    rows = list(
        session.exec(
            select(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == owner_user_id)
            .where(P90CollectorAlert.alert_type.in_(alert_types))  # type: ignore[attr-defined]
            .where(P90CollectorAlert.status.in_(("NEW", "ACKNOWLEDGED")))  # type: ignore[attr-defined]
            .order_by(P90CollectorAlert.priority_score.desc())
            .limit(limit)
        ).all()
    )
    return [_to_read(r) for r in rows]


def build_automation_dashboard(session: Session, *, owner_user_id: int) -> P90AutomationDashboardRead:
    def _build() -> P90AutomationDashboardRead:
        now = datetime.now(timezone.utc)
        return P90AutomationDashboardRead(
            todays_actions=build_action_queue(session, owner_user_id=owner_user_id),
            buy_alerts=_section_alerts(
                session,
                owner_user_id=owner_user_id,
                alert_types=("BUY_OPPORTUNITY", "PRICE_DROP", "WATCHLIST_MATCH"),
            ),
            sell_alerts=_section_alerts(session, owner_user_id=owner_user_id, alert_types=("SELL_OPPORTUNITY",)),
            grade_alerts=_section_alerts(session, owner_user_id=owner_user_id, alert_types=("GRADE_OPPORTUNITY",)),
            collection_gaps=_section_alerts(session, owner_user_id=owner_user_id, alert_types=("COLLECTION_GAP",)),
            release_alerts=_section_alerts(
                session,
                owner_user_id=owner_user_id,
                alert_types=("RELEASE_ALERT", "PORTFOLIO_ACTION"),
            ),
            generated_at=now,
        )

    return p90_safe_call(session, _build, default=_empty_automation_dashboard(), label="automation_dashboard")
