"""P80-02 mobile intake, storage assignment, and audit workflows."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models import InventoryCopy, Order, OrderItem, User
from app.models.p79_storage_audit import (
    AUDIT_COMPLETED,
    AUDIT_IN_PROGRESS,
    ENTRY_EXPECTED,
    ENTRY_MISSING,
    ENTRY_VERIFIED,
    P79StorageAuditEntry,
    P79StorageAuditSession,
)
from app.models.p80_mobile_operations import P80MobileAuditLink, P80MobileIntakeSession, utc_now
from app.models.storage_location import P79InventoryLocationAssignment, P79StorageBox, P79StorageSlot
from app.schemas.mobile_operations import (
    P80AuditCompleteRead,
    P80AuditScanRead,
    P80AuditStartRead,
    P80IntakeCompleteRead,
    P80IntakeScanResultRead,
    P80IntakeSessionRead,
    P80OperationsDashboardRead,
    P80StorageSuggestionRead,
)
from app.schemas.orders import OrderCreate, OrderItemCreate
from app.schemas.physical_intake import MarkInventoryReceivedPayload
from app.services.mobile_scan_platform_service import _BookIdentity, resolve_barcode_identification
from app.services.orders import create_order_for_user_in_transaction
from app.services.physical_intake import mark_physical_received
from app.services.storage_assignment_service import (
    StorageAssignmentError,
    assign_inventory_copy,
    build_location_path,
    suggest_next_slot_number,
)
from app.services.storage_audit_service import (
    StorageAuditError,
    complete_audit,
    create_audit_session,
    get_audit_detail,
    mark_verified,
    record_unexpected,
)
from app.services.storage_capacity import count_unassigned_copies, occupied_slots_for_box
from app.services.storage_copy_meta import copy_display_meta, section_for_slot
from app.services.storage_missing_detection import build_detection_summary

PENDING_ORDER_STATUSES = frozenset({"ordered", "preordered", "shipped"})


def _session_read(row: P80MobileIntakeSession) -> P80IntakeSessionRead:
    missing = max(0, int(row.expected_count) - int(row.received_count))
    return P80IntakeSessionRead(
        session_id=int(row.id or 0),
        intake_mode=row.intake_mode,
        order_id=row.order_id,
        status=row.status,
        expected_count=row.expected_count,
        scanned_count=row.scanned_count,
        received_count=row.received_count,
        missing_count=missing,
        duplicate_scan_count=row.duplicate_scan_count,
        unknown_scan_count=row.unknown_scan_count,
        scans=list(row.scans_json or []),
    )


def _get_intake_session(session: Session, *, owner_user_id: int, session_id: int) -> P80MobileIntakeSession:
    row = session.get(P80MobileIntakeSession, session_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Intake session not found.")
    return row


def _pending_copies_for_order(session: Session, *, owner_user_id: int, order_id: int) -> list[InventoryCopy]:
    copies = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.id == order_id)
        .where(Order.user_id == owner_user_id)
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(InventoryCopy.id.asc())
    ).all()
    return [c for c in copies if c.order_status in PENDING_ORDER_STATUSES]


def _expected_count_for_order(session: Session, *, owner_user_id: int, order_id: int) -> int:
    return len(_pending_copies_for_order(session, owner_user_id=owner_user_id, order_id=order_id))


def _match_copy_for_identity(
    session: Session,
    *,
    owner_user_id: int,
    order_id: int | None,
    identity: _BookIdentity,
    exclude_copy_ids: set[int],
) -> InventoryCopy | None:
    candidates: list[InventoryCopy] = []
    if order_id is not None:
        candidates = _pending_copies_for_order(session, owner_user_id=owner_user_id, order_id=order_id)
    else:
        candidates = list(
            session.exec(
                select(InventoryCopy)
                .where(InventoryCopy.user_id == owner_user_id)
                .where(col(InventoryCopy.order_status).in_(tuple(PENDING_ORDER_STATUSES)))
                .order_by(InventoryCopy.id.asc())
            ).all()
        )
    for copy in candidates:
        cid = int(copy.id or 0)
        if cid in exclude_copy_ids:
            continue
        meta = copy_display_meta(session, copy)
        if identity.variant_id is not None and int(copy.variant_id or 0) == identity.variant_id:
            return copy
        key = f"{identity.series_name}|{identity.issue_number}".lower()
        if key.strip("|") and f"{meta['series_name']}|{meta['issue_number']}".lower() == key:
            return copy
    return None


def _create_manual_intake_order(
    session: Session,
    *,
    current_user: User,
    identity: _BookIdentity,
) -> InventoryCopy:
    publisher = identity.publisher.strip() or "Unknown"
    series = identity.series_name.strip() or identity.title.strip() or "Unknown Series"
    issue = identity.issue_number.strip() or "1"
    payload = OrderCreate(
        retailer="Mobile Intake",
        order_date=date.today(),
        source_type="manual",
        shipping_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        items=[
            OrderItemCreate(
                title=series,
                publisher=publisher,
                issue_number=issue,
                cover_name=identity.variant_description or None,
                quantity=1,
                raw_item_price=Decimal("0"),
                order_status="shipped",
            )
        ],
    )
    response = create_order_for_user_in_transaction(session, current_user=current_user, payload=payload)
    copy = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == response.order_id)
        .where(InventoryCopy.user_id == int(current_user.id or 0))
        .order_by(InventoryCopy.id.desc())
    ).first()
    if copy is None:
        raise HTTPException(status_code=500, detail="Failed to create inventory copy.")
    return copy


def start_intake_session(
    session: Session,
    *,
    owner_user_id: int,
    intake_mode: str,
    order_id: int | None,
) -> P80IntakeSessionRead:
    mode = intake_mode.strip().upper()
    if mode not in {"ORDER", "PURCHASE", "MANUAL"}:
        raise HTTPException(status_code=422, detail="Invalid intake mode.")
    if mode in {"ORDER", "PURCHASE"} and order_id is None:
        raise HTTPException(status_code=422, detail="order_id is required for order intake.")
    if order_id is not None:
        order = session.get(Order, order_id)
        if order is None or order.user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="Order not found.")
    expected = _expected_count_for_order(session, owner_user_id=owner_user_id, order_id=order_id) if order_id else 0
    row = P80MobileIntakeSession(
        owner_user_id=owner_user_id,
        intake_mode=mode,
        order_id=order_id,
        status="IN_PROGRESS",
        expected_count=expected,
        scans_json=[],
        summary_json={},
    )
    session.add(row)
    session.flush()
    return _session_read(row)


def intake_scan(
    session: Session,
    *,
    current_user: User,
    session_id: int,
    barcode: str,
) -> P80IntakeScanResultRead:
    owner_user_id = int(current_user.id or 0)
    intake = _get_intake_session(session, owner_user_id=owner_user_id, session_id=session_id)
    if intake.status != "IN_PROGRESS":
        raise HTTPException(status_code=422, detail="Intake session is not active.")

    identity, confidence, _source, _storage, normalized = resolve_barcode_identification(
        session,
        owner_user_id=owner_user_id,
        raw_barcode=barcode,
    )
    scanned_ids = {int(s.get("inventory_copy_id") or 0) for s in (intake.scans_json or []) if s.get("inventory_copy_id")}

    if identity is None:
        intake.scanned_count += 1
        intake.unknown_scan_count += 1
        intake.scans_json = list(intake.scans_json or []) + [
            {"barcode": normalized, "status": "unknown", "confidence": confidence}
        ]
        session.add(intake)
        session.flush()
        return P80IntakeScanResultRead(
            session_id=session_id,
            session=_session_read(intake),
            scan_status="UNKNOWN",
            message="Could not identify book; manual review required.",
        )

    copy: InventoryCopy | None = None
    created = False
    duplicate = False
    if identity.representative_copy_id and int(identity.representative_copy_id) in scanned_ids:
        duplicate = True
        copy = session.get(InventoryCopy, int(identity.representative_copy_id))

    if not duplicate:
        copy = _match_copy_for_identity(
            session,
            owner_user_id=owner_user_id,
            order_id=intake.order_id,
            identity=identity,
            exclude_copy_ids=scanned_ids,
        )

    if copy is None and intake.intake_mode == "MANUAL":
        copy = _create_manual_intake_order(session, current_user=current_user, identity=identity)
        created = True
        intake.expected_count += 1

    if copy is None:
        intake.scanned_count += 1
        intake.unknown_scan_count += 1
        intake.scans_json = list(intake.scans_json or []) + [
            {
                "barcode": normalized,
                "status": "unmatched",
                "title": identity.title,
                "confidence": confidence,
            }
        ]
        session.add(intake)
        session.flush()
        return P80IntakeScanResultRead(
            session_id=session_id,
            session=_session_read(intake),
            scan_status="UNMATCHED",
            title=identity.title,
            message="No pending order line matched this scan.",
        )

    cid = int(copy.id or 0)
    if cid in scanned_ids:
        duplicate = True
        intake.duplicate_scan_count += 1
    else:
        if copy.order_status in PENDING_ORDER_STATUSES:
            mark_physical_received(
                session,
                current_user,
                inventory_copy_id=cid,
                payload=MarkInventoryReceivedPayload(),
            )
            intake.received_count += 1
        elif copy.order_status == "received":
            pass
        intake.scanned_count += 1

    meta = copy_display_meta(session, copy)
    intake.scans_json = list(intake.scans_json or []) + [
        {
            "barcode": normalized,
            "status": "duplicate" if duplicate else "received",
            "inventory_copy_id": cid,
            "title": meta["title"],
            "created_inventory": created,
        }
    ]
    session.add(intake)
    session.flush()
    return P80IntakeScanResultRead(
        session_id=session_id,
        session=_session_read(intake),
        scan_status="DUPLICATE" if duplicate else "RECEIVED",
        title=meta["title"],
        inventory_copy_id=cid,
        order_item_matched=intake.order_id is not None and not created,
        created_inventory=created,
        duplicate_scan=duplicate,
        message="Duplicate scan detected." if duplicate else "Marked received.",
    )


def complete_intake_session(
    session: Session,
    *,
    owner_user_id: int,
    session_id: int,
) -> P80IntakeCompleteRead:
    intake = _get_intake_session(session, owner_user_id=owner_user_id, session_id=session_id)
    intake.status = "COMPLETE"
    intake.completed_at = utc_now()
    missing = max(0, intake.expected_count - intake.received_count)
    intake.summary_json = {
        "missing_count": missing,
        "status_label": "COMPLETE" if missing == 0 else "PARTIAL",
    }
    session.add(intake)
    session.flush()
    label = str(intake.summary_json.get("status_label") or "COMPLETE")
    return P80IntakeCompleteRead(session=_session_read(intake), status_label=label)


def _series_score_in_box(session: Session, *, box_id: int, series_name: str) -> int:
    if not series_name:
        return 0
    slots = session.exec(select(P79StorageSlot).where(P79StorageSlot.box_id == box_id)).all()
    score = 0
    for slot in slots:
        assign = session.exec(
            select(P79InventoryLocationAssignment).where(
                P79InventoryLocationAssignment.storage_slot_id == int(slot.id or 0)
            )
        ).first()
        if assign is None:
            continue
        copy = session.get(InventoryCopy, assign.inventory_copy_id)
        if copy is None:
            continue
        meta = copy_display_meta(session, copy)
        if meta["series_name"].lower() == series_name.lower():
            score += 1
    return score


def suggest_storage(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    box_id: int | None = None,
) -> P80StorageSuggestionRead:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")
    meta = copy_display_meta(session, copy)
    boxes = session.exec(select(P79StorageBox).where(P79StorageBox.owner_user_id == owner_user_id)).all()
    reasons: list[str] = []
    chosen: P79StorageBox | None = None
    if box_id is not None:
        chosen = session.get(P79StorageBox, box_id)
        if chosen is None or chosen.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="Box not found.")
        reasons.append("User-selected box")
    else:
        ranked = sorted(
            boxes,
            key=lambda b: (
                -_series_score_in_box(session, box_id=int(b.id or 0), series_name=meta["series_name"]),
                occupied_slots_for_box(session, box_id=int(b.id or 0)),
            ),
        )
        for box in ranked:
            if occupied_slots_for_box(session, box_id=int(b.id or 0)) < int(box.capacity):
                chosen = box
                score = _series_score_in_box(session, box_id=int(box.id or 0), series_name=meta["series_name"])
                if score > 0:
                    reasons.append(f"Series grouping ({score} matching copies in box)")
                else:
                    reasons.append("Next available capacity")
                break
    if chosen is None:
        return P80StorageSuggestionRead(
            inventory_copy_id=inventory_copy_id,
            capacity_available=False,
            reasons=["No boxes with available capacity"],
        )
    bid = int(chosen.id or 0)
    slot = suggest_next_slot_number(session, box_id=bid)
    path_segments = build_location_path(session, owner_user_id=owner_user_id, shelf_location_id=chosen.shelf_location_id)
    path_text = " / ".join(s.name for s in path_segments) + f" / {chosen.name}"
    if slot is not None:
        path_text += f" / {section_for_slot(slot)} / Slot {slot}"
    return P80StorageSuggestionRead(
        inventory_copy_id=inventory_copy_id,
        recommended_box_id=bid,
        recommended_box_name=chosen.name,
        suggested_slot_number=slot,
        section_label=section_for_slot(slot) if slot else None,
        location_path_text=path_text,
        series_grouping_score=float(_series_score_in_box(session, box_id=bid, series_name=meta["series_name"])),
        capacity_available=slot is not None,
        reasons=reasons,
    )


def mobile_storage_assign(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    box_id: int,
    slot_number: int | None,
    use_suggested_slot: bool,
):
    from app.schemas.storage_foundation import P79StorageAssignmentRead

    try:
        assignment = assign_inventory_copy(
            session,
            owner_user_id=owner_user_id,
            inventory_copy_id=inventory_copy_id,
            box_id=box_id,
            slot_number=slot_number,
            use_suggested_slot=use_suggested_slot,
            assigned_by_user_id=owner_user_id,
        )
    except StorageAssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(assignment, P79StorageAssignmentRead):
        return assignment
    return P79StorageAssignmentRead.model_validate(assignment)


def start_mobile_audit(
    session: Session,
    *,
    owner_user_id: int,
    audit_name: str,
    scope_box_id: int | None,
    scope_location_id: int | None,
) -> P80AuditStartRead:
    try:
        audit = create_audit_session(
            session,
            owner_user_id=owner_user_id,
            audit_name=audit_name,
            scope_box_id=scope_box_id,
            scope_location_id=scope_location_id,
        )
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.add(
        P80MobileAuditLink(
            owner_user_id=owner_user_id,
            p79_audit_id=int(audit.id or 0),
            scope_box_id=scope_box_id,
            scope_location_id=scope_location_id,
        )
    )
    session.flush()
    return P80AuditStartRead(
        audit_id=int(audit.id or 0),
        audit_name=audit.audit_name,
        expected_count=int(audit.expected_count or 0),
        scope_box_id=scope_box_id,
        scope_location_id=scope_location_id,
    )


def _resolve_copy_id_from_barcode(
    session: Session,
    *,
    owner_user_id: int,
    barcode: str,
) -> tuple[int | None, str | None]:
    raw = barcode.strip()
    if raw.isdigit():
        cid = int(raw)
        copy = session.get(InventoryCopy, cid)
        if copy is not None and copy.user_id == owner_user_id:
            meta = copy_display_meta(session, copy)
            return cid, meta["title"]
    identity, _conf, _src, _stor, _norm = resolve_barcode_identification(
        session, owner_user_id=owner_user_id, raw_barcode=raw
    )
    if identity is None:
        return None, None
    if identity.representative_copy_id:
        copy = session.get(InventoryCopy, identity.representative_copy_id)
        if copy is not None and copy.user_id == owner_user_id:
            return int(copy.id or 0), identity.title
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    key = f"{identity.series_name}|{identity.issue_number}".lower()
    for copy in copies:
        meta = copy_display_meta(session, copy)
        if f"{meta['series_name']}|{meta['issue_number']}".lower() == key:
            return int(copy.id or 0), meta["title"]
    return None, identity.title


def audit_scan(
    session: Session,
    *,
    owner_user_id: int,
    audit_id: int,
    barcode: str,
) -> P80AuditScanRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Audit not found.")
    if audit.status != AUDIT_IN_PROGRESS:
        raise HTTPException(status_code=422, detail="Audit is not in progress.")

    copy_id, title = _resolve_copy_id_from_barcode(session, owner_user_id=owner_user_id, barcode=barcode)
    if copy_id is None:
        return P80AuditScanRead(
            audit_id=audit_id,
            outcome="UNKNOWN",
            message="Could not resolve inventory from scan.",
        )

    entry = session.exec(
        select(P79StorageAuditEntry)
        .where(P79StorageAuditEntry.audit_session_id == audit_id)
        .where(P79StorageAuditEntry.inventory_copy_id == copy_id)
    ).first()
    if entry is not None:
        entry.entry_status = ENTRY_VERIFIED
        entry.updated_at = utc_now()
        session.add(entry)
        session.commit()
        detail = get_audit_detail(session, owner_user_id=owner_user_id, audit_id=audit_id)
        return P80AuditScanRead(
            audit_id=audit_id,
            outcome="VERIFIED",
            inventory_copy_id=copy_id,
            entry_id=int(entry.id or 0),
            title=title,
            verified_count=detail.session.verified_count,
            unexpected_count=detail.session.unexpected_count,
            message="Book verified in audit scope.",
        )

    scope_box_id = audit.scope_box_id
    if scope_box_id is not None:
        try:
            detail = record_unexpected(
                session,
                owner_user_id=owner_user_id,
                audit_id=audit_id,
                inventory_copy_id=copy_id,
                storage_box_id=int(scope_box_id),
                notes="Mobile audit scan",
                move_to_box=False,
            )
        except StorageAuditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return P80AuditScanRead(
            audit_id=audit_id,
            outcome="UNEXPECTED",
            inventory_copy_id=copy_id,
            title=title,
            verified_count=detail.session.verified_count,
            unexpected_count=detail.session.unexpected_count,
            message="Book not expected in this audit scope.",
        )

    raise HTTPException(status_code=422, detail="No matching audit entry for scan.")


def complete_mobile_audit(
    session: Session,
    *,
    owner_user_id: int,
    audit_id: int,
) -> P80AuditCompleteRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Audit not found.")
    entries = session.exec(
        select(P79StorageAuditEntry).where(P79StorageAuditEntry.audit_session_id == audit_id)
    ).all()
    for entry in entries:
        if entry.entry_status == ENTRY_EXPECTED:
            entry.entry_status = ENTRY_MISSING
            entry.updated_at = utc_now()
            session.add(entry)
    session.flush()
    try:
        detail = complete_audit(session, owner_user_id=owner_user_id, audit_id=audit_id)
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    det = build_detection_summary(session, owner_user_id=owner_user_id)
    expected = max(1, int(detail.session.expected_count or 0))
    accuracy = round((detail.session.verified_count / expected) * 100.0, 1)
    return P80AuditCompleteRead(
        audit_id=audit_id,
        status=detail.session.status,
        verified_count=detail.session.verified_count,
        missing_count=detail.session.missing_count,
        unexpected_count=detail.session.unexpected_count,
        duplicate_assignments=det.duplicate_assignments,
        audit_accuracy_pct=accuracy,
    )


def get_mobile_audit(session: Session, *, owner_user_id: int, audit_id: int):
    from app.schemas.mobile_operations import P80MobileAuditDetailRead

    try:
        detail = get_audit_detail(session, owner_user_id=owner_user_id, audit_id=audit_id)
    except StorageAuditError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    expected = max(1, detail.session.expected_count)
    accuracy = round((detail.session.verified_count / expected) * 100.0, 1)
    dumped = detail.model_dump(mode="json")
    return P80MobileAuditDetailRead(
        session=dumped["session"],
        entries=dumped["entries"],
        detection_summary=dumped["detection_summary"],
        audit_accuracy_pct=accuracy,
    )


def build_operations_dashboard(session: Session, *, owner_user_id: int) -> P80OperationsDashboardRead:
    today = date.today()
    week_start = today - timedelta(days=7)
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    received_today = 0
    received_week = 0
    pending = 0
    assigned_today = 0
    for copy in copies:
        if copy.order_status in PENDING_ORDER_STATUSES:
            pending += 1
        if copy.received_at is not None:
            recv_date = copy.received_at.date()
            if recv_date == today:
                received_today += 1
            if recv_date >= week_start:
                received_week += 1

    assigns = session.exec(
        select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
    ).all()
    for assign in assigns:
        at = assign.assigned_at
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at >= today_start:
            assigned_today += 1

    open_audits = len(
        session.exec(
            select(P79StorageAuditSession)
            .where(P79StorageAuditSession.owner_user_id == owner_user_id)
            .where(P79StorageAuditSession.status == AUDIT_IN_PROGRESS)
        ).all()
    )
    completed = session.exec(
        select(P79StorageAuditSession)
        .where(P79StorageAuditSession.owner_user_id == owner_user_id)
        .where(P79StorageAuditSession.status == AUDIT_COMPLETED)
        .order_by(P79StorageAuditSession.completed_at.desc())
    ).all()
    accuracies: list[float] = []
    for row in completed[:10]:
        expected = max(1, int(row.expected_count or 0))
        accuracies.append((int(row.verified_count or 0) / expected) * 100.0)
    avg_accuracy = round(sum(accuracies) / len(accuracies), 1) if accuracies else 0.0

    return P80OperationsDashboardRead(
        intake_received_today=received_today,
        intake_received_this_week=received_week,
        intake_pending_receipts=pending,
        storage_assigned_today=assigned_today,
        storage_unassigned_inventory=count_unassigned_copies(session, owner_user_id=owner_user_id),
        audit_open_sessions=open_audits,
        audit_recent_completed=len(completed[:5]),
        audit_average_accuracy_pct=avg_accuracy,
        generated_at=now,
    )
