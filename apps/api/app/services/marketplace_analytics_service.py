from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    LiveSaleClaim,
    LiveSaleQueueItem,
    LiveSaleSession,
    MarketplaceAccount,
    MarketplaceEvent,
    MarketplaceEventProcessingRun,
    MarketplaceInventoryConflict,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
    MarketplaceOffer,
    MarketplaceOrder,
    MarketplaceTransaction,
    MarketplacePriceRecommendation,
    MarketplacePricingEvent,
    ShopifyProductMapping,
    ShopifyStorefront,
    ShopifySyncState,
)
from app.models.marketplace_analytics import (
    MarketplaceAnalyticsEvent,
    MarketplaceAnalyticsSnapshot,
    MarketplaceMetric,
    MarketplacePerformanceTrend,
)
from app.schemas.marketplace_analytics import (
    MarketplaceAnalyticsDashboardResponse,
    MarketplaceAnalyticsEventResponse,
    MarketplaceAnalyticsPermissionResponse,
    MarketplaceAnalyticsSnapshotListResponse,
    MarketplaceAnalyticsSnapshotResponse,
    MarketplaceMetricListResponse,
    MarketplaceMetricResponse,
    MarketplacePerformanceTrendListResponse,
    MarketplacePerformanceTrendResponse,
)
from app.services.live_sale_claim_service import CLAIM_STATUS_CLAIMED
from app.services.live_sale_queue_service import QUEUE_ITEM_STATUS_SOLD
from app.services.live_sale_workflow_service import SESSION_STATUS_LIVE
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED, VERIFICATION_STATUS_VERIFIED
from app.services.marketplace_event_processing import EVENT_STATUS_PROCESSED, PROCESSING_STATUS_FAILED
from app.services.marketplace_inventory_sync_service import CONFLICT_STATUS_RESOLVED, SYNC_STATUS_FAILED
from app.services.marketplace_kpi_registry import list_marketplace_kpi_definitions
from app.services.marketplace_listing_validation import LISTING_STATUS_READY, VALIDATION_STATUS_INVALID, VALIDATION_STATUS_VALID
from app.services.marketplace_offer_service import OFFER_STATUS_RECEIVED
from app.services.marketplace_order_ingestion import (
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IMPORTED,
    ORDER_STATUS_PENDING,
    TRANSACTION_STATUS_COMPLETED,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions
from app.services.marketplace_pricing_service import RECOMMENDATION_STATUS_GENERATED, RECOMMENDATION_STATUS_REVIEWED
from app.services.marketplace_trends import build_marketplace_trend_payloads, list_marketplace_trend_definitions
from app.services.shopify_publication_registry import MAPPING_STATUS_INVALID, MAPPING_STATUS_MAPPED


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplaceAnalyticsPermissionResponse:
    return MarketplaceAnalyticsPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _metric_response(row: MarketplaceMetric) -> MarketplaceMetricResponse:
    return MarketplaceMetricResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        metric_key=row.metric_key,
        metric_value_json=dict(row.metric_value_json or {}),
        metric_period=row.metric_period,
        generated_at=row.generated_at,
    )


def _trend_response(row: MarketplacePerformanceTrend) -> MarketplacePerformanceTrendResponse:
    return MarketplacePerformanceTrendResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        trend_key=row.trend_key,
        trend_payload_json=dict(row.trend_payload_json or {}),
        trend_period=row.trend_period,
        generated_at=row.generated_at,
    )


def _snapshot_response(row: MarketplaceAnalyticsSnapshot) -> MarketplaceAnalyticsSnapshotResponse:
    return MarketplaceAnalyticsSnapshotResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        snapshot_type=row.snapshot_type,
        snapshot_payload_json=dict(row.snapshot_payload_json or {}),
        generated_at=row.generated_at,
    )


def _event_response(row: MarketplaceAnalyticsEvent) -> MarketplaceAnalyticsEventResponse:
    return MarketplaceAnalyticsEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _validate_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_marketplace_analytics_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_analytics_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace analytics visibility is denied for this organization.")
    return resolution


def _validate_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_marketplace_analytics_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_analytics_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace analytics management is denied for this organization.")
    return resolution


def create_marketplace_analytics_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplaceAnalyticsEvent:
    row = MarketplaceAnalyticsEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _latest_rows_by_key(rows: list[Any], *, key_name: str) -> list[Any]:
    latest: dict[str, Any] = OrderedDict()
    for row in rows:
        key = getattr(row, key_name)
        if key not in latest:
            latest[key] = row
    return list(latest.values())


