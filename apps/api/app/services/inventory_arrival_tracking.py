from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models import User
from app.schemas.inventory_arrival_tracking import (
    InventoryArrivalTrackingLane,
    InventoryArrivalTrackingResponse,
    InventoryArrivalTrackingRow,
    InventoryArrivalTrackingSummary,
)
from app.services.order_arrival_intelligence import (
    OrderArrivalProjectionRow,
    _inventory_arrival_projection_rows,
    _utc_today,
)


def classify_inventory_arrival_lane(
    row: OrderArrivalProjectionRow,
    *,
    today: date,
) -> InventoryArrivalTrackingLane | None:
    """Mutually exclusive lane for copies that are ordered/preordered/shipped but not received."""

    if row.order_status in ("cancelled", "received"):
        return None

    release_date = row.release_date

    if row.release_status == "not_released_yet" or row.order_status == "preordered":
        return "not_released_yet"
    if release_date is not None and release_date > today:
        return "not_released_yet"

    if row.order_status == "shipped":
        return "on_the_way"

    if row.expected_ship_date is not None and row.received_at is None:
        if release_date is None or release_date <= today:
            return "on_the_way"

    if row.received_at is None:
        if row.release_status == "released":
            return "released_not_received"
        if release_date is not None and release_date <= today:
            return "released_not_received"
        if row.order_status == "ordered":
            return "released_not_received"

    return "released_not_received"


def _row_to_read(row: OrderArrivalProjectionRow, lane: InventoryArrivalTrackingLane) -> InventoryArrivalTrackingRow:
    return InventoryArrivalTrackingRow(
        inventory_copy_id=row.inventory_copy_id,
        title=row.title,
        publisher=row.publisher,
        issue_number=row.issue_number,
        retailer=row.retailer,
        source_type=row.source_type,
        order_status=row.order_status,
        release_status=row.release_status,
        release_date=row.release_date,
        expected_ship_date=row.expected_ship_date,
        received_at=row.received_at,
        lane=lane,
    )


def _release_sort_key(item: InventoryArrivalTrackingRow) -> tuple[date | None, str, str, str, int]:
    missing = date.max
    rd = item.release_date if item.release_date is not None else missing
    return (rd, item.publisher, item.title, item.issue_number, item.inventory_copy_id)


def build_inventory_arrival_tracking(
    session: Session,
    *,
    current_user: User,
    not_released_limit: int = 50,
) -> InventoryArrivalTrackingResponse:
    user_id = int(current_user.id) if current_user.id is not None else None
    today = _utc_today()
    limit = max(1, min(not_released_limit, 200))

    projections = _inventory_arrival_projection_rows(session, user_id=user_id)

    counts = {
        "on_the_way": 0,
        "not_released_yet": 0,
        "released_not_received": 0,
    }
    not_released_rows: list[InventoryArrivalTrackingRow] = []

    for projection in projections:
        lane = classify_inventory_arrival_lane(projection, today=today)
        if lane is None:
            continue
        counts[lane] += 1
        if lane == "not_released_yet":
            not_released_rows.append(_row_to_read(projection, lane))

    not_released_rows.sort(key=_release_sort_key)
    not_released_rows = not_released_rows[:limit]

    total = counts["on_the_way"] + counts["not_released_yet"] + counts["released_not_received"]

    summary = InventoryArrivalTrackingSummary(
        scope_user_id=user_id,
        generated_as_of_date=today.isoformat(),
        not_in_hand_total=total,
        on_the_way_count=counts["on_the_way"],
        not_released_yet_count=counts["not_released_yet"],
        released_not_received_count=counts["released_not_received"],
    )

    return InventoryArrivalTrackingResponse(
        summary=summary,
        not_released_yet_items=not_released_rows,
    )
