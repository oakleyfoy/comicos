from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models import (
    LiveSaleClaim,
    LiveSaleQueueItem,
    LiveSaleSession,
    MarketplaceEvent,
    MarketplaceEventProcessingRun,
    MarketplaceListingDraft,
    MarketplaceOffer,
    MarketplaceOrder,
    MarketplacePricingEvent,
    MarketplacePriceRecommendation,
    ShopifyProductMapping,
    ShopifyStorefront,
    ShopifySyncState,
)
from app.services.live_sale_claim_service import CLAIM_STATUS_CLAIMED
from app.services.live_sale_queue_service import QUEUE_ITEM_STATUS_SOLD
from app.services.live_sale_workflow_service import SESSION_STATUS_LIVE
from app.services.marketplace_event_processing import EVENT_STATUS_PROCESSED
from app.services.marketplace_offer_service import OFFER_STATUS_RECEIVED
from app.services.marketplace_order_ingestion import ORDER_STATUS_IMPORTED
from app.services.marketplace_pricing_service import RECOMMENDATION_STATUS_GENERATED, RECOMMENDATION_STATUS_REVIEWED
from app.services.shopify_publication_registry import MAPPING_STATUS_MAPPED, MAPPING_STATUS_INVALID


@dataclass(frozen=True)
class MarketplaceTrendDefinition:
    trend_key: str
    trend_group: str
    display_name: str
    trend_period: str = "30d"


MARKETPLACE_TREND_DEFINITIONS: tuple[MarketplaceTrendDefinition, ...] = (
    MarketplaceTrendDefinition("listing_growth", "listings", "Listing growth"),
    MarketplaceTrendDefinition("order_growth", "orders", "Order growth"),
    MarketplaceTrendDefinition("sales_growth", "orders", "Sales growth"),
    MarketplaceTrendDefinition("recommendation_activity", "pricing", "Recommendation activity"),
    MarketplaceTrendDefinition("event_processing_activity", "events", "Event processing activity"),
    MarketplaceTrendDefinition("live_sale_activity", "live_sales", "Live sale activity"),
    MarketplaceTrendDefinition("storefront_activity", "shopify", "Storefront activity"),
)


def list_marketplace_trend_definitions() -> tuple[MarketplaceTrendDefinition, ...]:
    return MARKETPLACE_TREND_DEFINITIONS


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


def _window_bounds(now: datetime, period: str) -> tuple[datetime, datetime, datetime]:
    if period == "30d":
        current_start = now - timedelta(days=30)
        previous_start = now - timedelta(days=60)
    else:
        current_start = now - timedelta(days=30)
        previous_start = now - timedelta(days=60)
    return current_start, previous_start, now


def _ratio(current: Decimal | int, previous: Decimal | int) -> float:
    current_value = Decimal(str(current))
    previous_value = Decimal(str(previous))
    if previous_value == 0:
        return float(current_value) if current_value != 0 else 0.0
    return float((current_value - previous_value) / previous_value)


def _period_payload(*, current_count: Decimal | int, previous_count: Decimal | int, period: str, now: datetime) -> dict[str, Any]:
    current_start, previous_start, current_end = _window_bounds(now, period)
    return _json_safe(
        {
            "trend_period": period,
            "current_window_start": current_start,
            "current_window_end": current_end,
            "previous_window_start": previous_start,
            "previous_window_end": current_start,
            "current_count": current_count,
            "previous_count": previous_count,
            "delta": Decimal(str(current_count)) - Decimal(str(previous_count)),
            "delta_rate": _ratio(current_count, previous_count),
        }
    )


def _time_filtered_rows(rows: list[Any], *, attribute: str, start: datetime, end: datetime) -> list[Any]:
    filtered: list[Any] = []
    for row in rows:
        value = getattr(row, attribute)
        if value is None:
            continue
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if start <= value < end:
            filtered.append(row)
    return filtered