def _count(rows: list[Any], *, predicate) -> int:
    return sum(1 for row in rows if predicate(row))


def _sum_decimal(rows: list[Any], *, value_name: str) -> Decimal:
    total = Decimal("0")
    for row in rows:
        total += Decimal(str(getattr(row, value_name)))
    return total


def _rate(numerator: int | Decimal, denominator: int | Decimal) -> float:
    denominator_value = Decimal(str(denominator))
    if denominator_value == 0:
        return 0.0
    return float(Decimal(str(numerator)) / denominator_value)


def _build_kpi_payloads(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    accounts = session.exec(select(MarketplaceAccount).where(MarketplaceAccount.organization_id == organization_id)).all()
    listings = session.exec(select(MarketplaceListingDraft).where(MarketplaceListingDraft.organization_id == organization_id)).all()
    orders = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.organization_id == organization_id)).all()
    transactions = session.exec(select(MarketplaceTransaction).where(MarketplaceTransaction.organization_id == organization_id)).all()
    recommendations = session.exec(
        select(MarketplacePriceRecommendation).where(MarketplacePriceRecommendation.organization_id == organization_id)
    ).all()
    offers = session.exec(select(MarketplaceOffer).where(MarketplaceOffer.organization_id == organization_id)).all()
    events = session.exec(select(MarketplaceEvent).where(MarketplaceEvent.organization_id == organization_id)).all()
    live_sessions = session.exec(select(LiveSaleSession).where(LiveSaleSession.organization_id == organization_id)).all()
    queue_items = session.exec(select(LiveSaleQueueItem).where(LiveSaleQueueItem.organization_id == organization_id)).all()
    claims = session.exec(select(LiveSaleClaim).where(LiveSaleClaim.organization_id == organization_id)).all()
    mappings = session.exec(select(ShopifyProductMapping).where(ShopifyProductMapping.organization_id == organization_id)).all()

    total_listing_drafts = len(listings)
    ready_listing_drafts = _count(listings, predicate=lambda row: row.listing_status == LISTING_STATUS_READY)
    valid_listing_drafts = _count(listings, predicate=lambda row: row.validation_status == VALIDATION_STATUS_VALID)
    invalid_listing_drafts = _count(listings, predicate=lambda row: row.validation_status == VALIDATION_STATUS_INVALID)

    imported_order_rows = [row for row in orders if row.order_status == ORDER_STATUS_IMPORTED]
    imported_orders = len(imported_order_rows)
    total_sales_amount = _sum_decimal(imported_order_rows, value_name="order_total")
    average_order_value = _rate(total_sales_amount, imported_orders) if imported_orders else 0.0

    total_transaction_volume = _sum_decimal(transactions, value_name="gross_amount")
    reconciliation_success_rate = _rate(
        _count(transactions, predicate=lambda row: row.transaction_status == TRANSACTION_STATUS_COMPLETED),
        len(transactions),
    )

    recommendations_generated = _count(recommendations, predicate=lambda row: row.recommendation_status == RECOMMENDATION_STATUS_GENERATED)
    reviewed_recommendations = _count(recommendations, predicate=lambda row: row.recommendation_status == RECOMMENDATION_STATUS_REVIEWED)
    received_offers = _count(offers, predicate=lambda row: row.offer_status == OFFER_STATUS_RECEIVED)

    processed_events = _count(events, predicate=lambda row: row.event_status == EVENT_STATUS_PROCESSED)
    duplicate_event_identifiers: set[tuple[int, str]] = set()
    duplicate_event_count = 0
    for event in events:
        key = (event.marketplace_account_id, event.external_event_identifier)
        if key in duplicate_event_identifiers:
            duplicate_event_count += 1
        else:
            duplicate_event_identifiers.add(key)
    duplicate_event_rate = _rate(duplicate_event_count, len(events))

    total_live_sale_sessions = len(live_sessions)
    sold_live_sale_items = _count(queue_items, predicate=lambda row: row.item_status == QUEUE_ITEM_STATUS_SOLD)
    claim_conversion_rate = _rate(len(claims), total_live_sale_sessions)

    mapped_products = _count(mappings, predicate=lambda row: row.mapping_status == MAPPING_STATUS_MAPPED)
    valid_product_mappings = _count(mappings, predicate=lambda row: row.mapping_status != MAPPING_STATUS_INVALID)

    sync_runs = session.exec(select(MarketplaceInventorySyncRun).where(MarketplaceInventorySyncRun.organization_id == organization_id)).all()
    conflicts = session.exec(
        select(MarketplaceInventoryConflict)
        .where(MarketplaceInventoryConflict.organization_id == organization_id)
        .where(MarketplaceInventoryConflict.conflict_status != CONFLICT_STATUS_RESOLVED)
    ).all()
    latest_sync_run = session.exec(
        select(MarketplaceInventorySyncRun)
        .where(MarketplaceInventorySyncRun.organization_id == organization_id)
        .order_by(MarketplaceInventorySyncRun.started_at.desc(), MarketplaceInventorySyncRun.id.desc())
    ).first()
    latest_sync_status = latest_sync_run.sync_status if latest_sync_run is not None else "none"

    storefronts = session.exec(select(ShopifyStorefront).where(ShopifyStorefront.organization_id == organization_id)).all()
    sync_states = session.exec(select(ShopifySyncState).where(ShopifySyncState.organization_id == organization_id)).all()

    return {
        "connected_accounts": {"count": _count(accounts, predicate=lambda row: row.account_status == ACCOUNT_STATUS_CONNECTED)},
        "total_listing_drafts": {"count": total_listing_drafts},
        "ready_listing_drafts": {"count": ready_listing_drafts},
        "listing_validation_rate": {
            "valid": valid_listing_drafts,
            "invalid": invalid_listing_drafts,
            "total": total_listing_drafts,
            "rate": _rate(valid_listing_drafts, total_listing_drafts),
        },
        "imported_orders": {"count": imported_orders},
        "total_sales_amount": {"value": str(total_sales_amount)},
        "average_order_value": {"value": str(Decimal(str(average_order_value)).quantize(Decimal("0.01"))) if imported_orders else "0.00"},
        "total_transaction_volume": {"value": str(total_transaction_volume)},
        "reconciliation_success_rate": {
            "completed": _count(transactions, predicate=lambda row: row.transaction_status == TRANSACTION_STATUS_COMPLETED),
            "total": len(transactions),
            "rate": reconciliation_success_rate,
        },
        "recommendations_generated": {"count": recommendations_generated},
        "reviewed_recommendations": {"count": reviewed_recommendations},
        "received_offers": {"count": received_offers},
        "processed_events": {"count": processed_events},
        "duplicate_event_rate": {
            "duplicate_events": duplicate_event_count,
            "total_events": len(events),
            "rate": duplicate_event_rate,
        },
        "total_live_sale_sessions": {"count": total_live_sale_sessions},
        "sold_live_sale_items": {"count": sold_live_sale_items},
        "claim_conversion_rate": {
            "claims": len(claims),
            "sessions": total_live_sale_sessions,
            "rate": claim_conversion_rate,
        },
        "mapped_products": {"count": mapped_products},
        "valid_product_mappings": {"count": valid_product_mappings},
        "sync": {
            "sync_runs": len(sync_runs),
            "open_conflicts": len(conflicts),
            "latest_sync_status": latest_sync_status,
        },
        "shopify": {
            "storefronts": len(storefronts),
            "sync_states": len(sync_states),
        },
    }


