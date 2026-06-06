"""Safe GET handlers for visible nav routes — cached reads, no generation on load."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import CollectionRiskSnapshot, CollectionValuationSnapshot
from app.schemas.foc_dashboard import FocDashboardRead, FocDashboardSummaryRead
from app.schemas.key_issue_intelligence import KeyIssueDashboardRead
from app.schemas.p78_sell_workflow import P78SellQueueListResponse
from app.schemas.p81_discovery import P81DiscoveryFeedRead
from app.schemas.p81_discovery_personalization import P81FuturePullListResponse
from app.schemas.p82_p84_collector_expansion import (
    CollectionForecastRead,
    CollectionOptimizationRead,
    CollectionRiskRead,
    CollectionValuationDashboardRead,
    MarketplaceAcquisitionListResponse,
)
from app.services.collector_page_load_service import _forecast_from_valuation_snapshot, _short_error
from app.services.foc_dashboard import get_foc_dashboard
from app.services.key_issue_dashboard import build_key_issue_dashboard
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p81_discovery_personalization_service import list_future_pull_list
from app.services.p81_discovery_service import build_discovery_feed

logger = logging.getLogger(__name__)

_KEY_ISSUE_LIMIT = 12


def _risk_from_snapshot(session: Session, *, owner_user_id: int) -> CollectionRiskRead | None:
    risk = session.exec(
        select(CollectionRiskSnapshot)
        .where(CollectionRiskSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectionRiskSnapshot.created_at.desc(), CollectionRiskSnapshot.id.desc())
        .limit(1)
    ).first()
    if risk is None:
        return None
    return CollectionRiskRead(
        risk_score=float(risk.risk_score),
        risk_category=risk.risk_category,  # type: ignore[arg-type]
        factors=dict(risk.factors_json or {}),
        snapshot_id=int(risk.id or 0) or None,
    )


def fast_marketplace_opportunities_list(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None,
    limit: int,
    offset: int,
    refresh: bool,
) -> MarketplaceAcquisitionListResponse:
    if refresh:
        return MarketplaceAcquisitionListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message="Live marketplace scan disabled on page load; use scan POST or ops jobs.",
        )
    try:
        body = list_acquisition_opportunities(
            session,
            owner_user_id=owner_user_id,
            recommendation=recommendation,
            limit=limit,
            offset=offset,
            refresh=False,
        )
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_marketplace_opportunities_list failed: %s", exc, exc_info=True)
        return MarketplaceAcquisitionListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message=_short_error(exc),
        )


def fast_valuation_dashboard(session: Session, *, owner_user_id: int) -> CollectionValuationDashboardRead:
    try:
        forecast = _forecast_from_valuation_snapshot(session, owner_user_id=owner_user_id)
        risk = _risk_from_snapshot(session, owner_user_id=owner_user_id)
        if forecast is None:
            forecast = CollectionForecastRead(current_value=0.0, horizons=[], snapshot_id=None)
        if risk is None:
            risk = CollectionRiskRead(risk_score=0.0, risk_category="LOW_RISK", factors={}, snapshot_id=None)
        empty_opt = CollectionOptimizationRead()
        status = "OK" if forecast.snapshot_id or risk.snapshot_id else "SKIPPED"
        message = "" if status == "OK" else "No cached valuation snapshot; run valuation from Collection Forecast."
        return CollectionValuationDashboardRead(
            forecast=forecast,
            risk=risk,
            optimization=empty_opt,
            status=status,
            message=message,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_valuation_dashboard failed: %s", exc, exc_info=True)
        return CollectionValuationDashboardRead(
            forecast=CollectionForecastRead(current_value=0.0, horizons=[]),
            risk=CollectionRiskRead(risk_score=0.0, risk_category="LOW_RISK", factors={}),
            optimization=CollectionOptimizationRead(),
            status="ERROR",
            message=_short_error(exc),
        )


def fast_sell_queue_list(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
    refresh: bool,
) -> P78SellQueueListResponse:
    if refresh:
        logger.info("sell_queue GET refresh=true ignored for owner_user_id=%s", owner_user_id)
    try:
        body = build_sell_queue(
            session,
            owner_user_id=owner_user_id,
            limit=limit,
            offset=offset,
            refresh_upstream=False,
        )
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_sell_queue_list failed: %s", exc, exc_info=True)
        return P78SellQueueListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message=_short_error(exc),
        )


def fast_discovery_feed(session: Session, *, owner_user_id: int, refresh: bool) -> P81DiscoveryFeedRead:
    if refresh:
        logger.info("discovery_feed GET refresh=true ignored for owner_user_id=%s", owner_user_id)
    try:
        body = build_discovery_feed(session, owner_user_id=owner_user_id, refresh=False)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_discovery_feed failed: %s", exc, exc_info=True)
        return P81DiscoveryFeedRead(status="ERROR", message=_short_error(exc))


def fast_future_pull_list(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
    refresh: bool,
) -> P81FuturePullListResponse:
    if refresh:
        logger.info("future_pull_list GET refresh=true ignored for owner_user_id=%s", owner_user_id)
    try:
        body = list_future_pull_list(
            session,
            owner_user_id=owner_user_id,
            limit=limit,
            offset=offset,
            refresh=False,
        )
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_future_pull_list failed: %s", exc, exc_info=True)
        return P81FuturePullListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message=_short_error(exc),
        )


def safe_foc_dashboard(session: Session, *, owner_user_id: int, **filters) -> FocDashboardRead:
    try:
        body = get_foc_dashboard(session, owner_user_id=owner_user_id, **filters)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_foc_dashboard failed: %s", exc, exc_info=True)
        return FocDashboardRead(
            summary=FocDashboardSummaryRead(),
            status="ERROR",
            message=_short_error(exc),
        )


def safe_key_issues_dashboard(session: Session, *, owner_user_id: int) -> KeyIssueDashboardRead:
    try:
        body = build_key_issue_dashboard(session, owner_user_id=owner_user_id, limit=_KEY_ISSUE_LIMIT)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_key_issues_dashboard failed: %s", exc, exc_info=True)
        return KeyIssueDashboardRead(
            status="ERROR",
            message=_short_error(exc),
            total_profiles=0,
        )
