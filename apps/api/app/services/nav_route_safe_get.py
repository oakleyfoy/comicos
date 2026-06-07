"""Safe GET handlers for visible nav routes — cached reads, no generation on load."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import CollectionRiskSnapshot, CollectionValuationSnapshot
from app.schemas.foc_dashboard import FocDashboardRead, FocDashboardSummaryRead
from app.schemas.key_issue_intelligence import KeyIssueDashboardRead
from app.schemas.p78_sell_workflow import P78SellQueueListResponse
from app.schemas.p81_discovery import P81DiscoveryFeedRead
from app.schemas.p81_discovery_analytics import (
    P81DiscoveryActivityRead,
    P81DiscoveryAlertPerformanceRead,
    P81DiscoveryAnalyticsDashboardRead,
    P81DiscoveryRoiRead,
    P81FuturePullAnalyticsRead,
    P81PersonalizationImpactRead,
)
from app.schemas.p81_discovery_personalization import (
    P81FuturePullListResponse,
    P81PersonalizedDiscoveryDashboardRead,
    P81PersonalizedDiscoveryListResponse,
    P81PersonalizedOpportunityRead,
)
from app.schemas.p85_production_hardening import P85PlatformCertificationRead
from app.schemas.p82_p84_collector_expansion import (
    CollectionForecastRead,
    CollectionOptimizationRead,
    CollectionRiskRead,
    CollectionValuationDashboardRead,
    MarketplaceAcquisitionListResponse,
)
from app.schemas.grading_intelligence import GradingDashboardRead
from app.schemas.grading_platform import (
    GradingPlatformCalibrationSummary,
    GradingPlatformCertificationRead,
    GradingPlatformConditionSummary,
    GradingPlatformHealthRead,
    GradingPlatformPredictionSummary,
    GradingPlatformRecommendationSummary,
    GradingPlatformReliabilitySummary,
    GradingPlatformRoiSummary,
    GradingPlatformSummaryRead,
    GradingPlatformValidationRead,
)
from app.schemas.p72_grading_operations import P72GradingQueueListResponse
from app.schemas.p78_marketplace import P78SellingAnalyticsRead, P78SellingDashboardRead
from app.schemas.p78_sell_workflow import P78ListingDraftListResponse
from app.schemas.storage_foundation import P79StorageDashboardRead, P79StorageLocationListResponse
from app.services.collector_page_load_service import _forecast_from_valuation_snapshot, _short_error
from app.services.grading_dashboard import build_grading_dashboard
from app.services.grading_platform_health import get_grading_platform_health
from app.services.grading_platform_summary import get_grading_platform_certification, get_grading_platform_summary
from app.services.grading_platform_validation import validate_grading_platform
from app.services.grading_queue_service import list_queue_entries
from app.services.p78_listing_draft_service import list_listing_drafts
from app.services.p78_selling_analytics_service import build_selling_analytics, build_selling_dashboard
from app.services.storage_dashboard_service import build_storage_dashboard
from app.services.storage_location_service import list_storage_locations
from app.services.foc_dashboard import get_foc_dashboard
from app.services.key_issue_dashboard import build_key_issue_dashboard
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p78_sell_queue_service import build_sell_queue
from app.models.p81_discovery import P81DiscoveryOpportunity
from app.models.p81_discovery_analytics import P81DiscoveryAnalyticsSnapshot
from app.services.p81_discovery_analytics_service import (
    _activity_metrics,
    _alert_performance,
    _category_performance,
    _future_pull_analytics,
    _roi_analytics,
    _watchlist_performance,
)
from app.services.p81_discovery_personalization_service import (
    list_alerts,
    list_future_pull_list,
    list_watchlists,
)
from app.services.p81_discovery_service import _to_read, build_discovery_feed
from app.services.platform_production_certification import (
    get_cached_platform_certification,
    run_platform_production_certification,
    store_platform_certification_cache,
)

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


def _empty_storage_dashboard(*, status: str, message: str) -> P79StorageDashboardRead:
    return P79StorageDashboardRead(
        location_count=0,
        box_count=0,
        assigned_books=0,
        unassigned_books=0,
        total_slot_capacity=0,
        occupied_slots=0,
        available_slots=0,
        location_utilization_pct=0.0,
        shelf_utilization_pct=0.0,
        box_utilization_pct=0.0,
        status=status,
        message=message,
    )


def safe_storage_dashboard(session: Session, *, owner_user_id: int) -> P79StorageDashboardRead:
    try:
        body = build_storage_dashboard(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_storage_dashboard failed for owner_user_id=%s", owner_user_id)
        return _empty_storage_dashboard(status="ERROR", message=_short_error(exc))


def safe_storage_locations_list(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> P79StorageLocationListResponse:
    try:
        items, total = list_storage_locations(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
        return P79StorageLocationListResponse(
            items=items,
            total_items=total,
            limit=limit,
            offset=offset,
            status="OK",
            message="",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_storage_locations_list failed for owner_user_id=%s", owner_user_id)
        return P79StorageLocationListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message=_short_error(exc),
        )


def safe_grading_queue_list(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None,
    batch_id: int | None,
    search: str | None,
    limit: int,
    offset: int,
) -> P72GradingQueueListResponse:
    try:
        body = list_queue_entries(
            session,
            owner_user_id=owner_user_id,
            status=status,
            batch_id=batch_id,
            search=search,
            limit=limit,
            offset=offset,
        )
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_grading_queue_list failed for owner_user_id=%s", owner_user_id)
        return P72GradingQueueListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message=_short_error(exc),
        )


def _empty_grading_dashboard(*, status: str, message: str) -> GradingDashboardRead:
    return GradingDashboardRead(
        prediction_count=0,
        recommendation_count=0,
        roi_analysis_count=0,
        average_confidence=0.0,
        average_priority=0.0,
        average_roi_percent=0.0,
        status=status,
        message=message,
    )


def safe_grading_intelligence_dashboard(session: Session, *, owner_user_id: int) -> GradingDashboardRead:
    try:
        body = build_grading_dashboard(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_grading_intelligence_dashboard failed for owner_user_id=%s", owner_user_id)
        return _empty_grading_dashboard(status="ERROR", message=_short_error(exc))


def safe_listing_drafts_list(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None,
    limit: int,
    offset: int,
) -> P78ListingDraftListResponse:
    try:
        body = list_listing_drafts(
            session,
            owner_user_id=owner_user_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_listing_drafts_list failed for owner_user_id=%s", owner_user_id)
        return P78ListingDraftListResponse(
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
            status="ERROR",
            message=_short_error(exc),
        )


def _empty_selling_analytics(*, status: str, message: str) -> P78SellingAnalyticsRead:
    return P78SellingAnalyticsRead(
        revenue=0.0,
        profit=0.0,
        roi_pct=0.0,
        listings_created=0,
        listings_sold=0,
        sell_conversion_rate_pct=0.0,
        average_days_to_sell=None,
        status=status,
        message=message,
    )


def safe_selling_analytics(session: Session, *, owner_user_id: int) -> P78SellingAnalyticsRead:
    try:
        body = build_selling_analytics(session, owner_user_id=owner_user_id, persist=False)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_selling_analytics failed for owner_user_id=%s", owner_user_id)
        return _empty_selling_analytics(status="ERROR", message=_short_error(exc))


def safe_selling_dashboard(session: Session, *, owner_user_id: int) -> P78SellingDashboardRead:
    try:
        body = build_selling_dashboard(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_selling_dashboard failed for owner_user_id=%s", owner_user_id)
        return P78SellingDashboardRead(
            analytics=_empty_selling_analytics(status="ERROR", message=_short_error(exc)),
            status="ERROR",
            message=_short_error(exc),
        )


def _empty_grading_platform_summary(*, status: str, message: str) -> GradingPlatformSummaryRead:
    return GradingPlatformSummaryRead(
        condition_summary=GradingPlatformConditionSummary(
            analysis_count=0,
            profile_count=0,
            average_condition_score=0.0,
            average_quality_score=0.0,
        ),
        prediction_summary=GradingPlatformPredictionSummary(prediction_count=0, average_confidence=0.0),
        recommendation_summary=GradingPlatformRecommendationSummary(recommendation_count=0, average_priority=0.0),
        roi_summary=GradingPlatformRoiSummary(roi_analysis_count=0, average_roi_percent=0.0),
        calibration_summary=GradingPlatformCalibrationSummary(
            validation_count=0,
            calibration_metric_count=0,
            average_accuracy_score=0.0,
        ),
        reliability_summary=GradingPlatformReliabilitySummary(
            reliability_metric_count=0,
            drift_event_count=0,
            average_reliability_score=0.0,
        ),
        status=status,
        message=message,
    )


def safe_grading_platform_summary(session: Session, *, owner_user_id: int) -> GradingPlatformSummaryRead:
    try:
        body = get_grading_platform_summary(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_grading_platform_summary failed for owner_user_id=%s", owner_user_id)
        return _empty_grading_platform_summary(status="ERROR", message=_short_error(exc))


def safe_grading_platform_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthRead:
    try:
        body = get_grading_platform_health(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_grading_platform_health failed for owner_user_id=%s", owner_user_id)
        return GradingPlatformHealthRead(overall_status="ERROR", components=[], status="ERROR", message=_short_error(exc))


def safe_grading_platform_validation(session: Session, *, owner_user_id: int) -> GradingPlatformValidationRead:
    try:
        body = validate_grading_platform(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_grading_platform_validation failed for owner_user_id=%s", owner_user_id)
        return GradingPlatformValidationRead(
            overall_status="ERROR",
            platform_certified=False,
            checks=[],
            status="ERROR",
            message=_short_error(exc),
        )


def safe_grading_platform_certification(session: Session, *, owner_user_id: int) -> GradingPlatformCertificationRead:
    try:
        body = get_grading_platform_certification(session, owner_user_id=owner_user_id)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.exception("safe_grading_platform_certification failed for owner_user_id=%s", owner_user_id)
        return GradingPlatformCertificationRead(
            platform_certified=False,
            validation_status="ERROR",
            health_status="ERROR",
            summary="Unavailable",
            go_live_recommendation="HOLD",
            status="ERROR",
            message=_short_error(exc),
        )


_DISCOVERY_EMPTY_MSG = "No cached discovery data yet."


def _lightweight_personalized(
    row: P81DiscoveryOpportunity,
    *,
    personalized_score: float | None = None,
    priority_category: str | None = None,
) -> P81PersonalizedOpportunityRead:
    score = float(personalized_score if personalized_score is not None else row.discovery_score)
    cat = priority_category or (
        "MUST_BUY"
        if score >= 90
        else "HIGH_PRIORITY"
        if score >= 75
        else "WATCH"
        if score >= 55
        else "LOW_PRIORITY"
        if score >= 35
        else "IGNORE"
    )
    return P81PersonalizedOpportunityRead(
        opportunity=_to_read(row),
        discovery_score=float(row.discovery_score),
        personalized_score=score,
        collector_adjustment=0.0,
        priority_category=cat,  # type: ignore[arg-type]
        recommendation_action="WATCH",
        recommendation_quantity=0,
    )


def fast_discovery_personalized_list(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
    refresh: bool,
) -> P81PersonalizedDiscoveryListResponse:
    if refresh:
        logger.info("discovery/personalized GET refresh=true ignored for owner_user_id=%s", owner_user_id)
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    try:
        pull_body = list_future_pull_list(session, owner_user_id=owner_user_id, limit=200, offset=0, refresh=False)
        items: list[P81PersonalizedOpportunityRead] = []
        for fp in pull_body.items:
            row = session.get(P81DiscoveryOpportunity, fp.opportunity_id)
            if row is None or row.owner_user_id != owner_user_id:
                continue
            items.append(
                _lightweight_personalized(
                    row,
                    personalized_score=float(fp.personalized_score),
                    priority_category=str(fp.priority_category),
                )
            )
        if not items:
            rows = list(
                session.exec(
                    select(P81DiscoveryOpportunity)
                    .where(P81DiscoveryOpportunity.owner_user_id == owner_user_id)
                    .order_by(P81DiscoveryOpportunity.discovery_score.desc(), P81DiscoveryOpportunity.id.desc())
                    .limit(100)
                ).all()
            )
            items = [_lightweight_personalized(r) for r in rows if r.registry_status == "PUBLISHED" or r.discovery_score >= 50]
        if not items:
            return P81PersonalizedDiscoveryListResponse(
                status="EMPTY",
                message=_DISCOVERY_EMPTY_MSG,
                items=[],
                total_items=0,
                limit=lim,
                offset=off,
            )
        page = items[off : off + lim]
        return P81PersonalizedDiscoveryListResponse(
            status="OK",
            message="",
            items=page,
            total_items=len(items),
            limit=lim,
            offset=off,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_discovery_personalized_list failed: %s", exc, exc_info=True)
        return P81PersonalizedDiscoveryListResponse(
            status="ERROR",
            message=_short_error(exc),
            items=[],
            total_items=0,
            limit=lim,
            offset=off,
        )


def fast_discovery_dashboard(session: Session, *, owner_user_id: int, refresh: bool) -> P81PersonalizedDiscoveryDashboardRead:
    if refresh:
        logger.info("discovery/dashboard GET refresh=true ignored for owner_user_id=%s", owner_user_id)
    try:
        pull_body = list_future_pull_list(session, owner_user_id=owner_user_id, limit=30, offset=0, refresh=False)
        personalized: list[P81PersonalizedOpportunityRead] = []
        for fp in pull_body.items:
            row = session.get(P81DiscoveryOpportunity, fp.opportunity_id)
            if row is None:
                continue
            personalized.append(
                _lightweight_personalized(
                    row,
                    personalized_score=float(fp.personalized_score),
                    priority_category=str(fp.priority_category),
                )
            )
        must_buy = [i for i in personalized if i.priority_category == "MUST_BUY"][:20]
        high = [i for i in personalized if i.priority_category == "HIGH_PRIORITY"][:20]
        watch = [i for i in personalized if i.priority_category == "WATCH"][:20]
        future_pull = pull_body.items
        watchlists = list_watchlists(session, owner_user_id=owner_user_id).items
        alerts = list_alerts(session, owner_user_id=owner_user_id, status="ACTIVE", limit=20, offset=0).items
        if not personalized and not future_pull and not watchlists and not alerts:
            return P81PersonalizedDiscoveryDashboardRead(
                status="EMPTY",
                message=_DISCOVERY_EMPTY_MSG,
                counts={},
            )
        return P81PersonalizedDiscoveryDashboardRead(
            status="OK",
            message="",
            must_buy=must_buy,
            high_priority=high,
            watch=watch,
            future_pull_list=future_pull,
            watchlists=watchlists,
            active_alerts=alerts,
            upcoming_foc=[],
            counts={
                "must_buy": len(must_buy),
                "high_priority": len(high),
                "watch": len(watch),
                "future_pull": len(future_pull),
                "active_alerts": len(alerts),
                "upcoming_foc": 0,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_discovery_dashboard failed: %s", exc, exc_info=True)
        return P81PersonalizedDiscoveryDashboardRead(status="ERROR", message=_short_error(exc))


def fast_discovery_analytics_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    refresh: bool,
) -> P81DiscoveryAnalyticsDashboardRead:
    if refresh:
        logger.info("discovery/analytics-dashboard GET refresh=true ignored for owner_user_id=%s", owner_user_id)
    try:
        snap = session.exec(
            select(P81DiscoveryAnalyticsSnapshot)
            .where(P81DiscoveryAnalyticsSnapshot.owner_user_id == owner_user_id)
            .order_by(P81DiscoveryAnalyticsSnapshot.created_at.desc(), P81DiscoveryAnalyticsSnapshot.id.desc())
            .limit(1)
        ).first()
        activity = _activity_metrics(session, owner_user_id=owner_user_id)
        if activity.opportunities_discovered == 0 and snap is None:
            empty_activity = P81DiscoveryActivityRead(
                opportunities_discovered=0,
                opportunities_published=0,
                opportunities_viewed=0,
                opportunities_saved=0,
                opportunities_purchased=0,
            )
            return P81DiscoveryAnalyticsDashboardRead(
                status="EMPTY",
                message=_DISCOVERY_EMPTY_MSG,
                activity=empty_activity,
                opportunity_performance=[],
                alert_performance=P81DiscoveryAlertPerformanceRead(
                    alerts_sent=0,
                    alerts_opened=0,
                    alerts_clicked=0,
                    alerts_converted=0,
                ),
                watchlist_performance=[],
                future_pull=P81FuturePullAnalyticsRead(recommendations=0, purchased=0, skipped=0, accuracy_pct=0.0),
                discovery_roi=P81DiscoveryRoiRead(portfolio_roi_pct=0.0, average_fmv_gain_pct=0.0, highlights=[]),
                personalization_impact=P81PersonalizationImpactRead(
                    opportunities_evaluated=0,
                    opportunities_adjusted=0,
                    adjustment_rate_pct=0.0,
                ),
                snapshot_ids={},
            )
        if snap is not None and snap.activity_metrics_json:
            activity = P81DiscoveryActivityRead.model_validate(snap.activity_metrics_json)
        return P81DiscoveryAnalyticsDashboardRead(
            status="OK",
            message="",
            activity=activity,
            opportunity_performance=_category_performance(session, owner_user_id=owner_user_id),
            alert_performance=_alert_performance(session, owner_user_id=owner_user_id),
            watchlist_performance=_watchlist_performance(session, owner_user_id=owner_user_id),
            future_pull=_future_pull_analytics(session, owner_user_id=owner_user_id),
            discovery_roi=_roi_analytics(session, owner_user_id=owner_user_id),
            personalization_impact=P81PersonalizationImpactRead(
                opportunities_evaluated=activity.opportunities_discovered,
                opportunities_adjusted=0,
                adjustment_rate_pct=0.0,
            ),
            snapshot_ids={"activity": int(snap.id or 0) if snap else None},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_discovery_analytics_dashboard failed: %s", exc, exc_info=True)
        return P81DiscoveryAnalyticsDashboardRead(
            status="ERROR",
            message=_short_error(exc),
            activity=P81DiscoveryActivityRead(
                opportunities_discovered=0,
                opportunities_published=0,
                opportunities_viewed=0,
                opportunities_saved=0,
                opportunities_purchased=0,
            ),
            opportunity_performance=[],
            alert_performance=P81DiscoveryAlertPerformanceRead(
                alerts_sent=0,
                alerts_opened=0,
                alerts_clicked=0,
                alerts_converted=0,
            ),
            watchlist_performance=[],
            future_pull=P81FuturePullAnalyticsRead(recommendations=0, purchased=0, skipped=0, accuracy_pct=0.0),
            discovery_roi=P81DiscoveryRoiRead(portfolio_roi_pct=0.0, average_fmv_gain_pct=0.0, highlights=[]),
            personalization_impact=P81PersonalizationImpactRead(
                opportunities_evaluated=0,
                opportunities_adjusted=0,
                adjustment_rate_pct=0.0,
            ),
            snapshot_ids={},
        )


def fast_platform_certification(session: Session, *, owner_user_id: int) -> P85PlatformCertificationRead:
    cached = get_cached_platform_certification(owner_user_id)
    if cached is not None:
        return cached
    return P85PlatformCertificationRead(
        title="ComicOS Platform Production Certification (P85)",
        status="SKIPPED",
        message="Certification has not been generated yet.",
        certified_production_release=False,
        readiness_score=0.0,
        checks_passed=0,
        warnings=0,
        failures=0,
        categories=[],
        production_checklist=[],
    )


def generate_platform_certification(session: Session, *, owner_user_id: int) -> P85PlatformCertificationRead:
    body = run_platform_production_certification(session, owner_user_id=owner_user_id)
    store_platform_certification_cache(owner_user_id, body)
    return body