def build_marketplace_trend_payloads(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    now = utc_now()
    current_start, previous_start, current_end = _window_bounds(now, "30d")

    listing_rows = session.exec(select(MarketplaceListingDraft).where(MarketplaceListingDraft.organization_id == organization_id)).all()
    order_rows = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.organization_id == organization_id)).all()
    recommendation_rows = session.exec(
        select(MarketplacePriceRecommendation).where(MarketplacePriceRecommendation.organization_id == organization_id)
    ).all()
    event_rows = session.exec(select(MarketplaceEvent).where(MarketplaceEvent.organization_id == organization_id)).all()
    run_rows = session.exec(
        select(MarketplaceEventProcessingRun).where(MarketplaceEventProcessingRun.organization_id == organization_id)
    ).all()
    live_sessions = session.exec(select(LiveSaleSession).where(LiveSaleSession.organization_id == organization_id)).all()
    queue_items = session.exec(select(LiveSaleQueueItem).where(LiveSaleQueueItem.organization_id == organization_id)).all()
    claims = session.exec(select(LiveSaleClaim).where(LiveSaleClaim.organization_id == organization_id)).all()
    storefronts = session.exec(select(ShopifyStorefront).where(ShopifyStorefront.organization_id == organization_id)).all()
    mappings = session.exec(select(ShopifyProductMapping).where(ShopifyProductMapping.organization_id == organization_id)).all()
    sync_states = session.exec(select(ShopifySyncState).where(ShopifySyncState.organization_id == organization_id)).all()
    pricing_events = session.exec(select(MarketplacePricingEvent).where(MarketplacePricingEvent.organization_id == organization_id)).all()
    offers = session.exec(select(MarketplaceOffer).where(MarketplaceOffer.organization_id == organization_id)).all()

    current_listing_rows = _time_filtered_rows(listing_rows, attribute="created_at", start=current_start, end=current_end)
    previous_listing_rows = _time_filtered_rows(listing_rows, attribute="created_at", start=previous_start, end=current_start)

    current_order_rows = _time_filtered_rows(order_rows, attribute="imported_at", start=current_start, end=current_end)
    previous_order_rows = _time_filtered_rows(order_rows, attribute="imported_at", start=previous_start, end=current_start)

    current_order_sales = sum(Decimal(str(row.order_total)) for row in current_order_rows)
    previous_order_sales = sum(Decimal(str(row.order_total)) for row in previous_order_rows)

    current_recommendations = _time_filtered_rows(recommendation_rows, attribute="generated_at", start=current_start, end=current_end)
    previous_recommendations = _time_filtered_rows(recommendation_rows, attribute="generated_at", start=previous_start, end=current_start)

    current_events = _time_filtered_rows(event_rows, attribute="created_at", start=current_start, end=current_end)
    previous_events = _time_filtered_rows(event_rows, attribute="created_at", start=previous_start, end=current_start)

    current_processed_events = [row for row in current_events if row.event_status == EVENT_STATUS_PROCESSED]
    previous_processed_events = [row for row in previous_events if row.event_status == EVENT_STATUS_PROCESSED]

    current_live_sessions = _time_filtered_rows(live_sessions, attribute="created_at", start=current_start, end=current_end)
    previous_live_sessions = _time_filtered_rows(live_sessions, attribute="created_at", start=previous_start, end=current_start)

    current_queue_items = _time_filtered_rows(queue_items, attribute="created_at", start=current_start, end=current_end)
    previous_queue_items = _time_filtered_rows(queue_items, attribute="created_at", start=previous_start, end=current_start)
    current_claims = _time_filtered_rows(claims, attribute="created_at", start=current_start, end=current_end)
    previous_claims = _time_filtered_rows(claims, attribute="created_at", start=previous_start, end=current_start)

    current_storefronts = _time_filtered_rows(storefronts, attribute="created_at", start=current_start, end=current_end)
    previous_storefronts = _time_filtered_rows(storefronts, attribute="created_at", start=previous_start, end=current_start)
    current_sync_states = _time_filtered_rows(sync_states, attribute="created_at", start=current_start, end=current_end)
    previous_sync_states = _time_filtered_rows(sync_states, attribute="created_at", start=previous_start, end=current_start)

    current_mapped_products = [row for row in mappings if row.mapping_status == MAPPING_STATUS_MAPPED]
    current_valid_mappings = [row for row in mappings if row.mapping_status != MAPPING_STATUS_INVALID]
    current_reviewed_recommendations = [row for row in recommendation_rows if row.recommendation_status == RECOMMENDATION_STATUS_REVIEWED]

    return {
        "listing_growth": _period_payload(
            current_count=len(current_listing_rows),
            previous_count=len(previous_listing_rows),
            period="30d",
            now=now,
        ),
        "order_growth": _period_payload(
            current_count=len(current_order_rows),
            previous_count=len(previous_order_rows),
            period="30d",
            now=now,
        ),
        "sales_growth": _period_payload(
            current_count=current_order_sales,
            previous_count=previous_order_sales,
            period="30d",
            now=now,
        ),
        "recommendation_activity": _period_payload(
            current_count=len(current_recommendations) + len(current_reviewed_recommendations),
            previous_count=len(previous_recommendations),
            period="30d",
            now=now,
        ),
        "event_processing_activity": _period_payload(
            current_count=len(current_processed_events),
            previous_count=len(previous_processed_events),
            period="30d",
            now=now,
        ),
        "live_sale_activity": _period_payload(
            current_count=len(current_live_sessions) + len(current_queue_items) + len(current_claims),
            previous_count=len(previous_live_sessions) + len(previous_queue_items) + len(previous_claims),
            period="30d",
            now=now,
        ),
        "storefront_activity": _period_payload(
            current_count=len(current_storefronts) + len(current_sync_states),
            previous_count=len(previous_storefronts) + len(previous_sync_states),
            period="30d",
            now=now,
        ),
        "shopify_mappings": _json_safe(
            {
                "trend_period": "30d",
                "current_mapped_products": len(current_mapped_products),
                "current_valid_product_mappings": len(current_valid_mappings),
                "current_reviewed_recommendations": len(current_reviewed_recommendations),
                "current_offers": len([row for row in offers if row.offer_status == OFFER_STATUS_RECEIVED]),
                "current_sync_states": len(sync_states),
            }
        ),
    }