def _build_trend_payloads(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    payloads = build_marketplace_trend_payloads(session, organization_id=organization_id)
    return payloads


def generate_marketplace_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplaceMetricListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:metrics_generate")
    payloads = _build_kpi_payloads(session, organization_id=organization_id)
    now = utc_now()
    rows: list[MarketplaceMetric] = []
    for definition in list_marketplace_kpi_definitions():
        row = MarketplaceMetric(
            organization_id=organization_id,
            metric_key=definition.metric_key,
            metric_value_json=_json_safe(payloads[definition.metric_key]),
            metric_period=definition.metric_period,
            generated_at=now,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    create_marketplace_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_metrics_generated",
        event_payload_json={"metric_keys": [definition.metric_key for definition in list_marketplace_kpi_definitions()]},
    )
    session.commit()
    return MarketplaceMetricListResponse(
        items=[_metric_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_metrics(session: Session, *, organization_id: int) -> list[MarketplaceMetricResponse]:
    rows = session.exec(
        select(MarketplaceMetric)
        .where(MarketplaceMetric.organization_id == organization_id)
        .order_by(MarketplaceMetric.generated_at.desc(), MarketplaceMetric.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="metric_key")
    order = {definition.metric_key: index for index, definition in enumerate(list_marketplace_kpi_definitions())}
    latest.sort(key=lambda row: (order.get(row.metric_key, 999), row.metric_key))
    return [_metric_response(row) for row in latest]


def generate_marketplace_trends(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplacePerformanceTrendListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:trends_generate")
    payloads = _build_trend_payloads(session, organization_id=organization_id)
    now = utc_now()
    rows: list[MarketplacePerformanceTrend] = []
    for definition in list_marketplace_trend_definitions():
        row = MarketplacePerformanceTrend(
            organization_id=organization_id,
            trend_key=definition.trend_key,
            trend_payload_json=_json_safe(payloads[definition.trend_key]),
            trend_period=definition.trend_period,
            generated_at=now,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    create_marketplace_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_trends_generated",
        event_payload_json={"trend_keys": [definition.trend_key for definition in list_marketplace_trend_definitions()]},
    )
    session.commit()
    return MarketplacePerformanceTrendListResponse(
        items=[_trend_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_trends(session: Session, *, organization_id: int) -> list[MarketplacePerformanceTrendResponse]:
    rows = session.exec(
        select(MarketplacePerformanceTrend)
        .where(MarketplacePerformanceTrend.organization_id == organization_id)
        .order_by(MarketplacePerformanceTrend.generated_at.desc(), MarketplacePerformanceTrend.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="trend_key")
    order = {definition.trend_key: index for index, definition in enumerate(list_marketplace_trend_definitions())}
    latest.sort(key=lambda row: (order.get(row.trend_key, 999), row.trend_key))
    return [_trend_response(row) for row in latest]


def _build_summary(session: Session, *, organization_id: int) -> dict[str, Any]:
    metrics = _build_current_metrics(session, organization_id=organization_id)
    trends = _build_current_trends(session, organization_id=organization_id)
    if metrics:
        metric_map = {metric.metric_key: metric.metric_value_json for metric in metrics}
    else:
        metric_map = _build_kpi_payloads(session, organization_id=organization_id)
    if trends:
        trend_map = {trend.trend_key: trend.trend_payload_json for trend in trends}
    else:
        trend_map = _build_trend_payloads(session, organization_id=organization_id)
    sync_runs = session.exec(select(MarketplaceInventorySyncRun).where(MarketplaceInventorySyncRun.organization_id == organization_id)).all()
    conflicts = session.exec(
        select(MarketplaceInventoryConflict)
        .where(MarketplaceInventoryConflict.organization_id == organization_id)
        .where(MarketplaceInventoryConflict.conflict_status != CONFLICT_STATUS_RESOLVED)
    ).all()
    latest_sync_run = session.exec(
        select(MarketplaceInventorySyncRun)
        .where(MarketplaceInventorySyncRun.organization_id == organization_id)
        .order_by(MarketplaceInventorySyncRun.started_at.desc(), MarketplaceInventorySyncRun.id.desc())
    ).first()
    storefronts = session.exec(select(ShopifyStorefront).where(ShopifyStorefront.organization_id == organization_id)).all()
    mappings = session.exec(select(ShopifyProductMapping).where(ShopifyProductMapping.organization_id == organization_id)).all()
    sync_states = session.exec(select(ShopifySyncState).where(ShopifySyncState.organization_id == organization_id)).all()
    return _json_safe(
        {
            "accounts": {
                "connected_accounts": metric_map.get("connected_accounts", {}).get("count", 0),
            },
            "listings": {
                "total_listing_drafts": metric_map.get("total_listing_drafts", {}).get("count", 0),
                "ready_listing_drafts": metric_map.get("ready_listing_drafts", {}).get("count", 0),
                "listing_validation_rate": metric_map.get("listing_validation_rate", {}).get("rate", 0.0),
            },
            "orders": {
                "imported_orders": metric_map.get("imported_orders", {}).get("count", 0),
                "total_sales_amount": metric_map.get("total_sales_amount", {}).get("value", "0.00"),
                "average_order_value": metric_map.get("average_order_value", {}).get("value", "0.00"),
            },
            "transactions": {
                "total_transaction_volume": metric_map.get("total_transaction_volume", {}).get("value", "0.00"),
                "reconciliation_success_rate": metric_map.get("reconciliation_success_rate", {}).get("rate", 0.0),
            },
            "pricing": {
                "recommendations_generated": metric_map.get("recommendations_generated", {}).get("count", 0),
                "reviewed_recommendations": metric_map.get("reviewed_recommendations", {}).get("count", 0),
                "received_offers": metric_map.get("received_offers", {}).get("count", 0),
            },
            "events": {
                "processed_events": metric_map.get("processed_events", {}).get("count", 0),
                "duplicate_event_rate": metric_map.get("duplicate_event_rate", {}).get("rate", 0.0),
            },
            "live_sales": {
                "total_live_sale_sessions": metric_map.get("total_live_sale_sessions", {}).get("count", 0),
                "sold_live_sale_items": metric_map.get("sold_live_sale_items", {}).get("count", 0),
                "claim_conversion_rate": metric_map.get("claim_conversion_rate", {}).get("rate", 0.0),
            },
            "shopify": {
                "storefronts": len(storefronts),
                "mapped_products": _count(mappings, predicate=lambda row: row.mapping_status == MAPPING_STATUS_MAPPED),
                "valid_product_mappings": _count(mappings, predicate=lambda row: row.mapping_status != MAPPING_STATUS_INVALID),
                "sync_states": len(sync_states),
            },
            "sync": {
                "sync_runs": len(sync_runs),
                "open_conflicts": len(conflicts),
                "latest_sync_status": latest_sync_run.sync_status if latest_sync_run is not None else "none",
            },
            "trends": {
                trend_key: trend_map.get(trend_key, {}) for trend_key in ["listing_growth", "order_growth", "sales_growth", "recommendation_activity", "event_processing_activity", "live_sale_activity", "storefront_activity"]
            },
        }
    )


def list_marketplace_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceMetricListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:metric:view")
    metrics = _build_current_metrics(session, organization_id=organization_id)
    total = len(metrics)
    items = metrics[offset : offset + limit]
    return MarketplaceMetricListResponse(
        items=items,
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_marketplace_trends(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplacePerformanceTrendListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:trend:view")
    trends = _build_current_trends(session, organization_id=organization_id)
    total = len(trends)
    items = trends[offset : offset + limit]
    return MarketplacePerformanceTrendListResponse(
        items=items,
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_marketplace_snapshots(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceAnalyticsSnapshotListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:snapshot:view")
    base = select(MarketplaceAnalyticsSnapshot).where(MarketplaceAnalyticsSnapshot.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(MarketplaceAnalyticsSnapshot.generated_at.desc(), MarketplaceAnalyticsSnapshot.id.desc()).offset(offset).limit(limit)).all()
    return MarketplaceAnalyticsSnapshotListResponse(
        items=[_snapshot_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def build_marketplace_analytics_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplaceAnalyticsDashboardResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:view")
    create_marketplace_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_analytics_generated",
        event_payload_json={"action": "marketplace_analytics:view"},
    )
    session.commit()
    metrics = _build_current_metrics(session, organization_id=organization_id)
    trends = _build_current_trends(session, organization_id=organization_id)
    snapshots = list_marketplace_snapshots(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=20, offset=0).items
    events = session.exec(
        select(MarketplaceAnalyticsEvent)
        .where(MarketplaceAnalyticsEvent.organization_id == organization_id)
        .order_by(MarketplaceAnalyticsEvent.created_at.desc(), MarketplaceAnalyticsEvent.id.desc())
        .limit(25)
    ).all()
    return MarketplaceAnalyticsDashboardResponse(
        permissions=_permission_response(resolution),
        summary=_build_summary(session, organization_id=organization_id),
        metrics=metrics,
        trends=trends,
        snapshots=snapshots,
        events=[_event_response(row) for row in events],
        latest_snapshot=snapshots[0] if snapshots else None,
    )


def generate_marketplace_analytics_snapshot(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    snapshot_type: str = "marketplace_analytics_snapshot",
) -> MarketplaceAnalyticsSnapshotResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_analytics:snapshot_generate")
    metric_list = generate_marketplace_metrics(session, organization_id=organization_id, actor_user_id=actor_user_id).items
    trend_list = generate_marketplace_trends(session, organization_id=organization_id, actor_user_id=actor_user_id).items
    payload = _json_safe(
        {
            "snapshot_type": snapshot_type,
            "summary": _build_summary(session, organization_id=organization_id),
            "metrics": [metric.model_dump(mode="json") for metric in metric_list],
            "trends": [trend.model_dump(mode="json") for trend in trend_list],
        }
    )
    row = MarketplaceAnalyticsSnapshot(
        organization_id=organization_id,
        snapshot_type=snapshot_type,
        snapshot_payload_json=payload,
        generated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_marketplace_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_performance_calculated",
        event_payload_json={"snapshot_type": snapshot_type, "snapshot_id": int(row.id or 0)},
    )
    create_marketplace_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_snapshot_generated",
        event_payload_json={"snapshot_type": snapshot_type, "snapshot_id": int(row.id or 0)},
    )
    session.commit()
    return _snapshot_response(row)
