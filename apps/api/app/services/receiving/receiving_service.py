from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from PIL import Image

from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    Order,
    OrderItem,
    Publisher,
    Variant,
)
from app.models.receiving import (
    ReceivingSession,
    ReceivingSessionItem,
    RecognitionCorrectionEvent,
    utc_now,
)
from app.services.cover_images import sha256_raw_bytes
from app.services.recognition.catalog_matcher import load_catalog_issue_identity
from app.services.receiving_live_capture_service import (
    normalize_live_capture_source,
    should_suppress_duplicate_capture,
    update_live_capture_stats,
)
from app.services.orders import (
    allocate_by_subtotal,
    build_order_item_metadata_identity_key,
    get_or_create_issue,
    get_or_create_publisher,
    get_or_create_title,
    get_or_create_variant,
    resolve_order_item_canonical_series,
    quantize_money,
    sync_canonical_creators_for_order_item,
)
from app.schemas.receiving import (
    ReceivingActionResponse,
    ReceivingCompletionSummaryRead,
    ReceivingConfirmPayload,
    ReceivingCorrectionPayload,
    ReceivingPurchaseAssignmentPayload,
    ReceivingSessionCreatePayload,
    ReceivingSessionDetailRead,
    ReceivingSessionItemRead,
    ReceivingSessionSummaryRead,
    ReceivingSkipPayload,
    ReceivingUploadResponse,
)
from app.services.recognition.recognition_service import identify_comic_cover_read

LOGGER = logging.getLogger(__name__)

RECEIVING_ITEM_SEQUENCE_CONSTRAINT = "uq_receiving_session_item_sequence_idx"
MAX_SEQUENCE_INDEX_RETRIES = 3

QUEUE_BUCKETS = ("VERIFIED", "REVIEW", "UNKNOWN")
FINAL_STATUSES = {"CONFIRMED", "SKIPPED"}


class _ReceivingMetrics:
    def __init__(self) -> None:
        self.receiving_sessions_created = 0
        self.items_uploaded = 0
        self.items_confirmed = 0
        self.items_reviewed = 0
        self.items_unknown = 0
        self.items_skipped = 0
        self.receiving_sessions_completed = 0
        self.inventory_created_from_receiving = 0
        self.allocation_method_usage: Counter[str] = Counter()
        self.source_type_usage: Counter[str] = Counter()
        self.capture_source_usage: Counter[str] = Counter()
        self.live_capture_frames_received = 0
        self.stable_frames_accepted = 0
        self.duplicate_frames_suppressed = 0
        self.recognition_latency_total_ms = 0
        self.recognition_latency_samples = 0

    def snapshot(self) -> dict[str, float | int]:
        total = self.items_confirmed + self.items_reviewed + self.items_unknown
        handled_total = self.items_confirmed + self.items_reviewed + self.items_unknown + self.items_skipped
        confirmation_rate = self.items_confirmed / total if total else 0.0
        review_rate = self.items_reviewed / total if total else 0.0
        skip_rate = self.items_skipped / handled_total if handled_total else 0.0
        average_recognition_time = (
            self.recognition_latency_total_ms / self.recognition_latency_samples if self.recognition_latency_samples else 0.0
        )
        return {
            "receiving_sessions_created": self.receiving_sessions_created,
            "items_uploaded": self.items_uploaded,
            "items_confirmed": self.items_confirmed,
            "items_reviewed": self.items_reviewed,
            "items_unknown": self.items_unknown,
            "items_skipped": self.items_skipped,
            "receiving_sessions_completed": self.receiving_sessions_completed,
            "inventory_created_from_receiving": self.inventory_created_from_receiving,
            "confirmation_rate": round(confirmation_rate, 6),
            "confirm_rate": round(confirmation_rate, 6),
            "review_rate": round(review_rate, 6),
            "skip_rate": round(skip_rate, 6),
            "average_recognition_time": round(average_recognition_time, 2),
            "allocation_method_usage": dict(self.allocation_method_usage),
            "source_type_usage": dict(self.source_type_usage),
            "capture_source_usage": dict(self.capture_source_usage),
            "live_capture_frames_received": self.live_capture_frames_received,
            "stable_frames_accepted": self.stable_frames_accepted,
            "duplicate_frames_suppressed": self.duplicate_frames_suppressed,
        }


_METRICS = _ReceivingMetrics()
_METRICS_LOCK = threading.Lock()


def receiving_metrics_snapshot() -> dict[str, float | int]:
    with _METRICS_LOCK:
        return _METRICS.snapshot()


def _touch(row: ReceivingSession | ReceivingSessionItem) -> None:
    row.updated_at = utc_now()


