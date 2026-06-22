from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import InventoryCopy, OrderItem, User
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    purchase_date_expr,
    retailer_expr,
    source_type_expr,
    title_expr,
)
from app.schemas.inventory_intelligence import KeyedCount
from app.schemas.order_arrival_intelligence import (
    OrderArrivalCalendarCell,
    OrderArrivalCalendarRow,
    OrderArrivalIntelCalendarResponse,
    OrderArrivalIntelListResponse,
    OrderArrivalIntelRead,
    OrderArrivalIntelSummary,
    OrderArrivalIntelSummaryItem,
    OrderArrivalClassification,
)


def _utc_today() -> date:
    """Separate from date.today() for deterministic tests."""

    return date.today()


def _iso_week_bounds(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _as_calendar_date(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(timezone.utc).date()


def _asset_state_expression_labels() -> Any:
    from sqlalchemy import case, or_

    return case(
        (InventoryCopy.order_status == "cancelled", "cancelled"),
        (InventoryCopy.order_status == "received", "in_hand"),
        (
            or_(
                InventoryCopy.release_status == "not_released_yet",
                InventoryCopy.order_status == "preordered",
            ),
            "preorder_not_released_yet",
        ),
        else_="ordered_not_received",
    )


@dataclass(frozen=True)
class OrderArrivalProjectionRow:
    inventory_copy_id: int
    owner_user_id: int | None
    retailer: str
    source_type: str | None
    publisher: str
    title: str
    issue_number: str
    order_item_quantity: int
    purchase_date: date | None
    release_date: date | None
    release_status: str
    order_status: str
    expected_ship_date: date | None
    received_at: datetime | None
    asset_state: str


def _inventory_arrival_projection_rows(session: Session, *, user_id: int | None) -> list[OrderArrivalProjectionRow]:
    stmt = apply_inventory_spine_joins(
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.user_id.label("owner_user_id"),
            retailer_expr().label("retailer"),
            source_type_expr().label("source_type"),
            publisher_expr().label("publisher"),
            title_expr().label("title"),
            issue_number_expr().label("issue_number"),
            OrderItem.quantity.label("order_item_quantity"),
            purchase_date_expr().label("purchase_date"),
            InventoryCopy.release_date.label("release_date"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.expected_ship_date.label("expected_ship_date"),
            InventoryCopy.received_at.label("received_at"),
            _asset_state_expression_labels().label("asset_state"),
        ).select_from(InventoryCopy)
    )
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    stmt = stmt.order_by(InventoryCopy.id.asc())
    rows = session.exec(stmt).all()
    return [
        OrderArrivalProjectionRow(
            inventory_copy_id=int(row.inventory_copy_id),
            owner_user_id=int(row.owner_user_id) if row.owner_user_id is not None else None,
            retailer=str(row.retailer),
            source_type=str(row.source_type) if row.source_type is not None else None,
            publisher=str(row.publisher),
            title=str(row.title),
            issue_number=str(row.issue_number),
            order_item_quantity=int(row.order_item_quantity or 1),
            purchase_date=row.purchase_date,
            release_date=row.release_date,
            release_status=str(row.release_status),
            order_status=str(row.order_status),
            expected_ship_date=row.expected_ship_date,
            received_at=row.received_at,
            asset_state=str(row.asset_state),
        )
        for row in rows
    ]


def _projection_for_inventory(session: Session, *, user_id: int | None, inventory_copy_id: int) -> OrderArrivalProjectionRow | None:
    return next((row for row in _inventory_arrival_projection_rows(session, user_id=user_id) if row.inventory_copy_id == inventory_copy_id), None)


def derive_order_arrival_classifications(row: OrderArrivalProjectionRow, *, today: date) -> list[OrderArrivalClassification]:
    if row.order_status == "cancelled":
        return ["cancelled_order"]

    out: list[OrderArrivalClassification] = []
    recv_empty = row.received_at is None
    recv_date = _as_calendar_date(row.received_at)

    rd = row.release_date
    esd = row.expected_ship_date

    if row.order_status == "preordered" and rd is not None and rd > today:
        out.append("upcoming_preorder")

    week_start, week_end = _iso_week_bounds(today)
    if rd is not None and week_start <= rd <= week_end:
        out.append("releases_this_week")

    if rd is not None and rd <= today and recv_empty:
        out.append("released_not_received")

    if esd is not None and recv_empty:
        ship_window_end = today + timedelta(days=14)
        if today <= esd <= ship_window_end:
            out.append("expected_to_ship_soon")
        if esd < today:
            out.append("overdue_expected_ship")

    if recv_date is not None and today >= recv_date and (today - recv_date).days <= 30:
        out.append("received_recently")

    if (row.order_status == "preordered" or row.release_status == "not_released_yet") and rd is None:
        out.append("missing_release_date")

    if row.order_status in ("ordered", "preordered") and esd is None:
        out.append("missing_expected_ship_date")

    return sorted(dict.fromkeys(out))


def _evidence_snapshot(row: OrderArrivalProjectionRow, *, classification: OrderArrivalClassification, as_of_date: date) -> dict[str, Any]:
    return {
        "classification": classification,
        "purchase_date": None if row.purchase_date is None else row.purchase_date.isoformat(),
        "release_date": None if row.release_date is None else row.release_date.isoformat(),
        "expected_ship_date": None if row.expected_ship_date is None else row.expected_ship_date.isoformat(),
        "received_at": None if row.received_at is None else row.received_at.isoformat(),
        "release_status": row.release_status,
        "order_status": row.order_status,
        "asset_state": row.asset_state,
        "retailer": row.retailer,
        "order_item_quantity": row.order_item_quantity,
        "comparison_as_of_date": as_of_date.isoformat(),
        "comparison_rule": classification,
    }


def _build_intel_reads(rows: Iterable[OrderArrivalProjectionRow], *, today: date) -> list[OrderArrivalIntelRead]:
    reads: list[OrderArrivalIntelRead] = []
    for row in rows:
        for classification in derive_order_arrival_classifications(row, today=today):
            reads.append(
                OrderArrivalIntelRead(
                    intel_key=f"{classification}|{row.inventory_copy_id}",
                    inventory_copy_id=row.inventory_copy_id,
                    classification=classification,
                    retailer=row.retailer,
                    source_type=row.source_type,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    order_item_quantity=row.order_item_quantity,
                    order_status=row.order_status,
                    release_status=row.release_status,
                    asset_state=row.asset_state,
                    purchase_date=row.purchase_date,
                    release_date=row.release_date,
                    expected_ship_date=row.expected_ship_date,
                    received_at=row.received_at,
                    evidence_json=_evidence_snapshot(row, classification=classification, as_of_date=today),
                )
            )
    reads.sort(
        key=lambda item: (
            item.classification,
            item.publisher,
            item.title,
            item.issue_number,
            item.inventory_copy_id,
        )
    )
    return reads


def _matches_intel_filters(
    item: OrderArrivalIntelRead,
    *,
    classification: OrderArrivalClassification | None,
    retailer: str | None,
    publisher: str | None,
    release_date_from: date | None,
    release_date_to: date | None,
    expected_ship_date_from: date | None,
    expected_ship_date_to: date | None,
    order_status: str | None,
    in_hand_only: bool,
) -> bool:
    if classification is not None and item.classification != classification:
        return False
    if retailer is not None and item.retailer != retailer:
        return False
    if publisher is not None and item.publisher != publisher:
        return False
    if order_status is not None and item.order_status != order_status:
        return False
    if in_hand_only and item.order_status != "received":
        return False
    rd = item.release_date
    if release_date_from is not None:
        if rd is None:
            return False
        if rd < release_date_from:
            return False
    if release_date_to is not None:
        if rd is None:
            return False
        if rd > release_date_to:
            return False
    es = item.expected_ship_date
    if expected_ship_date_from is not None:
        if es is None:
            return False
        if es < expected_ship_date_from:
            return False
    if expected_ship_date_to is not None:
        if es is None:
            return False
        if es > expected_ship_date_to:
            return False
    return True


def _summary_from_items(
    *,
    scope_user_id: int | None,
    scope: str,
    items: list[OrderArrivalIntelRead],
    total_inventory_copies: int,
    today_iso: str,
) -> OrderArrivalIntelSummary:
    by_classification: defaultdict[str, int] = defaultdict(int)
    buckets: defaultdict[int, list[OrderArrivalIntelRead]] = defaultdict(list)

    for item in items:
        by_classification[item.classification] += 1
        buckets[item.inventory_copy_id].append(item)

    top_items: list[OrderArrivalIntelSummaryItem] = []
    for inv_id, inv_items in buckets.items():
        inv_items_sorted = sorted(
            inv_items,
            key=lambda r: (
                r.classification,
                r.inventory_copy_id,
            ),
        )
        top = inv_items_sorted[0]
        top_items.append(
            OrderArrivalIntelSummaryItem(
                inventory_copy_id=inv_id,
                publisher=top.publisher,
                title=top.title,
                issue_number=top.issue_number,
                retailer=top.retailer,
                classification_count=len(inv_items_sorted),
                classifications=sorted({r.classification for r in inv_items_sorted}),
                evidence_preview=[
                    r.classification
                    + ": "
                    + (
                        ""
                        if r.release_date is None and r.expected_ship_date is None
                        else ", ".join(
                            part
                            for part in [
                                f"release {r.release_date.isoformat()}" if r.release_date else None,
                                f"ship {r.expected_ship_date.isoformat()}" if r.expected_ship_date else None,
                            ]
                            if part is not None
                        )
                    )
                    for r in inv_items_sorted[:3]
                ],
            )
        )

    top_items.sort(
        key=lambda row: (-row.classification_count, row.publisher, row.title, row.inventory_copy_id),
    )

    return OrderArrivalIntelSummary(
        scope_user_id=scope_user_id,
        scope=scope,
        generated_as_of_date=today_iso,
        total_inventory_copies=total_inventory_copies,
        total_intel_items=len(items),
        copies_tagged=len(buckets),
        by_classification=[KeyedCount(key=key, count=by_classification[key]) for key in sorted(by_classification)],
        top_action_items=top_items[:10],
    )


def compute_order_arrival_intelligence(
    session: Session,
    *,
    current_user: User | None,
    classification: OrderArrivalClassification | None = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: str | None = None,
    in_hand_only: bool = False,
) -> tuple[OrderArrivalIntelListResponse, dict[int, list[OrderArrivalClassification]]]:
    user_id = int(current_user.id) if current_user is not None and current_user.id is not None else None
    scope = "owner" if current_user is not None else "ops"
    today = _utc_today()

    projections = _inventory_arrival_projection_rows(session, user_id=user_id)
    total_inventory_copies = len(projections)

    reads = _build_intel_reads(projections, today=today)
    filtered = [
        row
        for row in reads
        if _matches_intel_filters(
            row,
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
    ]

    classifications_by_inventory: dict[int, list[OrderArrivalClassification]] = {}
    for row in projections:
        classifications_by_inventory[row.inventory_copy_id] = derive_order_arrival_classifications(row, today=today)

    summary = _summary_from_items(
        scope_user_id=user_id,
        scope=scope,
        items=filtered,
        total_inventory_copies=total_inventory_copies,
        today_iso=today.isoformat(),
    )

    response = OrderArrivalIntelListResponse(
        scope_user_id=user_id,
        scope=scope,
        generated_as_of_date=today.isoformat(),
        total_count=len(filtered),
        classification=classification or "all",
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status or "all",
        in_hand_only=in_hand_only,
        summary=summary,
        items=filtered,
    )
    return response, classifications_by_inventory


def classifications_for_inventory_copy(
    session: Session,
    *,
    inventory_copy_id: int,
    user_id: int | None,
) -> list[OrderArrivalClassification]:
    row = _projection_for_inventory(session, user_id=user_id, inventory_copy_id=inventory_copy_id)
    if row is None:
        return []
    return derive_order_arrival_classifications(row, today=_utc_today())


def batch_order_arrival_classifications(
    session: Session,
    *,
    user_id: int | None,
) -> dict[int, list[OrderArrivalClassification]]:
    today = _utc_today()
    projections = _inventory_arrival_projection_rows(session, user_id=user_id)
    return {row.inventory_copy_id: derive_order_arrival_classifications(row, today=today) for row in projections}


def get_order_arrival_calendar(
    session: Session,
    *,
    current_user: User | None,
    calendar_start: date | None,
    calendar_end: date | None,
    classification: OrderArrivalClassification | None = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: str | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelCalendarResponse:
    """Bucket filtered copies onto release / expected ship dates inside the requested window."""

    user_id = int(current_user.id) if current_user is not None and current_user.id is not None else None
    scope = "owner" if current_user is not None else "ops"
    today = _utc_today()
    projections = _inventory_arrival_projection_rows(session, user_id=user_id)

    start = calendar_start or today
    end = calendar_end or (today + timedelta(days=56))
    if end < start:
        raise HTTPException(status_code=400, detail="calendar_end must not be before calendar_start")

    list_response, _ = compute_order_arrival_intelligence(
        session,
        current_user=current_user,
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
    visible_ids = {item.inventory_copy_id for item in list_response.items}

    by_date: dict[date, tuple[list[OrderArrivalProjectionRow], list[OrderArrivalProjectionRow]]] = defaultdict(
        lambda: ([], [])
    )

    for row in projections:
        if row.inventory_copy_id not in visible_ids:
            continue
        rd = row.release_date
        if rd is not None and start <= rd <= end:
            releases, ships = by_date[rd]
            releases.append(row)
        esd = row.expected_ship_date
        if esd is not None and start <= esd <= end:
            releases, ships = by_date[esd]
            ships.append(row)

    calendar_rows: list[OrderArrivalCalendarRow] = []
    cursor = start
    while cursor <= end:
        rel_copies, ship_copies = by_date[cursor]

        def cells_from(rows: list[OrderArrivalProjectionRow]) -> list[OrderArrivalCalendarCell]:
            mapped: list[OrderArrivalCalendarCell] = []
            for r in sorted(rows, key=lambda z: (z.publisher, z.title, z.issue_number, z.inventory_copy_id)):
                derived = derive_order_arrival_classifications(r, today=today)
                cell_cls = derived if classification is None else ([classification] if classification in derived else [])
                mapped.append(
                    OrderArrivalCalendarCell(
                        inventory_copy_id=r.inventory_copy_id,
                        title=r.title,
                        issue_number=r.issue_number,
                        publisher=r.publisher,
                        retailer=r.retailer,
                        order_status=r.order_status,
                        release_status=r.release_status,
                        classifications=cell_cls,
                    )
                )
            return mapped

        calendar_rows.append(
            OrderArrivalCalendarRow(
                calendar_date=cursor,
                on_release_date=cells_from(rel_copies),
                on_expected_ship_date=cells_from(ship_copies),
            )
        )

        cursor += timedelta(days=1)

    return OrderArrivalIntelCalendarResponse(
        scope_user_id=user_id,
        scope=scope,
        generated_as_of_date=today.isoformat(),
        calendar_start=start,
        calendar_end=end,
        rows=calendar_rows,
    )


def order_arrival_summary_only(
    session: Session,
    *,
    user: User,
    classification: OrderArrivalClassification | None = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: str | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelSummary:
    response, _ = compute_order_arrival_intelligence(
        session,
        current_user=user,
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
    return response.summary

