"""P84/P85 page-load surfaces: cached reads only, no heavy generation on GET."""

from __future__ import annotations

import logging
import time
from datetime import date

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.daily_action_engine import DailyCollectorAction
from app.models.p77_collector_profile import P77CollectorBudget
from app.models.p82_p84_collector_expansion import (
    CollectionRiskSnapshot,
    CollectionValuationSnapshot,
    CollectorNotification,
    utc_now,
)
from app.models.p74_foc_purchase import P74FocAlert, P74FocRecommendationSnapshot
from app.schemas.daily_action_engine import DailyActionListResponse, DailyActionSummaryRead
from app.schemas.p82_p84_collector_expansion import (
    CollectionForecastRead,
    CollectorBriefingRead,
    CollectorCommandCenterRead,
    CollectorNotificationListResponse,
    CollectorNotificationRead,
)
from app.schemas.p85_production_hardening import P85WorkflowHealthRead, P85WorkflowIssueRead
from app.services.collector_briefing_service import _latest_briefing, _to_read as briefing_to_read
from app.services.collector_notification_service import _to_read as notification_to_read
from app.services.daily_action_engine import (
    ACTION_ACQUIRE,
    ACTION_GRADE,
    ACTION_PREORDER,
    ACTION_REBALANCE,
    ACTION_REVIEW,
    ACTION_SELL,
    ACTION_WATCH,
    _latest_action_rows,
    _sort_key,
    _to_read as action_to_read,
)
from app.services.recommendation_latest_rows import latest_by_key_bounded_scan

logger = logging.getLogger(__name__)

_PAGE_LOAD_MAX_SECONDS = 0.75
_CACHED_ACTION_SCAN_LIMIT = 1200


def _short_error(exc: BaseException) -> str:
    message = str(exc).strip()
    return message[:240] if message else exc.__class__.__name__


def fast_list_daily_actions(
    session: Session,
    *,
    owner_user_id: int,
    action_type: str | None = None,
    priority_min: float | None = None,
    due_before: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DailyActionListResponse:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    def _build() -> DailyActionListResponse:
        latest = _latest_action_rows(
            session,
            owner_user_id=owner_user_id,
            scan_limit=_CACHED_ACTION_SCAN_LIMIT,
        )
        rows: list[DailyCollectorAction] = []
        for row in latest.values():
            if action_type and row.action_type != action_type.strip().upper():
                continue
            if priority_min is not None and float(row.priority_score) < float(priority_min):
                continue
            if due_before is not None and row.due_date is not None and row.due_date > due_before:
                continue
            rows.append(row)
        rows.sort(key=_sort_key)
        items = [action_to_read(row, decision=None) for row in rows]
        page = items[offset : offset + limit]
        return DailyActionListResponse(
            items=page,
            total_items=len(items),
            limit=limit,
            offset=offset,
            status="OK",
            message="",
        )

    started = time.perf_counter()
    try:
        body = _build()
        status, message = "OK", ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_list_daily_actions failed: %s", exc, exc_info=True)
        body = DailyActionListResponse(items=[], total_items=0, limit=limit, offset=offset, status="ERROR", message=_short_error(exc))
        return body
    elapsed = time.perf_counter() - started
    if elapsed > _PAGE_LOAD_MAX_SECONDS:
        return DailyActionListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="SKIPPED",
            message="Cached daily actions read exceeded time budget; retry or use background refresh.",
        )
    body.status = status
    body.message = message
    return body


def fast_daily_action_summary(session: Session, *, owner_user_id: int) -> DailyActionSummaryRead:
    listing = fast_list_daily_actions(session, owner_user_id=owner_user_id, limit=500, offset=0)
    if listing.status != "OK":
        return DailyActionSummaryRead(
            total_actions=0,
            critical_actions=0,
            preorder_actions=0,
            acquisition_actions=0,
            grading_actions=0,
            sell_actions=0,
            rebalance_actions=0,
            watch_actions=0,
            status=listing.status,
            message=listing.message or "Summary unavailable.",
        )
    items = listing.items
    return DailyActionSummaryRead(
        total_actions=listing.total_items,
        critical_actions=sum(1 for i in items if i.priority_score >= 90.0),
        preorder_actions=sum(1 for i in items if i.action_type == ACTION_PREORDER),
        acquisition_actions=sum(1 for i in items if i.action_type == ACTION_ACQUIRE),
        grading_actions=sum(1 for i in items if i.action_type == ACTION_GRADE),
        sell_actions=sum(1 for i in items if i.action_type == ACTION_SELL),
        rebalance_actions=sum(1 for i in items if i.action_type == ACTION_REBALANCE),
        watch_actions=sum(1 for i in items if i.action_type in {ACTION_WATCH, ACTION_REVIEW}),
        status="OK",
        message="",
    )