def _touch_session(row: ReceivingSession) -> None:
    row.updated_at = utc_now()


def _increment_metrics(
    *,
    created: int = 0,
    uploaded: int = 0,
    confirmed: int = 0,
    reviewed: int = 0,
    unknown: int = 0,
    skipped: int = 0,
    completed: int = 0,
    inventory_created: int = 0,
    allocation_method: str | None = None,
    source_type: str | None = None,
    capture_source: str | None = None,
    live_capture_frames: int = 0,
    stable_frames: int = 0,
    duplicate_suppressed: int = 0,
    recognition_latency_ms: int | None = None,
) -> None:
    with _METRICS_LOCK:
        _METRICS.receiving_sessions_created += created
        _METRICS.items_uploaded += uploaded
        _METRICS.items_confirmed += confirmed
        _METRICS.items_reviewed += reviewed
        _METRICS.items_unknown += unknown
        _METRICS.items_skipped += skipped
        _METRICS.receiving_sessions_completed += completed
        _METRICS.inventory_created_from_receiving += inventory_created
        if allocation_method:
            _METRICS.allocation_method_usage[allocation_method] += 1
        if source_type:
            _METRICS.source_type_usage[source_type] += 1
        if capture_source:
            _METRICS.capture_source_usage[capture_source] += 1
        _METRICS.live_capture_frames_received += live_capture_frames
        _METRICS.stable_frames_accepted += stable_frames
        _METRICS.duplicate_frames_suppressed += duplicate_suppressed
        if recognition_latency_ms is not None:
            _METRICS.recognition_latency_total_ms += recognition_latency_ms
            _METRICS.recognition_latency_samples += 1


