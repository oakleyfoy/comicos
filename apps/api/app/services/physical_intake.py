"""Deterministic physical receiving + intake dashboards (explicit mutations only).

No automatic OCR, scan processing beyond user-created placeholder session rows, or metadata mutation beyond receiving fields."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, Variant, User
from app.models.asset_ledger import utc_now
from app.schemas.inventory import (
    BulkMarkInventoryReceivedItemResult,
    BulkMarkInventoryReceivedRequest,
    BulkMarkInventoryReceivedResponse,
    InventoryRow,
    InventoryUpdate,
)
from app.schemas.order_arrival_intelligence import OrderArrivalClassification
from app.schemas.physical_intake import (
    CreatePhysicalIntakeScanSessionPayload,
    MarkInventoryReceivedPayload,
    PhysicalIntakeDashboardBucket,
    PhysicalIntakeItemRead,
    PhysicalIntakeListResponse,
    PhysicalIntakeState,
    PhysicalIntakeSummaryCounts,
    PhysicalIntakeSummaryResponse,
)
from app.schemas.scan_sessions import (
    ScanSessionCreatePayload,
    ScanSessionDetailRead,
    ScanSessionItemCreatePayload,
    ScanSessionItemsAppendPayload,
)
from app.services.inventory import inventory_row_for_copy, update_inventory_copy
from app.services.inventory_intelligence import (
    _covers_by_inventory,
    _latest_ocr_map,
    _pick_primary_cover,
)
from app.services.order_arrival_intelligence import (
    OrderArrivalProjectionRow,
    _asset_state_expression_labels,
    derive_order_arrival_classifications,
)
from app.services.scan_sessions import append_scan_session_items, create_scan_session


def _today_utc_calendar() -> date:
    """Authoritative comparator date aligned with SQLite tests (local date.today)."""

    return date.today()


@dataclass(frozen=True)
class _PhysicalIntakeProjectionRow:
    inventory_copy_id: int
    order_item_id: int
    order_id: int
    order_item_quantity: int
    owner_user_id: int | None
    primary_cover_image_id: int | None
    retailer: str
    source_type: str | None
    publisher: str
    title: str
    issue_number: str
    purchase_date: date | None
    release_date: date | None
    release_status: str
    order_status: str
    expected_ship_date: date | None
    received_at: datetime | None
    asset_state: str


def _physical_intake_rows(session: Session, *, owner_user_id: int | None) -> list[_PhysicalIntakeProjectionRow]:
    stmt = (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            OrderItem.id.label("order_item_id"),
            Order.id.label("order_id"),
            InventoryCopy.user_id.label("owner_user_id"),
            InventoryCopy.primary_cover_image_id.label("primary_cover_image_id"),
            OrderItem.quantity.label("order_item_quantity"),
            Order.retailer.label("retailer"),
            Order.source_type.label("source_type"),
            Publisher.name.label("publisher"),
            ComicTitle.name.label("title"),
            ComicIssue.issue_number.label("issue_number"),
            Order.order_date.label("purchase_date"),
            InventoryCopy.release_date.label("release_date"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.expected_ship_date.label("expected_ship_date"),
            InventoryCopy.received_at.label("received_at"),
            _asset_state_expression_labels().label("asset_state"),
        )
        .select_from(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
    )
    if owner_user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == owner_user_id)
    stmt = stmt.order_by(InventoryCopy.id.asc())
    rows = session.exec(stmt).all()
    return [
        _PhysicalIntakeProjectionRow(
            inventory_copy_id=int(r.inventory_copy_id),
            order_item_id=int(r.order_item_id),
            order_id=int(r.order_id),
            order_item_quantity=int(r.order_item_quantity),
            owner_user_id=int(r.owner_user_id) if r.owner_user_id is not None else None,
            primary_cover_image_id=int(r.primary_cover_image_id) if r.primary_cover_image_id is not None else None,
            retailer=str(r.retailer),
            source_type=str(r.source_type) if r.source_type is not None else None,
            publisher=str(r.publisher),
            title=str(r.title),
            issue_number=str(r.issue_number),
            purchase_date=r.purchase_date,
            release_date=r.release_date,
            release_status=str(r.release_status),
            order_status=str(r.order_status),
            expected_ship_date=r.expected_ship_date,
            received_at=r.received_at,
            asset_state=str(r.asset_state),
        )
        for r in rows
    ]


def _to_arrival_row(p: _PhysicalIntakeProjectionRow) -> OrderArrivalProjectionRow:
    return OrderArrivalProjectionRow(
        inventory_copy_id=p.inventory_copy_id,
        owner_user_id=p.owner_user_id,
        retailer=p.retailer,
        source_type=p.source_type,
        publisher=p.publisher,
        title=p.title,
        issue_number=p.issue_number,
        order_item_quantity=p.order_item_quantity,
        purchase_date=p.purchase_date,
        release_date=p.release_date,
        release_status=p.release_status,
        order_status=p.order_status,
        expected_ship_date=p.expected_ship_date,
        received_at=p.received_at,
        asset_state=p.asset_state,
    )


def _derive_cover_signals(
    session: Session,
    *,
    inv_map: dict[int, list],
    proj: _PhysicalIntakeProjectionRow,
) -> tuple[bool, bool]:
    covers = inv_map.get(proj.inventory_copy_id, [])
    primary = _pick_primary_cover(proj.primary_cover_image_id, covers)
    has_cover = len(covers) > 0
    primary_id = int(primary.id) if primary is not None and primary.id is not None else None
    ocr_row_map = (
        _latest_ocr_map(session, [primary_id]) if primary_id is not None else {}
    )
    ocr_row = ocr_row_map.get(primary_id) if primary_id is not None else None
    cover_processing_failed = primary is not None and getattr(primary, "processing_status", "") == "failed"
    ocr_complete = (
        primary_id is not None
        and not cover_processing_failed
        and ocr_row is not None
        and getattr(ocr_row, "processing_status", "") == "processed"
    )
    return has_cover, ocr_complete


def derive_physical_intake_state(
    proj: OrderArrivalProjectionRow,
    *,
    today: date,
    has_cover_scan: bool,
    ocr_complete_on_primary_cover: bool,
) -> PhysicalIntakeState:
    if proj.order_status == "cancelled":
        return "cancelled"

    if proj.order_status == "received" or proj.received_at is not None:
        if not has_cover_scan:
            return "received_pending_scan"
        if not ocr_complete_on_primary_cover:
            return "received_scanned"
        return "completed"

    if proj.asset_state == "preorder_not_released_yet":
        return "awaiting_release"

    if (
        proj.expected_ship_date is not None
        and proj.expected_ship_date < today
        and proj.order_status != "received"
        and proj.received_at is None
    ):
        return "intake_blocked"

    return "released_awaiting_receipt"


def _dashboard_buckets_from(
    *,
    classifications: list[OrderArrivalClassification],
    intake_state: PhysicalIntakeState,
    order_cancelled: bool,
) -> list[PhysicalIntakeDashboardBucket]:
    buckets: list[PhysicalIntakeDashboardBucket] = []
    if order_cancelled or intake_state == "cancelled":
        buckets.append("cancelled")
    if intake_state == "completed":
        buckets.append("completed")
    if intake_state == "received_pending_scan":
        buckets.append("received_pending_scan")

    lookup = classifications
    if "released_not_received" in lookup:
        buckets.append("released_not_received")
    if "overdue_expected_ship" in lookup:
        buckets.append("overdue_expected_ship")
    if "missing_release_date" in lookup:
        buckets.append("missing_release_date")
    if "missing_expected_ship_date" in lookup:
        buckets.append("missing_expected_ship_date")

    return sorted(dict.fromkeys(buckets))


def _build_item_reads(
    session: Session,
    *,
    owner_user_id: int | None,
    today: date,
    intake_state_filter: PhysicalIntakeState | None,
) -> list[PhysicalIntakeItemRead]:
    rows = _physical_intake_rows(session, owner_user_id=owner_user_id)
    if not rows:
        return []

    ids = [r.inventory_copy_id for r in rows]
    inv_map = _covers_by_inventory(session, ids)

    out: list[PhysicalIntakeItemRead] = []
    for proj in rows:
        arrival_row = _to_arrival_row(proj)
        classifications = derive_order_arrival_classifications(arrival_row, today=today)
        has_cover, ocr_primary = _derive_cover_signals(session, inv_map=inv_map, proj=proj)
        intake_state = derive_physical_intake_state(
            arrival_row,
            today=today,
            has_cover_scan=has_cover,
            ocr_complete_on_primary_cover=ocr_primary,
        )
        buckets = _dashboard_buckets_from(
            classifications=classifications,
            intake_state=intake_state,
            order_cancelled=arrival_row.order_status == "cancelled",
        )

        item = PhysicalIntakeItemRead(
            inventory_copy_id=proj.inventory_copy_id,
            order_item_id=proj.order_item_id,
            order_id=proj.order_id,
            intake_state=intake_state,
            retailer=proj.retailer,
            publisher=proj.publisher,
            title=proj.title,
            issue_number=proj.issue_number,
            purchase_date=proj.purchase_date,
            release_date=proj.release_date,
            release_status=proj.release_status,
            order_status=proj.order_status,
            asset_state=proj.asset_state,
            expected_ship_date=proj.expected_ship_date,
            received_at=proj.received_at,
            has_cover_scan=has_cover,
            ocr_complete_on_primary_cover=ocr_primary,
            dashboard_buckets=buckets,
            order_arrival_classifications=classifications,
        )

        if intake_state_filter is not None and item.intake_state != intake_state_filter:
            continue
        out.append(item)

    return out


def summarize_physical_intake_items(items: Iterable[PhysicalIntakeItemRead]) -> PhysicalIntakeSummaryCounts:
    c = PhysicalIntakeSummaryCounts()
    for row in items:
        cf = row.order_arrival_classifications
        if "released_not_received" in cf:
            c.released_not_received += 1
        if "overdue_expected_ship" in cf:
            c.overdue_expected_ship += 1
        if "missing_release_date" in cf:
            c.missing_release_date += 1
        if "missing_expected_ship_date" in cf:
            c.missing_expected_ship_date += 1

        match row.intake_state:
            case "awaiting_release":
                c.awaiting_release += 1
            case "released_awaiting_receipt":
                c.released_awaiting_receipt += 1
            case "received_pending_scan":
                c.received_pending_scan += 1
            case "received_scanned":
                c.received_scanned += 1
            case "intake_blocked":
                c.intake_blocked += 1
            case "cancelled":
                c.cancelled += 1
            case "completed":
                c.completed += 1

    return c


def list_physical_intake(
    session: Session,
    *,
    owner_user_id: int | None,
    intake_state_filter: PhysicalIntakeState | None,
    today: date | None = None,
) -> PhysicalIntakeListResponse:
    as_of = today or _today_utc_calendar()
    items = _build_item_reads(
        session,
        owner_user_id=owner_user_id,
        today=as_of,
        intake_state_filter=intake_state_filter,
    )
    return PhysicalIntakeListResponse(generated_as_of=as_of, items=items)


def build_physical_intake_summary(
    session: Session,
    *,
    owner_user_id: int | None,
    today: date | None = None,
) -> PhysicalIntakeSummaryResponse:
    as_of = today or _today_utc_calendar()
    items = _build_item_reads(
        session,
        owner_user_id=owner_user_id,
        today=as_of,
        intake_state_filter=None,
    )
    return PhysicalIntakeSummaryResponse(generated_as_of=as_of, counts=summarize_physical_intake_items(items))


def _physical_receive_skip_reason(copy: InventoryCopy) -> str | None:
    if copy.order_status == "cancelled":
        return "cancelled"
    if copy.hold_status == "sold":
        return "sold"
    if copy.order_status == "received":
        return None
    if copy.order_status not in {"ordered", "preordered", "shipped"}:
        return "invalid_order_status"
    return None


def mark_physical_received(
    session: Session,
    current_user: User,
    *,
    inventory_copy_id: int,
    payload: MarkInventoryReceivedPayload,
) -> InventoryRow:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    skip = _physical_receive_skip_reason(copy)
    if skip == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled inventory cannot be marked received")
    if skip == "sold":
        raise HTTPException(status_code=400, detail="Sold inventory cannot be marked received")
    if skip == "invalid_order_status":
        raise HTTPException(status_code=400, detail="Order line cannot be physically received")
    if copy.order_status == "received":
        return inventory_row_for_copy(session, current_user, inventory_copy_id)

    ts = payload.received_at if payload.received_at is not None else utc_now()

    return update_inventory_copy(
        session,
        current_user,
        inventory_copy_id,
        InventoryUpdate(received_at=ts, order_status="received"),
    )


def bulk_mark_physical_received(
    session: Session,
    current_user: User,
    *,
    payload: BulkMarkInventoryReceivedRequest,
) -> BulkMarkInventoryReceivedResponse:
    owner_id = int(current_user.id)  # type: ignore[arg-type]
    ts = payload.received_at if payload.received_at is not None else utc_now()

    uniq: list[int] = []
    seen: set[int] = set()
    for raw_id in payload.inventory_copy_ids:
        cid = int(raw_id)
        if cid not in seen:
            uniq.append(cid)
            seen.add(cid)

    copies_by_id: dict[int, InventoryCopy] = {}
    if uniq:
        rows = session.exec(
            select(InventoryCopy).where(
                InventoryCopy.id.in_(uniq),
                InventoryCopy.user_id == owner_id,
            )
        ).all()
        copies_by_id = {int(row.id): row for row in rows if row.id is not None}

    results: list[BulkMarkInventoryReceivedItemResult] = []
    marked_count = 0
    skipped_count = 0
    error_count = 0
    mutated = False

    for cid in uniq:
        copy = copies_by_id.get(cid)
        if copy is None:
            skipped_count += 1
            results.append(
                BulkMarkInventoryReceivedItemResult(
                    inventory_copy_id=cid,
                    outcome="skipped",
                    detail="not_found",
                )
            )
            continue

        skip = _physical_receive_skip_reason(copy)
        if skip in {"cancelled", "sold", "invalid_order_status"}:
            skipped_count += 1
            results.append(
                BulkMarkInventoryReceivedItemResult(
                    inventory_copy_id=cid,
                    outcome="skipped",
                    detail=skip,
                )
            )
            continue

        if copy.order_status == "received":
            marked_count += 1
            results.append(
                BulkMarkInventoryReceivedItemResult(
                    inventory_copy_id=cid,
                    outcome="marked",
                    detail="already_received",
                    row=inventory_row_for_copy(session, current_user, cid),
                )
            )
            continue

        copy.received_at = ts
        copy.order_status = "received"
        session.add(copy)
        mutated = True
        marked_count += 1
        results.append(
            BulkMarkInventoryReceivedItemResult(
                inventory_copy_id=cid,
                outcome="marked",
                row=None,
            )
        )

    if mutated:
        session.commit()

    hydrated: list[BulkMarkInventoryReceivedItemResult] = []
    for item in results:
        if item.outcome == "marked" and item.row is None:
            hydrated.append(
                item.model_copy(
                    update={
                        "row": inventory_row_for_copy(session, current_user, item.inventory_copy_id),
                    }
                )
            )
        else:
            hydrated.append(item)

    return BulkMarkInventoryReceivedResponse(
        marked_count=marked_count,
        skipped_count=skipped_count,
        error_count=error_count,
        results=hydrated,
    )


def create_physical_intake_scan_session(
    session: Session,
    current_user: User,
    payload: CreatePhysicalIntakeScanSessionPayload,
) -> ScanSessionDetailRead:
    owner_id = int(current_user.id)  # type: ignore[arg-type]
    uniq: list[int] = []
    seen: set[int] = set()
    for raw_id in payload.inventory_copy_ids:
        cid = int(raw_id)
        if cid not in seen:
            uniq.append(cid)
            seen.add(cid)

    validated: list[int] = []
    for cid in uniq:
        row = session.get(InventoryCopy, cid)
        if row is None or row.user_id != owner_id:
            raise HTTPException(status_code=400, detail="Inventory copy out of scope for receiving session")
        if row.order_status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot queue cancelled inventory in an intake receiving session")
        if row.order_status != "received":
            raise HTTPException(status_code=400, detail="Only received inventory can be queued for intake scan sessions")

        validated.append(cid)

    created = create_scan_session(
        session,
        owner_user_id=owner_id,
        payload=ScanSessionCreatePayload(session_type="intake_receiving"),
    )
    append_payload = ScanSessionItemsAppendPayload(
        items=[
            ScanSessionItemCreatePayload(
                inventory_copy_id=c,
                cover_image_id=None,
                source_filename=None,
                image_width=None,
                image_height=None,
                image_sha256=None,
            )
            for c in validated
        ],
    )

    return append_scan_session_items(
        session,
        owner_user_id=owner_id,
        session_id=int(created.id),
        payload=append_payload,
    )