def safe_daily_actions_list_fallback(*, limit: int, offset: int, message: str) -> DailyActionListResponse:
    return DailyActionListResponse(
        items=[],
        total_items=0,
        limit=limit,
        offset=offset,
        status="ERROR",
        message=message[:240],
    )


def safe_daily_action_summary_fallback(message: str) -> DailyActionSummaryRead:
    return DailyActionSummaryRead(
        total_actions=0,
        critical_actions=0,
        preorder_actions=0,
        acquisition_actions=0,
        grading_actions=0,
        sell_actions=0,
        rebalance_actions=0,
        watch_actions=0,
        status="ERROR",
        message=message[:240],
    )


def fast_list_collector_notifications(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> CollectorNotificationListResponse:
    lim = max(1, min(limit, 200))
    off = max(0, offset)

    def _build() -> CollectorNotificationListResponse:
        stmt = select(CollectorNotification).where(CollectorNotification.owner_user_id == owner_user_id)
        if status:
            stmt = stmt.where(CollectorNotification.status == status.strip().upper())
        rows = list(session.exec(stmt.order_by(CollectorNotification.created_at.desc())).all())
        unread = sum(1 for r in rows if r.status == "UNREAD")
        page = [notification_to_read(r) for r in rows[off : off + lim]]
        return CollectorNotificationListResponse(
            items=page,
            total_items=len(rows),
            limit=lim,
            offset=off,
            unread_count=unread,
            status="OK",
            message="",
        )

    started = time.perf_counter()
    try:
        body = _build()
    except Exception as exc:  # noqa: BLE001
        return CollectorNotificationListResponse(
            items=[],
            total_items=0,
            limit=lim,
            offset=off,
            unread_count=0,
            status="ERROR",
            message=_short_error(exc),
        )
    if time.perf_counter() - started > _PAGE_LOAD_MAX_SECONDS:
        return CollectorNotificationListResponse(
            items=[],
            total_items=0,
            limit=lim,
            offset=off,
            unread_count=0,
            status="SKIPPED",
            message="Notification list read exceeded time budget.",
        )
    return body


def safe_notifications_fallback(*, limit: int, offset: int, message: str) -> CollectorNotificationListResponse:
    return CollectorNotificationListResponse(
        items=[],
        total_items=0,
        limit=limit,
        offset=offset,
        unread_count=0,
        status="ERROR",
        message=message[:240],
    )


def fast_get_daily_briefing(session: Session, *, owner_user_id: int) -> CollectorBriefingRead:
    day = date.today()
    try:
        row = _latest_briefing(session, owner_user_id=owner_user_id, briefing_type="DAILY", briefing_date=day)
        if row:
            out = briefing_to_read(row)
            out.status = "OK"
            out.message = ""
            return out
        return CollectorBriefingRead(
            id=0,
            briefing_type="DAILY",
            briefing_date=day,
            sections={},
            top_actions=[],
            created_at=utc_now(),
            status="SKIPPED",
            message="No cached daily briefing; use POST /briefings/generate when ready.",
        )
    except Exception as exc:  # noqa: BLE001
        return CollectorBriefingRead(
            id=0,
            briefing_type="DAILY",
            briefing_date=day,
            sections={},
            top_actions=[],
            created_at=utc_now(),
            status="ERROR",
            message=_short_error(exc),
        )


def fast_get_weekly_briefing(session: Session, *, owner_user_id: int) -> CollectorBriefingRead:
    day = date.today()
    try:
        row = _latest_briefing(session, owner_user_id=owner_user_id, briefing_type="WEEKLY", briefing_date=day)
        if row:
            out = briefing_to_read(row)
            out.status = "OK"
            out.message = ""
            return out
        return CollectorBriefingRead(
            id=0,
            briefing_type="WEEKLY",
            briefing_date=day,
            sections={},
            top_actions=[],
            created_at=utc_now(),
            status="SKIPPED",
            message="No cached weekly briefing; use POST /briefings/generate when ready.",
        )
    except Exception as exc:  # noqa: BLE001
        return CollectorBriefingRead(
            id=0,
            briefing_type="WEEKLY",
            briefing_date=day,
            sections={},
            top_actions=[],
            created_at=utc_now(),
            status="ERROR",
            message=_short_error(exc),
        )


def _forecast_from_valuation_snapshot(session: Session, *, owner_user_id: int) -> CollectionForecastRead | None:
    valuation = session.exec(
        select(CollectionValuationSnapshot)
        .where(CollectionValuationSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectionValuationSnapshot.created_at.desc(), CollectionValuationSnapshot.id.desc())
        .limit(1)
    ).first()
    if valuation is None:
        return None
    return CollectionForecastRead(
        current_value=float(valuation.current_value),
        horizons=[],
        snapshot_id=int(valuation.id or 0) or None,
    )


def _budget_dict(session: Session, *, owner_user_id: int) -> dict:
    budget = session.exec(
        select(P77CollectorBudget).where(P77CollectorBudget.owner_user_id == owner_user_id).limit(1)
    ).first()
    if budget is None:
        return {"status": "SKIPPED", "state": None, "monthly_budget": None, "monthly_spend": None}
    return {
        "status": "OK",
        "state": "CONFIGURED" if float(budget.monthly_budget or 0) > 0 else "UNSET",
        "monthly_budget": float(budget.monthly_budget or 0),
        "monthly_spend": None,
    }


def _portfolio_dict(session: Session, *, owner_user_id: int) -> dict:
    valuation = session.exec(
        select(CollectionValuationSnapshot)
        .where(CollectionValuationSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectionValuationSnapshot.created_at.desc())
        .limit(1)
    ).first()
    risk = session.exec(
        select(CollectionRiskSnapshot)
        .where(CollectionRiskSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectionRiskSnapshot.created_at.desc())
        .limit(1)
    ).first()
    if valuation is None and risk is None:
        return {"status": "SKIPPED", "current_value": None, "risk_category": None}
    return {
        "status": "OK",
        "current_value": float(valuation.current_value) if valuation else None,
        "risk_category": risk.risk_category if risk else None,
    }


def _risk_alerts_from_cache(session: Session, *, owner_user_id: int) -> list[CollectorNotificationRead]:
    rows = session.exec(
        select(CollectorNotification)
        .where(
            CollectorNotification.owner_user_id == owner_user_id,
            CollectorNotification.notification_type == "PORTFOLIO_RISK_ALERT",
            CollectorNotification.status != "DISMISSED",
        )
        .order_by(CollectorNotification.created_at.desc())
        .limit(5)
    ).all()
    return [notification_to_read(r) for r in rows]


def _foc_preview(session: Session, *, owner_user_id: int) -> list[dict]:
    snap = session.exec(
        select(P74FocRecommendationSnapshot)
        .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P74FocRecommendationSnapshot.generated_at.desc())
        .limit(1)
    ).first()
    if snap is None:
        return []
    alerts = session.exec(
        select(P74FocAlert)
        .where(P74FocAlert.snapshot_id == int(snap.id or 0))
        .order_by(P74FocAlert.priority_score.desc())
        .limit(8)
    ).all()
    return [{"title": a.title, "status": a.alert_type} for a in alerts]