def _require_owner(session: Session, *, owner_user_id: int, receiving_session_id: int) -> ReceivingSession:
    row = session.get(ReceivingSession, receiving_session_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiving session not found")
    return row


def _sorted_items(rows: list[ReceivingSessionItem]) -> list[ReceivingSessionItem]:
    return sorted(rows, key=lambda row: (row.sequence_index, row.id or 0))


def _coerce_json_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _coerce_json_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _session_summary(row: ReceivingSession) -> ReceivingSessionSummaryRead:
    payload = {
        **row.model_dump(),
        "capture_source": normalize_live_capture_source(row.capture_source),
        "allocation_details_json": _coerce_json_dict(row.allocation_details_json),
        "live_capture_stats_json": _coerce_json_dict(row.live_capture_stats_json),
    }
    return ReceivingSessionSummaryRead.model_validate(payload)


def _item_to_read(row: ReceivingSessionItem) -> ReceivingSessionItemRead:
    if row.id is None:
        raise ValueError("Receiving session item is missing a primary key")
    latency = row.recognition_latency_ms
    if latency is not None and not isinstance(latency, int):
        latency = int(latency)
    confidence = row.recognition_confidence
    if confidence is not None:
        confidence = float(confidence)
    payload = {
        **row.model_dump(),
        "capture_source": normalize_live_capture_source(row.capture_source),
        "recognition_confidence": confidence,
        "recognition_latency_ms": latency,
        "recognition_snapshot_json": _coerce_json_dict(row.recognition_snapshot_json),
        "candidate_snapshot_json": _coerce_json_list(row.candidate_snapshot_json),
        "capture_metadata_json": _coerce_json_dict(row.capture_metadata_json),
        "selected_candidate_json": row.selected_candidate_json if isinstance(row.selected_candidate_json, dict) else None,
    }
    return ReceivingSessionItemRead.model_validate(payload)


def _detail_from_rows(session_row: ReceivingSession, item_rows: list[ReceivingSessionItem]) -> ReceivingSessionDetailRead:
    summary = _session_summary(session_row)
    return ReceivingSessionDetailRead.model_validate(
        {**summary.model_dump(), "items": [_item_to_read(row).model_dump() for row in _sorted_items(item_rows)]}
    )


def _top_additions_from_items(items: list[ReceivingSessionItem], limit: int = 5) -> list[str]:
    confirmed = [item for item in items if item.status == "CONFIRMED" and item.selected_candidate_json]
    titles: list[str] = []
    for item in confirmed:
        candidate = item.selected_candidate_json or {}
        series = candidate.get("series") if isinstance(candidate, dict) else None
        issue = candidate.get("issue_number") if isinstance(candidate, dict) else None
        title = f"{series} #{issue}" if series and issue else series or "Confirmed comic"
        if title not in titles:
            titles.append(str(title))
        if len(titles) >= limit:
            break
    return titles


def _recompute_session_counters(session: Session, receiving_session_id: int) -> None:
    sess = session.get(ReceivingSession, receiving_session_id)
    if sess is None:
        return
    items = session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()
    counters = Counter(row.status for row in items)
    sess.total_items = len(items)
    sess.verified_items = int(counters.get("VERIFIED", 0))
    sess.review_items = int(counters.get("REVIEW", 0))
    sess.unknown_items = int(counters.get("UNKNOWN", 0))
    sess.confirmed_items = int(counters.get("CONFIRMED", 0))
    sess.skipped_items = int(counters.get("SKIPPED", 0))
    if sess.started_at is None and items:
        sess.started_at = min(row.uploaded_at for row in items)
    if sess.status != "COMPLETED":
        sess.status = "ACTIVE" if items else "PENDING"
    _touch(sess)
    session.add(sess)


def create_receiving_session(
    session: Session,
    *,
    owner_user_id: int,
    payload: ReceivingSessionCreatePayload | None = None,
) -> ReceivingSessionSummaryRead:
    now = utc_now()
    row = ReceivingSession(
        owner_user_id=owner_user_id,
        status="PENDING",
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
        total_items=0,
        verified_items=0,
        review_items=0,
        unknown_items=0,
        confirmed_items=0,
        skipped_items=0,
        capture_source=normalize_live_capture_source(payload.capture_source if payload else None),
        session_notes=(payload.notes if payload else None),
        allocation_details_json={},
        inventory_created_count=0,
        live_capture_stats_json={},
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    _increment_metrics(created=1)
    LOGGER.info("receiving_session_created session_id=%s owner_user_id=%s", row.id, owner_user_id)
    return _session_summary(row)


def _ensure_session_open(sess: ReceivingSession) -> None:
    if sess.completed_at is not None or sess.status == "COMPLETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receiving session is already completed")


def _confirmed_items(session: Session, receiving_session_id: int) -> list[ReceivingSessionItem]:
    items = session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()
    return [item for item in _sorted_items(items) if item.status == "CONFIRMED"]


def get_receiving_session_summary(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
) -> ReceivingCompletionSummaryRead:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    items = session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()
    return ReceivingCompletionSummaryRead(
        session=_session_summary(sess),
        confirmed_inventory_count=int(sess.inventory_created_count),
        inventory_copy_ids=[int(item.inventory_copy_id) for item in items if item.inventory_copy_id is not None],
        top_additions=_top_additions_from_items(items),
        order_id=sess.purchase_order_id,
    )


def assign_receiving_purchase(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
    payload: ReceivingPurchaseAssignmentPayload,
) -> ReceivingSessionSummaryRead:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    _ensure_session_open(sess)
    confirmed = _confirmed_items(session, receiving_session_id)
    if not confirmed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmed books are required before purchase assignment")

    if payload.mode == "existing" and payload.existing_order_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="existing_order_id is required for existing purchase assignment")
    if payload.mode == "new" and payload.purchase_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="purchase_date is required for new purchase assignment")

    sess.purchase_mode = payload.mode
    sess.purchase_source_type = payload.source_type
    sess.purchase_label = payload.purchase_label
    sess.seller_name = payload.seller_name
    sess.purchase_date = payload.purchase_date
    sess.amount_paid = payload.amount_paid
    sess.shipping_amount = payload.shipping_amount
    sess.tax_amount = payload.tax_amount
    sess.purchase_notes = payload.notes
    sess.allocation_method = payload.allocation_method

    if payload.mode == "existing":
        order = session.get(Order, payload.existing_order_id)
        if order is None or order.user_id != owner_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found")
        sess.purchase_order_id = int(order.id)
        if payload.source_type is not None and order.source_type is None:
            order.source_type = payload.source_type
        if payload.seller_name and not order.seller_name:
            order.seller_name = payload.seller_name
        if payload.notes and not order.notes:
            order.notes = payload.notes
        if payload.purchase_date is not None and order.order_date is None:  # type: ignore[unreachable]
            order.order_date = payload.purchase_date
        amount_paid = quantize_money(payload.amount_paid)
        shipping_amount = quantize_money(payload.shipping_amount)
        tax_amount = quantize_money(payload.tax_amount)
        order.shipping_amount = quantize_money(order.shipping_amount + shipping_amount)
        order.tax_amount = quantize_money(order.tax_amount + tax_amount)
        order.total_amount = quantize_money(order.total_amount + amount_paid + shipping_amount + tax_amount)
        session.add(order)
    else:
        total_amount = quantize_money(payload.amount_paid + payload.shipping_amount + payload.tax_amount)
        order = Order(
            user_id=owner_user_id,
            retailer=payload.purchase_label or (payload.source_type or "Receiving Purchase"),
            order_date=payload.purchase_date or utc_now().date(),
            source_type=payload.source_type,
            seller_name=payload.seller_name,
            notes=payload.notes,
            shipping_amount=quantize_money(payload.shipping_amount),
            tax_amount=quantize_money(payload.tax_amount),
            total_amount=total_amount,
        )
        session.add(order)
        session.flush()
        sess.purchase_order_id = int(order.id)

    sess.allocation_details_json = {
        "allocation_method": payload.allocation_method,
        "manual_allocations": [item.model_dump(mode="json") for item in payload.manual_allocations],
    }
    _touch_session(sess)
    session.add(sess)
    session.commit()
    session.refresh(sess)
    if payload.source_type:
        _increment_metrics(source_type=payload.source_type)
    return _session_summary(sess)


