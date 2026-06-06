"""P79-03 storage analytics, utilization, forecast, and snapshots."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.p79_storage_audit import (
    AUDIT_COMPLETED,
    AUDIT_IN_PROGRESS,
    ENTRY_MISSING,
    ENTRY_MOVED,
    ENTRY_UNEXPECTED,
    ENTRY_VERIFIED,
    P79StorageAuditEntry,
    P79StorageAuditSession,
)
from app.models.p79_storage_analytics import (
    P79StorageAnalyticsSnapshot,
    P79StorageAuditPerformanceSnapshot,
    P79StorageHealthSnapshot,
    P79StorageUtilizationSnapshot,
)
from app.models.p72_grading_operations import P72GradingQueueEntry
from app.models.storage_location import (
    P79_KIND_LOCATION,
    P79_KIND_RACK,
    P79_KIND_ROOM,
    P79_KIND_SHELF,
    P79InventoryLocationAssignment,
    P79StorageBox,
    P79StorageLocation,
)
from app.schemas.storage_analytics import (
    P79StorageAnalyticsDashboardRead,
    P79StorageAnalyticsRead,
    P79StorageAuditAnalyticsRead,
    P79StorageHealthRead,
    P79StorageUtilizationResponse,
    P79UnassignedInventoryResponse,
    P79UnassignedInventoryRowRead,
    P79UtilizationRowRead,
)
from app.models.p79_storage_audit import ENTRY_EXPECTED
from app.services.storage_capacity import (
    _descendant_shelf_ids,
    _pct,
    aggregate_utilization,
    count_unassigned_copies,
    location_tree_metrics,
    occupied_slots_for_box,
)
from app.services.storage_copy_meta import copy_display_meta
from app.services.storage_health_score import HIGH_VALUE_FMV, compute_storage_health_score
from app.services.storage_missing_detection import build_detection_summary


def _box_category(name: str) -> str:
    token = name.strip().upper().replace(" ", "-")
    if token.startswith("SPEC"):
        return "SPEC"
    if token.startswith("SALE"):
        return "SALE"
    return "STANDARD"


def _forecast_risk(util_pct: float, months_until_full: float | None) -> str:
    if util_pct >= 100:
        return "OVER_CAPACITY"
    if util_pct >= 95 or (months_until_full is not None and months_until_full < 1):
        return "AT_CAPACITY"
    if util_pct >= 80 or (months_until_full is not None and months_until_full < 6):
        return "WATCH"
    return "LOW_RISK"


def _copy_created_utc(copy: InventoryCopy) -> datetime | None:
    if not copy.created_at:
        return None
    ts = copy.created_at
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _monthly_additions_estimate(session: Session, *, owner_user_id: int) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=90)
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    recent = [c for c in copies if (ts := _copy_created_utc(c)) is not None and ts >= since]
    if not recent:
        return max(1.0, len(copies) / 12.0) if copies else 1.0
    return max(1.0, len(recent) / 3.0)


def compute_core_analytics(session: Session, *, owner_user_id: int) -> dict:
    util = aggregate_utilization(session, owner_user_id=owner_user_id)
    locations = session.exec(select(P79StorageLocation).where(P79StorageLocation.owner_user_id == owner_user_id)).all()
    boxes = session.exec(select(P79StorageBox).where(P79StorageBox.owner_user_id == owner_user_id)).all()
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    assigned = len(
        session.exec(
            select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        ).all()
    )
    over_cap = sum(
        1 for b in boxes if occupied_slots_for_box(session, box_id=int(b.id or 0)) > int(b.capacity)
    )
    inactive = sum(1 for loc in locations if not loc.is_active)
    monthly = _monthly_additions_estimate(session, owner_user_id=owner_user_id)
    available = int(util["available_slots"])
    months = round(available / monthly, 1) if monthly > 0 else None
    util_pct = float(util["box_utilization_pct"])
    return {
        "total_locations": len(locations),
        "total_boxes": len(boxes),
        "total_capacity": int(util["total_slot_capacity"]),
        "used_capacity": int(util["occupied_slots"]),
        "available_capacity": available,
        "utilization_pct": util_pct,
        "assigned_inventory_count": assigned,
        "unassigned_inventory_count": count_unassigned_copies(session, owner_user_id=owner_user_id),
        "over_capacity_boxes": over_cap,
        "inactive_locations": inactive,
        "forecast_risk": _forecast_risk(util_pct, months),
        "estimated_months_until_full": months,
        "total_copies": len(copies),
    }


def build_utilization_rows(session: Session, *, owner_user_id: int) -> list[P79UtilizationRowRead]:
    rows: list[P79UtilizationRowRead] = []
    locations = session.exec(select(P79StorageLocation).where(P79StorageLocation.owner_user_id == owner_user_id)).all()
    for kind in (P79_KIND_ROOM, P79_KIND_RACK, P79_KIND_SHELF, P79_KIND_LOCATION):
        for loc in locations:
            if loc.location_kind != kind:
                continue
            used, _, util = location_tree_metrics(
                session, owner_user_id=owner_user_id, location_id=int(loc.id or 0)
            )
            shelf_ids = _descendant_shelf_ids(session, owner_user_id=owner_user_id, location_id=int(loc.id or 0))
            if kind == P79_KIND_SHELF:
                shelf_ids = [int(loc.id or 0)]
            cap = 0
            if shelf_ids:
                box_list = session.exec(
                    select(P79StorageBox).where(P79StorageBox.shelf_location_id.in_(shelf_ids))
                ).all()
                cap = sum(int(b.capacity) for b in box_list)
            if cap == 0 and loc.capacity:
                cap = int(loc.capacity)
            rows.append(
                P79UtilizationRowRead(
                    group_kind=kind,
                    group_key=loc.name,
                    entity_id=int(loc.id or 0),
                    utilization_pct=util,
                    used_capacity=used,
                    total_capacity=cap,
                )
            )

    boxes = session.exec(select(P79StorageBox).where(P79StorageBox.owner_user_id == owner_user_id)).all()
    type_used: dict[str, int] = {}
    type_cap: dict[str, int] = {}
    for box in boxes:
        used = occupied_slots_for_box(session, box_id=int(box.id or 0))
        cap = int(box.capacity)
        rows.append(
            P79UtilizationRowRead(
                group_kind="BOX",
                group_key=box.name,
                entity_id=int(box.id or 0),
                utilization_pct=_pct(used, cap),
                used_capacity=used,
                total_capacity=cap,
            )
        )
        cat = _box_category(box.name)
        type_used[cat] = type_used.get(cat, 0) + used
        type_cap[cat] = type_cap.get(cat, 0) + cap
    for cat, used in type_used.items():
        cap = type_cap[cat]
        rows.append(
            P79UtilizationRowRead(
                group_kind="BOX_TYPE",
                group_key=cat,
                entity_id=None,
                utilization_pct=_pct(used, cap),
                used_capacity=used,
                total_capacity=cap,
            )
        )
    return rows


def build_audit_analytics(session: Session, *, owner_user_id: int) -> dict:
    sessions = session.exec(
        select(P79StorageAuditSession).where(P79StorageAuditSession.owner_user_id == owner_user_id)
    ).all()
    started = len(sessions)
    completed = sum(1 for s in sessions if s.status == AUDIT_COMPLETED)
    missing = unexpected = moved = verified = expected = 0
    for aud in sessions:
        entries = session.exec(
            select(P79StorageAuditEntry).where(P79StorageAuditEntry.audit_session_id == int(aud.id or 0))
        ).all()
        for e in entries:
            if e.entry_status == ENTRY_VERIFIED:
                verified += 1
            if e.entry_status == ENTRY_MISSING:
                missing += 1
            if e.entry_status == ENTRY_UNEXPECTED:
                unexpected += 1
            if e.entry_status == ENTRY_MOVED:
                moved += 1
            if e.entry_status in (ENTRY_VERIFIED, ENTRY_MISSING, ENTRY_EXPECTED):
                expected += 1
    ver_rate = round(verified / max(1, verified + missing) * 100.0, 1)
    accuracy = round(verified / max(1, expected) * 100.0, 1) if expected else 100.0
    det = build_detection_summary(session, owner_user_id=owner_user_id)
    return {
        "audits_started": started,
        "audits_completed": completed,
        "average_verification_rate_pct": ver_rate,
        "missing_books_found": missing,
        "unexpected_books_found": unexpected + moved,
        "duplicate_assignments_found": det.duplicate_assignments,
        "moved_books": moved,
        "audit_accuracy_rate_pct": accuracy,
    }


def build_unassigned_dashboard(session: Session, *, owner_user_id: int, limit: int = 50) -> P79UnassignedInventoryResponse:
    assigned_ids = {
        int(a.inventory_copy_id)
        for a in session.exec(
            select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        ).all()
    }
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    grading_ids = {
        int(r.inventory_copy_id)
        for r in session.exec(
            select(P72GradingQueueEntry).where(P72GradingQueueEntry.owner_user_id == owner_user_id)
        ).all()
    }
    rows: list[P79UnassignedInventoryRowRead] = []
    in_hand = graded = sell_q = hv = 0
    for copy in copies:
        cid = int(copy.id or 0)
        if cid in assigned_ids:
            continue
        meta = copy_display_meta(session, copy)
        in_hand_flag = copy.received_at is not None or copy.order_status in {"received", "in_hand"}
        graded_flag = copy.grade_status not in {"raw", "unknown"} or cid in grading_ids
        sell_flag = copy.hold_status == "sell"
        fmv = copy.current_fmv
        hv_flag = fmv is not None and float(fmv) >= HIGH_VALUE_FMV
        if in_hand_flag:
            in_hand += 1
        if graded_flag:
            graded += 1
        if sell_flag:
            sell_q += 1
        if hv_flag:
            hv += 1
        rows.append(
            P79UnassignedInventoryRowRead(
                inventory_copy_id=cid,
                title=meta["title"],
                in_hand=in_hand_flag,
                graded=graded_flag,
                sell_queue=sell_flag,
                high_value=hv_flag,
                estimated_fmv=fmv,
            )
        )
    rows.sort(key=lambda r: (not r.high_value, r.inventory_copy_id))
    return P79UnassignedInventoryResponse(
        total_unassigned=len(rows),
        in_hand_unassigned=in_hand,
        graded_unassigned=graded,
        sell_queue_unassigned=sell_q,
        high_value_unassigned=hv,
        items=rows[:limit],
    )


def persist_storage_analytics(session: Session, *, owner_user_id: int) -> P79StorageAnalyticsSnapshot:
    core = compute_core_analytics(session, owner_user_id=owner_user_id)
    util_rows = build_utilization_rows(session, owner_user_id=owner_user_id)
    audit = build_audit_analytics(session, owner_user_id=owner_user_id)
    unassigned = build_unassigned_dashboard(session, owner_user_id=owner_user_id)
    det = build_detection_summary(session, owner_user_id=owner_user_id)

    health_score, health_status, factors = compute_storage_health_score(
        total_copies=core["total_copies"],
        assigned_count=core["assigned_inventory_count"],
        audit_accuracy_pct=audit["audit_accuracy_rate_pct"],
        over_capacity_boxes=core["over_capacity_boxes"],
        high_value_unassigned=unassigned.high_value_unassigned,
        duplicate_assignments=det.duplicate_assignments,
        missing_books=audit["missing_books_found"],
    )

    snap = P79StorageAnalyticsSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=date.today(),
        total_locations=core["total_locations"],
        total_boxes=core["total_boxes"],
        total_capacity=core["total_capacity"],
        used_capacity=core["used_capacity"],
        available_capacity=core["available_capacity"],
        utilization_pct=core["utilization_pct"],
        assigned_inventory_count=core["assigned_inventory_count"],
        unassigned_inventory_count=core["unassigned_inventory_count"],
        over_capacity_boxes=core["over_capacity_boxes"],
        inactive_locations=core["inactive_locations"],
        forecast_risk=core["forecast_risk"],
        estimated_months_until_full=core["estimated_months_until_full"],
        summary_json={"audit": audit, "health_status": health_status},
    )
    session.add(snap)
    session.flush()
    sid = int(snap.id or 0)

    for row in util_rows:
        session.add(
            P79StorageUtilizationSnapshot(
                owner_user_id=owner_user_id,
                analytics_snapshot_id=sid,
                group_kind=row.group_kind,
                group_key=row.group_key,
                entity_id=row.entity_id,
                utilization_pct=row.utilization_pct,
                used_capacity=row.used_capacity,
                total_capacity=row.total_capacity,
            )
        )
    session.add(
        P79StorageAuditPerformanceSnapshot(
            owner_user_id=owner_user_id,
            analytics_snapshot_id=sid,
            audits_started=audit["audits_started"],
            audits_completed=audit["audits_completed"],
            average_verification_rate_pct=audit["average_verification_rate_pct"],
            missing_books_found=audit["missing_books_found"],
            unexpected_books_found=audit["unexpected_books_found"],
            duplicate_assignments_found=audit["duplicate_assignments_found"],
            moved_books=audit["moved_books"],
            audit_accuracy_rate_pct=audit["audit_accuracy_rate_pct"],
        )
    )
    session.add(
        P79StorageHealthSnapshot(
            owner_user_id=owner_user_id,
            analytics_snapshot_id=sid,
            health_score=health_score,
            health_status=health_status,
            factors_json=factors,
        )
    )
    session.commit()
    session.refresh(snap)
    return snap


def build_analytics_read(session: Session, *, owner_user_id: int) -> P79StorageAnalyticsRead:
    snap = persist_storage_analytics(session, owner_user_id=owner_user_id)
    return P79StorageAnalyticsRead(
        snapshot_id=int(snap.id or 0),
        generated_at=snap.generated_at,
        total_locations=snap.total_locations,
        total_boxes=snap.total_boxes,
        total_capacity=snap.total_capacity,
        used_capacity=snap.used_capacity,
        available_capacity=snap.available_capacity,
        utilization_pct=snap.utilization_pct,
        assigned_inventory_count=snap.assigned_inventory_count,
        unassigned_inventory_count=snap.unassigned_inventory_count,
        over_capacity_boxes=snap.over_capacity_boxes,
        inactive_locations=snap.inactive_locations,
        forecast_risk=snap.forecast_risk,
        estimated_months_until_full=snap.estimated_months_until_full,
    )


def build_analytics_dashboard(session: Session, *, owner_user_id: int) -> P79StorageAnalyticsDashboardRead:
    snap = persist_storage_analytics(session, owner_user_id=owner_user_id)
    sid = int(snap.id or 0)
    util_rows = build_utilization_rows(session, owner_user_id=owner_user_id)
    audit = build_audit_analytics(session, owner_user_id=owner_user_id)
    unassigned = build_unassigned_dashboard(session, owner_user_id=owner_user_id)
    health_row = session.exec(
        select(P79StorageHealthSnapshot).where(P79StorageHealthSnapshot.analytics_snapshot_id == sid)
    ).first()
    health = P79StorageHealthRead(
        snapshot_id=sid,
        health_score=health_row.health_score if health_row else 0,
        health_status=health_row.health_status if health_row else "WATCH",
        factors=health_row.factors_json if health_row else {},
    )
    over_alerts = [r for r in util_rows if r.group_kind == "BOX" and r.utilization_pct >= 95.0]
    return P79StorageAnalyticsDashboardRead(
        snapshot_id=sid,
        generated_at=snap.generated_at,
        analytics=P79StorageAnalyticsRead(
            snapshot_id=sid,
            generated_at=snap.generated_at,
            total_locations=snap.total_locations,
            total_boxes=snap.total_boxes,
            total_capacity=snap.total_capacity,
            used_capacity=snap.used_capacity,
            available_capacity=snap.available_capacity,
            utilization_pct=snap.utilization_pct,
            assigned_inventory_count=snap.assigned_inventory_count,
            unassigned_inventory_count=snap.unassigned_inventory_count,
            over_capacity_boxes=snap.over_capacity_boxes,
            inactive_locations=snap.inactive_locations,
            forecast_risk=snap.forecast_risk,
            estimated_months_until_full=snap.estimated_months_until_full,
        ),
        health=health,
        utilization=sorted(util_rows, key=lambda r: (-r.utilization_pct, r.group_key))[:24],
        audit_analytics=P79StorageAuditAnalyticsRead(snapshot_id=sid, **audit),
        unassigned=unassigned,
        over_capacity_alerts=over_alerts,
        certification_status="APPROVED_FOR_PRODUCTION",
    )


def build_utilization_response(session: Session, *, owner_user_id: int) -> P79StorageUtilizationResponse:
    snap = persist_storage_analytics(session, owner_user_id=owner_user_id)
    return P79StorageUtilizationResponse(
        snapshot_id=int(snap.id or 0),
        items=build_utilization_rows(session, owner_user_id=owner_user_id),
    )


def build_audit_analytics_read(session: Session, *, owner_user_id: int) -> P79StorageAuditAnalyticsRead:
    snap = persist_storage_analytics(session, owner_user_id=owner_user_id)
    audit = build_audit_analytics(session, owner_user_id=owner_user_id)
    return P79StorageAuditAnalyticsRead(snapshot_id=int(snap.id or 0), **audit)


def build_health_read(session: Session, *, owner_user_id: int) -> P79StorageHealthRead:
    snap = persist_storage_analytics(session, owner_user_id=owner_user_id)
    row = session.exec(
        select(P79StorageHealthSnapshot).where(
            P79StorageHealthSnapshot.analytics_snapshot_id == int(snap.id or 0)
        )
    ).first()
    assert row is not None
    return P79StorageHealthRead(
        snapshot_id=int(snap.id or 0),
        health_score=row.health_score,
        health_status=row.health_status,
        factors=row.factors_json,
    )
