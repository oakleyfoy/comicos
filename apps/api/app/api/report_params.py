"""FastAPI dependency helpers for deterministic read-only CSV/JSON report exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from fastapi import Query

from app.schemas.inventory import ReleaseCalendarPresence
from app.schemas.inventory_action_center import InventoryActionCenterCategory, InventoryReleaseStatusFilter
from app.schemas.inventory_risks import InventoryRiskPriority, InventoryRiskType
from app.schemas.collection_timeline import CollectionTimelineEventType, OwnershipStateFilter
from app.schemas.order_arrival_intelligence import OrderArrivalClassification
from app.services.reports_export import InventoryExportFilters


OrderStatusExportLiteral = Literal["ordered", "preordered", "shipped", "received", "cancelled"]


def parse_inventory_export_filters(
    search: str | None = None,
    publisher: str | None = None,
    hold_status: str | None = None,
    grade_status: str | None = None,
    release_year: Annotated[int | None, Query(ge=1800, le=2999)] = None,
    release_calendar: ReleaseCalendarPresence | None = None,
    asset_state: str | None = None,
    intelligence_health: Annotated[
        Literal["healthy", "needs_review", "incomplete", "blocked", "not_healthy"] | None,
        Query(description="Filter rows by deterministic computed inventory-health bucket."),
    ] = None,
    ownership_intel: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter rows by normalized ownership state (listing query)."),
    ] = None,
    risk_priority: Annotated[
        InventoryRiskPriority | None,
        Query(description="Filter rows by matching inventory risk priority."),
    ] = None,
    risk_type: Annotated[
        InventoryRiskType | None,
        Query(description="Filter rows by matching inventory risk type."),
    ] = None,
    needs_attention: bool = False,
    action_attention: Annotated[
        bool,
        Query(description="When true, only copies that have workflow actions in critical/high lanes."),
    ] = False,
    action_center_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter rows requiring the given deterministic action-center category."),
    ] = None,
    arrival_classification: Annotated[
        OrderArrivalClassification | None,
        Query(description="Filter rows derived order/arrival classification."),
    ] = None,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
    page_size: Annotated[int, Query(ge=1, le=250)] = 125,
    release_status: Annotated[
        str | None,
        Query(description="Exact post-hydrate match on inventory.release_status."),
    ] = None,
    order_status: Annotated[
        OrderStatusExportLiteral | None,
        Query(description="Exact post-hydrate match on inventory.order_status."),
    ] = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Post-hydrate normalized ownership snapshot filter (inventory intelligence JSON)."),
    ] = None,
) -> InventoryExportFilters:
    return InventoryExportFilters(
        search=search,
        publisher=publisher,
        hold_status=hold_status,
        grade_status=grade_status,
        release_year=release_year,
        release_calendar=release_calendar,
        asset_state=asset_state,
        intelligence_health=intelligence_health,
        ownership_intel=ownership_intel,
        risk_priority=risk_priority,
        risk_type=risk_type,
        needs_attention=needs_attention,
        action_attention=action_attention,
        action_center_category=action_center_category,
        arrival_classification=arrival_classification,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page_size=page_size,
        release_status=release_status,
        order_status=order_status,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        start_date=start_date,
        end_date=end_date,
        export_ownership_state=ownership_state,
    )


@dataclass(frozen=True, slots=True)
class OrderArrivalExportParams:
    classification: OrderArrivalClassification | None
    retailer: str | None
    publisher: str | None
    release_date_from: date | None
    release_date_to: date | None
    expected_ship_date_from: date | None
    expected_ship_date_to: date | None
    order_status: OrderStatusExportLiteral | None
    in_hand_only: bool


def parse_order_arrival_export_params(
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderStatusExportLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalExportParams:
    return OrderArrivalExportParams(
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )


@dataclass(frozen=True, slots=True)
class TimelineExportParams:
    event_type: CollectionTimelineEventType | None
    publisher: str | None
    ownership_state: OwnershipStateFilter | None
    release_status: InventoryReleaseStatusFilter | None
    start_date: date | None
    end_date: date | None
    preorder_only: bool
    in_hand_only: bool


def parse_timeline_export_params(
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    publisher: Annotated[str | None, Query(description="Case-insensitive substring match on publisher label.")] = None,
    ownership_state: Annotated[
        OwnershipStateFilter | None,
        Query(description="Filter rows to copies whose current normalized ownership matches."),
    ] = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query()] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
) -> TimelineExportParams:
    return TimelineExportParams(
        event_type=event_type,
        publisher=publisher,
        ownership_state=ownership_state,
        release_status=release_status,
        start_date=start_date,
        end_date=end_date,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
    )