def _build_inventory_payloads(
    session: Session,
    *,
    receiving_session_id: int,
    owner_user_id: int,
    order: Order,
    confirmed_items: list[ReceivingSessionItem],
    allocation_method: str,
    manual_allocations: list[dict[str, Any]],
) -> list[tuple[ReceivingSessionItem, OrderItem, InventoryCopy]]:
    confirmed_total = len(confirmed_items)
    if confirmed_total == 0:
        return []

    if allocation_method == "manual":
        manual_map = {int(item["item_id"]): Decimal(str(item["amount"])) for item in manual_allocations}
        assigned_total = sum(manual_map.values(), Decimal("0"))
        if assigned_total > quantize_money(order.total_amount):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manual allocations exceed purchase amount")
        remainder = quantize_money(order.total_amount - assigned_total)
        unassigned = [item for item in confirmed_items if item.id not in manual_map]
        split = allocate_by_subtotal([Decimal("1") for _ in unassigned], remainder) if unassigned else []
        allocation_map: dict[int, Decimal] = dict(manual_map)
        for item, value in zip(unassigned, split, strict=False):
            allocation_map[int(item.id)] = quantize_money(value)
    elif allocation_method == "key_weighted":
        weights: list[Decimal] = []
        for item in confirmed_items:
            candidate = item.selected_candidate_json or {}
            series = str(candidate.get("series") or "")
            issue = str(candidate.get("issue_number") or "")
            weight = Decimal("1")
            if issue in {"1", "1A", "1B", "1/2"} or "key" in series.lower():
                weight = Decimal("3")
            elif item.recognition_confidence is not None and item.recognition_confidence >= 0.9:
                weight = Decimal("2")
            weights.append(weight)
        allocated = allocate_by_subtotal(weights, order.total_amount)
        allocation_map = {int(item.id): quantize_money(value) for item, value in zip(confirmed_items, allocated, strict=False)}
    else:
        equal = allocate_by_subtotal([Decimal("1") for _ in confirmed_items], order.total_amount)
        allocation_map = {int(item.id): quantize_money(value) for item, value in zip(confirmed_items, equal, strict=False)}

    prepared: list[tuple[ReceivingSessionItem, OrderItem, InventoryCopy]] = []
    if order.id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase order could not be created")

    if order.id is not None:
        sync_items: list[Any] = []
        for item in confirmed_items:
            snapshot = item.selected_candidate_json or item.recognition_snapshot_json or {}
            publisher_name = str(snapshot.get("publisher") or "Unknown")
            title_name = str(snapshot.get("series") or "Unknown")
            issue_number = str(snapshot.get("issue_number") or "?")
            cover_name = snapshot.get("variant") if isinstance(snapshot.get("variant"), str) else None
            variant_type = snapshot.get("variant") if isinstance(snapshot.get("variant"), str) else None
            order_item_payload = {
                "publisher": publisher_name,
                "title": title_name,
                "issue_number": issue_number,
                "cover_name": cover_name,
                "variant_type": variant_type,
                "quantity": 1,
                "raw_item_price": allocation_map[int(item.id)],
                "purchase_date": order.order_date,
                "release_date": snapshot.get("release_date"),
            }
            sync_items.append(order_item_payload)
        # Build actual order items through the canonical helper path for consistency.
        for item, order_item_payload in zip(confirmed_items, sync_items, strict=False):
            from app.schemas.orders import OrderItemCreate

            payload = OrderItemCreate(
                title=order_item_payload["title"],
                publisher=order_item_payload["publisher"],
                issue_number=order_item_payload["issue_number"],
                cover_name=order_item_payload["cover_name"],
                variant_type=order_item_payload["variant_type"],
                quantity=1,
                raw_item_price=order_item_payload["raw_item_price"],
                release_date=order_item_payload["release_date"],
                purchase_date=order.order_date,
            )
            sync_canonical_creators_for_order_item(session, payload, actor_user_id=owner_user_id, audit_reason="Receiving completion purchase sync")
            publisher = get_or_create_publisher(session, payload.publisher)
            title = get_or_create_title(session, publisher.id, payload.title)
            issue = get_or_create_issue(session, title.id, payload.issue_number)
            variant = get_or_create_variant(session, issue.id, payload)
            canonical_series = resolve_order_item_canonical_series(session, payload, actor_user_id=owner_user_id, audit_reason="Receiving completion purchase sync")
            order_item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                quantity=1,
                raw_item_price=quantize_money(payload.raw_item_price),
                allocated_shipping=Decimal("0.00"),
                allocated_tax=Decimal("0.00"),
                all_in_unit_cost=quantize_money(allocation_map[int(item.id)]),
            )
            session.add(order_item)
            session.flush()
            inventory = InventoryCopy(
                user_id=owner_user_id,
                order_item_id=order_item.id,
                variant_id=variant.id,
                copy_number=1,
                acquisition_cost=quantize_money(allocation_map[int(item.id)]),
                metadata_identity_key=build_order_item_metadata_identity_key(payload),
                canonical_series_id=canonical_series.id,
                release_date=payload.release_date,
                release_year=payload.release_year,
                release_status=payload.release_status or "unknown",
                order_status="received",
                expected_ship_date=payload.expected_ship_date,
                received_at=utc_now(),
                primary_cover_image_id=None,
                receiving_session_id=receiving_session_id,
                received_via="RECEIVING_STATION",
            )
            session.add(inventory)
            session.flush()
            item.inventory_copy_id = inventory.id
            item.updated_at = utc_now()
            session.add(item)
            prepared.append((item, order_item, inventory))

    return prepared