def fast_build_collector_command_center(session: Session, *, owner_user_id: int) -> CollectorCommandCenterRead:
    try:
        forecast = _forecast_from_valuation_snapshot(session, owner_user_id=owner_user_id)
        daily = fast_get_daily_briefing(session, owner_user_id=owner_user_id)
        return CollectorCommandCenterRead(
            marketplace_deals=[],
            collection_forecast=forecast,
            risk_alerts=_risk_alerts_from_cache(session, owner_user_id=owner_user_id),
            daily_briefing=daily,
            top_buy_opportunities=[],
            top_sell_opportunities=[],
            upcoming_foc=_foc_preview(session, owner_user_id=owner_user_id),
            discovery_alerts=[],
            budget_status=_budget_dict(session, owner_user_id=owner_user_id),
            portfolio_movement=_portfolio_dict(session, owner_user_id=owner_user_id),
            storage_warnings=[],
            grading_candidates=[],
            status="OK",
            message="",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_build_collector_command_center failed: %s", exc, exc_info=True)
        return CollectorCommandCenterRead(
            status="ERROR",
            message=_short_error(exc),
        )


def safe_command_center_fallback(message: str) -> CollectorCommandCenterRead:
    return CollectorCommandCenterRead(status="ERROR", message=message[:240])


def fast_build_workflow_health(session: Session, *, owner_user_id: int) -> P85WorkflowHealthRead:
    issues: list[P85WorkflowIssueRead] = []
    empty_workflows: list[str] = []

    try:
        has_inventory = (
            session.exec(
                select(InventoryCopy.id)
                .where(InventoryCopy.user_id == owner_user_id)
                .where(InventoryCopy.hold_status != "sold")
                .limit(1)
            ).first()
            is not None
        )
        if not has_inventory:
            empty_workflows.append("inventory")
            issues.append(
                P85WorkflowIssueRead(
                    workflow="inventory",
                    severity="MEDIUM",
                    issue_type="NO_DATA",
                    message="No inventory copies yet.",
                    recommended_fix="Import an order or add inventory from the dashboard.",
                    action_url="/dashboard",
                )
            )

        action_rows = latest_by_key_bounded_scan(
            session,
            model=DailyCollectorAction,
            owner_user_id=owner_user_id,
            owner_field="owner_user_id",
            key_fn=lambda row: (row.action_type, row.title.strip().lower()),
            scan_limit=200,
        )
        if not action_rows:
            empty_workflows.append("daily_actions")
            issues.append(
                P85WorkflowIssueRead(
                    workflow="daily_actions",
                    severity="LOW",
                    issue_type="NO_DATA",
                    message="No cached daily actions yet.",
                    recommended_fix="Run daily action generation from a background job.",
                    action_url="/daily-actions",
                )
            )

        issues.append(
            P85WorkflowIssueRead(
                workflow="deep_scan",
                severity="LOW",
                issue_type="SKIPPED",
                message="Deep workflow scans disabled on page load.",
                recommended_fix="Use dedicated pages or ops jobs for sell queue and discovery checks.",
                action_url="/workflow-health",
            )
        )

        broken = [i for i in issues if i.issue_type == "BROKEN"]
        score = max(0.0, 100.0 - len(broken) * 25.0 - len(empty_workflows) * 5.0)
        status = "HEALTHY" if not broken else "DEGRADED"
        if score < 50:
            status = "NEEDS_ATTENTION"

        return P85WorkflowHealthRead(
            health_score=round(score, 1),
            status=status,
            issues=issues[:30],
            stale_jobs=[],
            empty_workflows=empty_workflows,
            load_message="",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_build_workflow_health failed: %s", exc, exc_info=True)
        return P85WorkflowHealthRead(
            health_score=0.0,
            status="DEGRADED",
            issues=[
                P85WorkflowIssueRead(
                    workflow="workflow_health",
                    severity="HIGH",
                    issue_type="ERROR",
                    message=_short_error(exc),
                    recommended_fix="Retry workflow health or check API logs.",
                    action_url="/workflow-health",
                )
            ],
            empty_workflows=[],
            load_message=_short_error(exc),
        )


def safe_workflow_health_fallback(message: str) -> P85WorkflowHealthRead:
    return P85WorkflowHealthRead(
        health_score=0.0,
        status="DEGRADED",
        issues=[
            P85WorkflowIssueRead(
                workflow="workflow_health",
                severity="HIGH",
                issue_type="ERROR",
                message=message[:240],
                recommended_fix="Retry workflow health.",
                action_url="/workflow-health",
            )
        ],
        load_message=message[:240],
    )