def complete_receiving_session(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
) -> ReceivingCompletionSummaryRead:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    _ensure_session_open(sess)
    confirmed = _confirmed_items(session, receiving_session_id)
    if not confirmed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmed books are required before completion")
    if sess.purchase_order_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Purchase assignment is required before completion")

    order = session.get(Order, sess.purchase_order_id)
    if order is None or order.user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found")

    created = _build_inventory_payloads(
        session,
        receiving_session_id=receiving_session_id,
        owner_user_id=owner_user_id,
        order=order,
        confirmed_items=confirmed,
        allocation_method=sess.allocation_method or "equal",
        manual_allocations=list(sess.allocation_details_json.get("manual_allocations", [])),
    )

    sess.status = "COMPLETED"
    sess.completed_at = utc_now()
    sess.inventory_created_count = len(created)
    _touch_session(sess)
    session.add(sess)
    session.add(order)
    session.commit()
    session.refresh(sess)
    _increment_metrics(
        completed=1,
        inventory_created=len(created),
        allocation_method=sess.allocation_method,
        source_type=sess.purchase_source_type,
    )
    LOGGER.info(
        "receiving_session_completed session_id=%s inventory_created=%s allocation_method=%s",
        receiving_session_id,
        len(created),
        sess.allocation_method,
    )
    return ReceivingCompletionSummaryRead(
        session=_session_summary(sess),
        confirmed_inventory_count=len(created),
        inventory_copy_ids=[inventory.id for _, _, inventory in created if inventory.id is not None],
        top_additions=_top_additions_from_items(session.exec(
            select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
        ).all()),
        order_id=order.id,
    )


def get_receiving_session_detail(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
) -> ReceivingSessionDetailRead:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    items = session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()
    return _detail_from_rows(sess, items)


async def _read_upload_bytes(file: UploadFile) -> bytes:
    body = await file.read()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image upload is required")
    return body


def _latest_sequence_index(session: Session, receiving_session_id: int) -> int:
    max_idx = session.exec(
        select(func.max(ReceivingSessionItem.sequence_index)).where(
            ReceivingSessionItem.receiving_session_id == receiving_session_id
        )
    ).first()
    if max_idx is None:
        return -1
    return int(max_idx)


def _lock_receiving_session_row(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
) -> ReceivingSession:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": receiving_session_id},
        )
    row = session.exec(
        select(ReceivingSession)
        .where(
            ReceivingSession.id == receiving_session_id,
            ReceivingSession.owner_user_id == owner_user_id,
        )
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiving session not found")
    return row


def _is_receiving_sequence_index_violation(exc: IntegrityError) -> bool:
    message = str(exc).lower()
    if RECEIVING_ITEM_SEQUENCE_CONSTRAINT.lower() in message:
        return True
    orig = getattr(exc, "orig", None)
    if orig is not None:
        orig_message = str(orig).lower()
        return "23505" in orig_message and "sequence_index" in orig_message
    return False


@dataclass(frozen=True)
class _PreparedReceivingUpload:
    body: bytes
    source_filename: str | None
    mime_type: str | None
    frame_fingerprint: str
    recognition: Any
    recognition_latency_ms: int
    capture_started_at: Any
    capture_completed_at: Any
    image_width: int
    image_height: int


def _persist_receiving_upload_item(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
    prepared: _PreparedReceivingUpload,
    normalized_capture_source: str,
    stable_frame_count: int,
    frame_sequence_index: int | None,
    uploaded_at: Any,
    extra_capture_metadata: dict[str, Any] | None = None,
) -> ReceivingSessionItem:
    last_error: IntegrityError | None = None
    for attempt in range(MAX_SEQUENCE_INDEX_RETRIES):
        try:
            _lock_receiving_session_row(
                session,
                owner_user_id=owner_user_id,
                receiving_session_id=receiving_session_id,
            )
            sequence_index = _latest_sequence_index(session, receiving_session_id) + 1
            item = ReceivingSessionItem(
                receiving_session_id=receiving_session_id,
                sequence_index=sequence_index,
                source_filename=prepared.source_filename,
                mime_type=prepared.mime_type,
                image_width=prepared.image_width,
                image_height=prepared.image_height,
                image_sha256=sha256_raw_bytes(prepared.body),
                capture_source=normalized_capture_source,
                frame_fingerprint=prepared.frame_fingerprint,
                frame_sequence_index=frame_sequence_index if frame_sequence_index is not None else sequence_index,
                stable_frame_count=stable_frame_count,
                recognition_bucket=prepared.recognition.bucket,
                status=prepared.recognition.bucket,
                recognition_confidence=prepared.recognition.confidence,
                recognition_latency_ms=prepared.recognition_latency_ms,
                capture_started_at=prepared.capture_started_at,
                capture_completed_at=prepared.capture_completed_at,
                recognition_snapshot_json=prepared.recognition.model_dump(mode="json"),
                candidate_snapshot_json=[
                    candidate.model_dump(mode="json") for candidate in prepared.recognition.candidates
                ],
                selected_candidate_index=None,
                selected_candidate_json=None,
                action_taken=None,
                action_reason=None,
                capture_metadata_json={
                    "capture_source": normalized_capture_source,
                    "frame_fingerprint": prepared.frame_fingerprint,
                    "stable_frame_count": stable_frame_count,
                    **(extra_capture_metadata or {}),
                },
                uploaded_at=uploaded_at,
                recognized_at=uploaded_at,
                confirmed_at=None,
                skipped_at=None,
                created_at=uploaded_at,
                updated_at=uploaded_at,
            )
            session.add(item)
            session.flush()
            session.commit()
            session.refresh(item)
            return item
        except IntegrityError as exc:
            session.rollback()
            last_error = exc
            if not _is_receiving_sequence_index_violation(exc):
                raise
            LOGGER.warning(
                "receiving_upload_sequence_retry session_id=%s attempt=%s",
                receiving_session_id,
                attempt + 1,
            )
    LOGGER.error(
        "receiving_upload_sequence_exhausted session_id=%s attempts=%s",
        receiving_session_id,
        MAX_SEQUENCE_INDEX_RETRIES,
    )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Concurrent live capture uploads collided; retry the frame.",
    ) from last_error


async def upload_receiving_session_images(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
    images: list[UploadFile],
    capture_source: str | None = None,
    frame_fingerprint: str | None = None,
    stable_frame_count: int = 0,
    frame_sequence_index: int | None = None,
    diagnostic_image: UploadFile | None = None,
    capture_metadata_json: str | None = None,
) -> ReceivingUploadResponse:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one image is required")

    extra_capture_metadata: dict[str, Any] = {}
    if capture_metadata_json:
        try:
            parsed = json.loads(capture_metadata_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="capture_metadata_json must be valid JSON",
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="capture_metadata_json must be a JSON object",
            )
        extra_capture_metadata.update(parsed)

    if diagnostic_image is not None:
        diagnostic_body = await _read_upload_bytes(diagnostic_image)
        with Image.open(BytesIO(diagnostic_body)) as img:
            diagnostic_width = int(img.width)
            diagnostic_height = int(img.height)
        extra_capture_metadata["diagnostic_frame_sha256"] = sha256_raw_bytes(diagnostic_body)
        extra_capture_metadata["diagnostic_frame_width"] = diagnostic_width
        extra_capture_metadata["diagnostic_frame_height"] = diagnostic_height
        extra_capture_metadata["diagnostic_frame_filename"] = diagnostic_image.filename

    uploaded = 0
    duplicate_suppressed_count = 0
    now = utc_now()
    normalized_capture_source = normalize_live_capture_source(capture_source) or sess.capture_source or "WEBCAM"

    prepared_uploads: list[_PreparedReceivingUpload] = []
    for image in images:
        body = await _read_upload_bytes(image)
        start = utc_now()
        next_fingerprint = frame_fingerprint or sha256_raw_bytes(body)
        duplicate_suppressed = should_suppress_duplicate_capture(
            capture_source=normalized_capture_source,
            frame_fingerprint=next_fingerprint,
            now=start,
        )
        if duplicate_suppressed:
            duplicate_suppressed_count += 1
            _increment_metrics(
                live_capture_frames=1,
                duplicate_suppressed=1,
                capture_source=normalized_capture_source,
            )
            continue
        recognition = identify_comic_cover_read(session, image_bytes=body, source_name=image.filename or "upload")
        end = utc_now()
        recognition_latency_ms = int((end - start).total_seconds() * 1000)
        with Image.open(BytesIO(body)) as img:
            image_width = int(img.width)
            image_height = int(img.height)
        prepared_uploads.append(
            _PreparedReceivingUpload(
                body=body,
                source_filename=image.filename,
                mime_type=image.content_type,
                frame_fingerprint=next_fingerprint,
                recognition=recognition,
                recognition_latency_ms=recognition_latency_ms,
                capture_started_at=start,
                capture_completed_at=end,
                image_width=image_width,
                image_height=image_height,
            )
        )

    for prepared in prepared_uploads:
        _persist_receiving_upload_item(
            session,
            owner_user_id=owner_user_id,
            receiving_session_id=receiving_session_id,
            prepared=prepared,
            normalized_capture_source=normalized_capture_source,
            stable_frame_count=stable_frame_count,
            frame_sequence_index=frame_sequence_index if frame_sequence_index is not None else None,
            uploaded_at=now,
            extra_capture_metadata=extra_capture_metadata if uploaded == 0 else None,
        )
        uploaded += 1
        _increment_metrics(
            uploaded=1,
            reviewed=int(prepared.recognition.bucket == "REVIEW"),
            unknown=int(prepared.recognition.bucket == "UNKNOWN"),
            live_capture_frames=1,
            stable_frames=int(stable_frame_count >= 3),
            capture_source=normalized_capture_source,
            recognition_latency_ms=prepared.recognition_latency_ms,
        )

    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    sess.capture_source = normalized_capture_source
    if sess.started_at is None:
        sess.started_at = now
    sess.status = "ACTIVE"
    _recompute_session_counters(session, receiving_session_id)
    sess.live_capture_stats_json = update_live_capture_stats(
        sess.live_capture_stats_json,
        capture_source=normalized_capture_source,
        stable_frame_count=stable_frame_count,
        duplicate_suppressed=duplicate_suppressed_count > 0,
    )
    session.commit()
    session.refresh(sess)
    items = session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()
    LOGGER.info(
        "receiving_items_uploaded session_id=%s uploaded=%s metrics=%s",
        receiving_session_id,
        uploaded,
        receiving_metrics_snapshot(),
    )
    return ReceivingUploadResponse(session=_detail_from_rows(sess, items), uploaded_count=uploaded)


def _select_candidate_snapshot(item: ReceivingSessionItem, candidate_index: int | None) -> tuple[int | None, dict[str, Any] | None]:
    candidates = list(item.candidate_snapshot_json or [])
    if not candidates:
        return None, None
    idx = 0 if candidate_index is None else candidate_index
    if idx < 0 or idx >= len(candidates):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate index out of range")
    return idx, candidates[idx]


def confirm_receiving_session_item(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
    payload: ReceivingConfirmPayload,
) -> ReceivingActionResponse:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    item = session.get(ReceivingSessionItem, payload.item_id)
    if item is None or item.receiving_session_id != receiving_session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiving item not found")
    if item.status in FINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receiving item already finalized")

    candidate_index, candidate_snapshot = _select_candidate_snapshot(item, payload.selected_candidate_index)
    now = utc_now()
    item.status = "CONFIRMED"
    item.action_taken = payload.decision
    item.action_reason = payload.note
    item.confirmed_at = now
    item.skipped_at = None
    item.selected_candidate_index = candidate_index
    item.selected_candidate_json = candidate_snapshot
    item.updated_at = now
    session.add(item)

    _recompute_session_counters(session, receiving_session_id)
    session.add(sess)
    session.commit()
    session.refresh(item)
    session.refresh(sess)
    _increment_metrics(confirmed=1)
    LOGGER.info("receiving_item_confirmed session_id=%s item_id=%s", receiving_session_id, item.id)
    return ReceivingActionResponse(session=_detail_from_rows(sess, session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()), item=_item_to_read(item))


def _corrected_snapshot_from_catalog(session: Session, catalog_issue_id: int) -> dict[str, Any]:
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog issue not found")
    return {
        "series": identity.series,
        "issue_number": identity.issue_number,
        "variant": None,
        "publisher": identity.publisher,
        "release_date": None,
        "confidence": 1.0,
        "cover_image_url": identity.cover_image_url,
        "catalog_issue_id": identity.catalog_issue_id,
        "source": "user_correction",
        "source_id": identity.catalog_issue_id,
        "winning_source": "user_correction",
    }


def correct_receiving_session_item(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
    item_id: int,
    payload: ReceivingCorrectionPayload,
) -> ReceivingActionResponse:
    """P95-06: point a receiving item at a user-chosen catalog issue, preserving the original match."""
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    item = session.get(ReceivingSessionItem, item_id)
    if item is None or item.receiving_session_id != receiving_session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiving item not found")
    if item.status in FINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receiving item already finalized")

    corrected_snapshot = _corrected_snapshot_from_catalog(session, payload.catalog_issue_id)
    original_snapshot = _coerce_json_dict(item.recognition_snapshot_json)

    # Preserve the very first machine recognition only once, even across repeated corrections.
    if not item.original_recognition_snapshot_json:
        item.original_recognition_snapshot_json = original_snapshot

    original_catalog_issue_id = original_snapshot.get("catalog_issue_id")
    original_source = original_snapshot.get("winning_source")
    original_confidence = item.recognition_confidence

    # Append the corrected issue as a selectable candidate so the existing confirm flow uses it.
    candidates = _coerce_json_list(item.candidate_snapshot_json)
    candidates = [*candidates, corrected_snapshot]
    corrected_index = len(candidates) - 1

    now = utc_now()
    item.candidate_snapshot_json = candidates
    item.corrected_recognition_snapshot_json = corrected_snapshot
    item.corrected_catalog_issue_id = payload.catalog_issue_id
    item.selected_candidate_index = corrected_index
    item.selected_candidate_json = corrected_snapshot
    item.user_corrected = True
    item.correction_reason = payload.reason
    item.user_corrected_at = now
    item.user_corrected_by = owner_user_id
    item.updated_at = now
    session.add(item)

    event = RecognitionCorrectionEvent(
        user_id=owner_user_id,
        receiving_session_id=receiving_session_id,
        receiving_session_item_id=item_id,
        original_catalog_issue_id=int(original_catalog_issue_id) if isinstance(original_catalog_issue_id, int) else None,
        corrected_catalog_issue_id=payload.catalog_issue_id,
        original_confidence=float(original_confidence) if original_confidence is not None else None,
        original_source=str(original_source) if original_source else None,
        correction_reason=payload.reason,
        captured_image_sha256=item.image_sha256,
        created_at=now,
    )
    session.add(event)

    session.commit()
    session.refresh(item)
    session.refresh(sess)
    LOGGER.info(
        "receiving_item_corrected session_id=%s item_id=%s corrected_catalog_issue_id=%s",
        receiving_session_id,
        item_id,
        payload.catalog_issue_id,
    )
    return ReceivingActionResponse(
        session=_detail_from_rows(
            sess,
            session.exec(
                select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
            ).all(),
        ),
        item=_item_to_read(item),
    )


def skip_receiving_session_item(
    session: Session,
    *,
    owner_user_id: int,
    receiving_session_id: int,
    payload: ReceivingSkipPayload,
) -> ReceivingActionResponse:
    sess = _require_owner(session, owner_user_id=owner_user_id, receiving_session_id=receiving_session_id)
    item = session.get(ReceivingSessionItem, payload.item_id)
    if item is None or item.receiving_session_id != receiving_session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiving item not found")
    if item.status in FINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receiving item already finalized")

    now = utc_now()
    item.status = "SKIPPED"
    item.action_taken = "skip"
    item.action_reason = payload.reason
    item.skipped_at = now
    item.confirmed_at = None
    item.updated_at = now
    session.add(item)

    _recompute_session_counters(session, receiving_session_id)
    session.add(sess)
    session.commit()
    session.refresh(item)
    session.refresh(sess)
    _increment_metrics(skipped=1)
    LOGGER.info("receiving_item_skipped session_id=%s item_id=%s", receiving_session_id, item.id)
    return ReceivingActionResponse(session=_detail_from_rows(sess, session.exec(
        select(ReceivingSessionItem).where(ReceivingSessionItem.receiving_session_id == receiving_session_id)
    ).all()), item=_item_to_read(item))

