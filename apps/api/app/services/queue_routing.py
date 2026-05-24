"""Deterministic queue-routing recommendations (signals only; no auto enqueue)."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import Session, select

from app.models import (
    CoverImage,
    CoverImageMatchCandidate,
    CoverRelationshipConflict,
    HighResReviewRequest,
    QueueRoutingRecommendation,
    ScanQaResult,
    ScanSession,
    ScanSessionItem,
)
from app.models.asset_ledger import utc_now
from app.schemas.queue_routing import (
    QueueRoutingListResponse,
    QueueRoutingPriority,
    QueueRoutingRecommendationRead,
    QueueRoutingRecommendationType,
    QueueRoutingStatus,
    ScanSessionRoutingRead,
)
from app.schemas.scan_qa import ScanQaItemRead
from app.services.scan_qa import compute_qa_items_for_scan_session

RECOMMENDATION_ORDER: tuple[QueueRoutingRecommendationType, ...] = (
    "recommend_rescan",
    "recommend_hold",
    "recommend_manual_review",
    "recommend_high_res_review",
    "recommend_ocr",
    "recommend_no_action",
)

RECOMMENDATION_PRIORITY: dict[QueueRoutingRecommendationType, QueueRoutingPriority] = {
    "recommend_rescan": "high",
    "recommend_hold": "high",
    "recommend_manual_review": "medium",
    "recommend_high_res_review": "medium",
    "recommend_ocr": "low",
    "recommend_no_action": "low",
}

REASON_ORDER: dict[str, int] = {
    "already_ocr_processed": 0,
    "review_request_open": 5,
    "duplicate_scan": 10,
    "corrupt_image": 15,
    "insufficient_dimensions": 20,
    "unreadable_text": 25,
    "failed_ocr": 30,
    "unresolved_relationship_conflict": 35,
    "high_confidence_match_available": 40,
    "high_res_scan_present": 45,
    "blurry_scan": 50,
    "low_contrast": 55,
    "low_resolution": 60,
    "needs_rescan": 65,
    "needs_high_res_review": 70,
    "ready_for_ocr": 80,
    "scan_qa_other": 90,
}


@dataclass(frozen=True)
class _RoutingContext:
    scan_session_item_id: int
    cover_image_id: int | None
    recommendation_type: QueueRoutingRecommendationType
    reasons: list[str]
    signals: list[Mapping[str, Any]]
    priority: QueueRoutingPriority


def _priority_for_recommendation(recommendation_type: QueueRoutingRecommendationType) -> QueueRoutingPriority:
    return RECOMMENDATION_PRIORITY[recommendation_type]


def _reason_sort_key(reason: str) -> tuple[int, str]:
    return (REASON_ORDER.get(reason, 999), reason)


def _sorted_signals(signals: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in sorted(signals, key=lambda row: (str(row.get("kind", "")), str(sorted(row.items()))))]


def _latest_quality_by_cover(session: Session, cover_image_id: int) -> list[dict[str, Any]]:
    from app.models import CoverImageOcrQualityAnalysis

    rows = session.exec(
        select(CoverImageOcrQualityAnalysis)
        .where(CoverImageOcrQualityAnalysis.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrQualityAnalysis.id.asc())
    ).all()
    latest: dict[str, Any] = {}
    for row in rows:
        key = str(row.quality_type)
        if key not in latest or int(row.id or 0) > int(latest[key].id or 0):
            latest[key] = row
    out: list[dict[str, Any]] = []
    for row in latest.values():
        out.append(
            {
                "kind": "ocr_quality",
                "quality_type": row.quality_type,
                "severity": row.severity,
                "deterministic_score": row.deterministic_score,
            }
        )
    return out


def _latest_ocr_result(session: Session, cover_image_id: int):
    from app.models import CoverImageOcrResult

    stmt = (
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrResult.processed_at.desc().nullslast(), CoverImageOcrResult.id.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def _open_high_res_request_exists(session: Session, inventory_copy_id: int | None, cover_image_id: int | None) -> bool:
    if inventory_copy_id is None and cover_image_id is None:
        return False
    stmt = select(HighResReviewRequest).where(HighResReviewRequest.status.in_(("pending", "scanned", "linked")))
    predicates: list[Any] = []
    if inventory_copy_id is not None:
        predicates.append(HighResReviewRequest.inventory_copy_id == inventory_copy_id)
    if cover_image_id is not None:
        predicates.append(
            (HighResReviewRequest.source_cover_image_id == cover_image_id)
            | (HighResReviewRequest.high_res_cover_image_id == cover_image_id)
        )
    if predicates:
        stmt = stmt.where(predicates[0] if len(predicates) == 1 else (predicates[0] | predicates[1]))
    return session.exec(stmt.limit(1)).first() is not None


def _open_conflict_exists(session: Session, cover_image_id: int | None) -> bool:
    if cover_image_id is None:
        return False
    return (
        session.exec(
            select(CoverRelationshipConflict).where(
                CoverRelationshipConflict.status == "open",
                (
                    (CoverRelationshipConflict.source_cover_image_id == cover_image_id)
                    | (CoverRelationshipConflict.related_cover_image_id == cover_image_id)
                ),
            )
        ).first()
        is not None
    )


def _high_confidence_match_available(session: Session, cover_image_id: int | None) -> bool:
    if cover_image_id is None:
        return False
    return (
        session.exec(
            select(CoverImageMatchCandidate).where(
                CoverImageMatchCandidate.source_cover_image_id == cover_image_id,
                CoverImageMatchCandidate.dismissed_at.is_(None),  # type: ignore[union-attr]
                CoverImageMatchCandidate.acknowledged_at.is_(None),  # type: ignore[union-attr]
                CoverImageMatchCandidate.confidence_bucket.in_(("high", "very_high")),
            )
        ).first()
        is not None
    )


def _high_res_scan_present(
    session: Session,
    *,
    cover: CoverImage | None,
    inventory_copy_id: int | None,
) -> bool:
    if cover is not None and cover.image_width and cover.image_height and max(cover.image_width, cover.image_height) >= 1400:
        return True
    if inventory_copy_id is None:
        return False
    return (
        session.exec(
            select(CoverImage)
            .where(
                CoverImage.inventory_copy_id == inventory_copy_id,
                CoverImage.image_width.is_not(None),
                CoverImage.image_height.is_not(None),
            )
            .order_by(CoverImage.image_width.desc(), CoverImage.image_height.desc(), CoverImage.id.desc())
            .limit(1)
        ).first()
        is not None
    )


def _scan_qa_row_for_item(rows: Sequence[ScanQaItemRead], item_id: int) -> ScanQaItemRead | None:
    for row in rows:
        if row.scan_session_item_id == item_id:
            return row
    return None


def _has_reason(qa_row: ScanQaItemRead | None, reason: str) -> bool:
    if qa_row is None:
        return False
    signals = qa_row.evidence_json.get("signals")
    if not isinstance(signals, list):
        return False
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        kind = str(signal.get("kind") or "")
        if reason == "corrupt_image" and kind in {"unsupported_mime", "cover_processing_failed", "ingest_failure", "ingest_failure_unknown"}:
            return True
        if reason == "needs_rescan" and kind in {"explicit_physical_rescan_marker", "phone_camera_under_target_resolution"}:
            return True
        if reason == "low_resolution" and kind in {"dimension_below_minimum", "ocr_quality_signal"}:
            return True
        if reason == "low_contrast" and kind == "ocr_quality_signal" and signal.get("quality_type") == "low_contrast":
            return True
        if reason == "blurry_scan" and kind == "ocr_quality_signal" and signal.get("quality_type") == "blur_detection":
            return True
        if reason == "already_ocr_processed" and kind == "ingest_status_ocr_complete":
            return True
        if reason == "failed_ocr" and kind == "ocr_quality_signal" and signal.get("quality_type") == "unreadable_ocr":
            return True
        if reason == "unreadable_text" and kind == "ocr_quality_signal" and signal.get("quality_type") == "unreadable_ocr":
            return True
        if reason == "duplicate_scan" and kind == "duplicate_sha256_within_session":
            return True
        if reason == "needs_high_res_review" and kind in {"ocr_quality_signal", "overall_quality_escalated_by_dimensions"}:
            return True
    return False


def _recommendation_for_item(
    session: Session,
    *,
    qa_row: ScanQaItemRead | None,
    item: ScanSessionItem,
    cover: CoverImage | None,
) -> _RoutingContext:
    inventory_copy_id = int(item.inventory_copy_id) if item.inventory_copy_id is not None else None
    cover_id = int(item.cover_image_id) if item.cover_image_id is not None else (int(cover.id) if cover and cover.id else None)
    reasons: list[str] = []
    signals: list[Mapping[str, Any]] = []

    if qa_row is not None:
        reasons.extend(qa_row.evidence_json.get("deterministic_notes", []))
        raw_signals = qa_row.evidence_json.get("signals")
        if isinstance(raw_signals, list):
            for row in raw_signals:
                if isinstance(row, dict):
                    signals.append(dict(row))

    ocr_result = _latest_ocr_result(session, cover_id) if cover_id is not None else None
    if ocr_result is not None:
        signals.append(
            {
                "kind": "ocr_history",
                "processing_status": ocr_result.processing_status,
                "ocr_engine": ocr_result.ocr_engine,
                "processed_at": ocr_result.processed_at,
            }
        )
        if ocr_result.processing_status == "processed":
            reasons.append("already_ocr_processed")
        elif ocr_result.processing_status == "failed":
            reasons.append("failed_ocr")

    if cover is not None:
        signals.append(
            {
                "kind": "cover_processing",
                "processing_status": cover.processing_status,
                "matching_status": cover.matching_status,
                "image_width": cover.image_width,
                "image_height": cover.image_height,
            }
        )
        if cover.processing_status == "processed":
            reasons.append("already_ocr_processed")
        elif cover.processing_status == "failed":
            reasons.append("corrupt_image")

    if cover is not None and cover.image_width is not None and cover.image_height is not None:
        if max(cover.image_width, cover.image_height) < 560:
            reasons.append("insufficient_dimensions")
        elif max(cover.image_width, cover.image_height) < 900:
            reasons.append("low_resolution")

    if qa_row is not None:
        cls = qa_row.qa_classification
        if cls == "already_processed":
            reasons.append("already_ocr_processed")
        elif cls == "duplicate_scan":
            reasons.append("duplicate_scan")
        elif cls == "needs_rescan":
            reasons.append("needs_rescan")
        elif cls == "corrupt_or_unreadable":
            reasons.append("corrupt_image")
        elif cls in {"low_resolution", "low_contrast", "blurry", "needs_high_res_review"}:
            reasons.append(cls if cls != "needs_high_res_review" else "needs_high_res_review")
        elif cls == "review_required":
            reasons.append("scan_qa_other")
        elif cls == "ready_for_ocr":
            reasons.append("ready_for_ocr")

    if _open_high_res_request_exists(session, inventory_copy_id, cover_id):
        reasons.append("review_request_open")
    if _open_conflict_exists(session, cover_id):
        reasons.append("unresolved_relationship_conflict")
    if _high_confidence_match_available(session, cover_id):
        reasons.append("high_confidence_match_available")

    high_res_present = _high_res_scan_present(session, cover=cover, inventory_copy_id=inventory_copy_id)
    if high_res_present:
        reasons.append("high_res_scan_present")

    reason_set = set(reasons)
    if "already_ocr_processed" in reason_set:
        recommendation = "recommend_no_action"
    elif "review_request_open" in reason_set:
        recommendation = "recommend_hold"
    elif "duplicate_scan" in reason_set:
        recommendation = "recommend_hold"
    elif "corrupt_image" in reason_set or "insufficient_dimensions" in reason_set or "needs_rescan" in reason_set:
        recommendation = "recommend_rescan"
    elif "unresolved_relationship_conflict" in reason_set or "high_confidence_match_available" in reason_set:
        recommendation = "recommend_manual_review"
    elif any(
        reason in reason_set
        for reason in (
            "needs_high_res_review",
            "low_resolution",
            "low_contrast",
            "blurry_scan",
            "failed_ocr",
            "unreadable_text",
        )
    ):
        recommendation = "recommend_high_res_review"
    elif "high_res_scan_present" in reason_set:
        recommendation = "recommend_ocr"
    elif "ready_for_ocr" in reason_set or item.ingest_status in {"imported", "queued_for_ocr", "pending"}:
        recommendation = "recommend_ocr"
    else:
        recommendation = "recommend_manual_review"

    priority: QueueRoutingPriority = _priority_for_recommendation(recommendation)
    if recommendation in {"recommend_rescan", "recommend_hold"}:
        priority = "high"
    elif recommendation in {"recommend_manual_review", "recommend_high_res_review"}:
        priority = "medium"

    evidence: dict[str, Any] = {
        "scan_session_item_id": int(item.id or 0),
        "cover_image_id": cover_id,
        "scan_session_id": int(item.scan_session_id),
        "item_ingest_status": item.ingest_status,
        "qa_classification": qa_row.qa_classification if qa_row is not None else None,
        "qa_routing_recommendation": qa_row.routing_recommendation if qa_row is not None else None,
        "qa_severity": qa_row.severity if qa_row is not None else None,
        "reasons": sorted(reason_set, key=_reason_sort_key),
        "signals": _sorted_signals(signals),
        "priority_basis": priority,
        "high_res_scan_present": high_res_present,
        "already_ocr_processed": "already_ocr_processed" in reason_set,
    }

    return _RoutingContext(
        scan_session_item_id=int(item.id or 0),
        cover_image_id=cover_id,
        recommendation_type=recommendation,
        reasons=evidence["reasons"],
        signals=evidence["signals"],
        priority=priority,
    )


def _hydrate_live_routing(
    *,
    session: Session,
    scan_session: ScanSession,
    qa_rows: Sequence[ScanQaItemRead],
) -> list[QueueRoutingRecommendationRead]:
    stmt = (
        select(ScanSessionItem, CoverImage)
        .join(CoverImage, ScanSessionItem.cover_image_id == CoverImage.id, isouter=True)
        .where(ScanSessionItem.scan_session_id == int(scan_session.id or 0))
        .order_by(ScanSessionItem.sequence_index.asc(), ScanSessionItem.id.asc())
    )
    rows = session.exec(stmt).all()
    persisted = {
        int(row.scan_session_item_id): row
        for row in session.exec(
            select(QueueRoutingRecommendation).where(
                QueueRoutingRecommendation.scan_session_item_id.in_(
                    [int(r.id) for r in session.exec(select(ScanSessionItem.id).where(ScanSessionItem.scan_session_id == int(scan_session.id or 0))).all() if r is not None]
                )
            )
        ).all()
        if row.scan_session_item_id is not None
    }

    out: list[QueueRoutingRecommendationRead] = []
    for item, cover in rows:
        if item.id is None:
            continue
        qa_row = _scan_qa_row_for_item(qa_rows, int(item.id))
        ctx = _recommendation_for_item(session, qa_row=qa_row, item=item, cover=cover)
        stored = persisted.get(int(item.id))
        if stored is not None:
            out.append(
                QueueRoutingRecommendationRead(
                    id=int(stored.id or 0),
                    scan_session_item_id=int(stored.scan_session_item_id) if stored.scan_session_item_id is not None else None,
                    cover_image_id=int(stored.cover_image_id) if stored.cover_image_id is not None else None,
                    scan_session_id=int(item.scan_session_id),
                    recommendation_type=stored.recommendation_type,  # type: ignore[arg-type]
                    priority=stored.priority,  # type: ignore[arg-type]
                    routing_status=stored.routing_status,  # type: ignore[arg-type]
                    evidence_json=dict(stored.evidence_json or {}),
                    created_at=stored.created_at,
                    updated_at=stored.updated_at,
                )
            )
        else:
            out.append(
                QueueRoutingRecommendationRead(
                    id=None,
                    scan_session_item_id=int(item.id),
                    cover_image_id=ctx.cover_image_id,
                    scan_session_id=int(item.scan_session_id),
                    recommendation_type=ctx.recommendation_type,
                    priority=ctx.priority,
                    routing_status="open",
                    evidence_json={
                        "reasons": ctx.reasons,
                        "signals": ctx.signals,
                    },
                    created_at=None,
                    updated_at=None,
                )
            )
    return out


def _persisted_routing_rows_for_session(session: Session, scan_session_id: int) -> list[QueueRoutingRecommendation]:
    item_ids = [int(rid) for rid in session.exec(select(ScanSessionItem.id).where(ScanSessionItem.scan_session_id == scan_session_id)).all() if rid is not None]
    if not item_ids:
        return []
    return session.exec(
        select(QueueRoutingRecommendation).where(QueueRoutingRecommendation.scan_session_item_id.in_(item_ids))
    ).all()


def _item_map_for_session(session: Session, scan_session_id: int) -> dict[int, tuple[ScanSessionItem, CoverImage | None]]:
    stmt = (
        select(ScanSessionItem, CoverImage)
        .join(CoverImage, ScanSessionItem.cover_image_id == CoverImage.id, isouter=True)
        .where(ScanSessionItem.scan_session_id == scan_session_id)
        .order_by(ScanSessionItem.sequence_index.asc(), ScanSessionItem.id.asc())
    )
    out: dict[int, tuple[ScanSessionItem, CoverImage | None]] = {}
    for item, cover in session.exec(stmt).all():
        if item.id is not None:
            out[int(item.id)] = (item, cover)
    return out


def _qa_rows_for_session(session: Session, scan_session: ScanSession) -> list[ScanQaItemRead]:
    return compute_qa_items_for_scan_session(session, scan_session=scan_session)


def _session_routing_summary_from_live(
    session: Session,
    *,
    scan_session: ScanSession,
    persisted_rows: Mapping[int, QueueRoutingRecommendation] | None = None,
) -> list[QueueRoutingRecommendationRead]:
    qa_rows = _qa_rows_for_session(session, scan_session)
    item_map = _item_map_for_session(session, int(scan_session.id or 0))
    persisted_rows = persisted_rows or {}
    out: list[QueueRoutingRecommendationRead] = []
    for item_id in sorted(item_map.keys()):
        item, cover = item_map[item_id]
        qa_row = _scan_qa_row_for_item(qa_rows, item_id)
        ctx = _recommendation_for_item(session, qa_row=qa_row, item=item, cover=cover)
        stored = persisted_rows.get(item_id)
        if stored is not None:
            out.append(
                QueueRoutingRecommendationRead(
                    id=int(stored.id or 0),
                    scan_session_item_id=int(stored.scan_session_item_id) if stored.scan_session_item_id is not None else None,
                    cover_image_id=int(stored.cover_image_id) if stored.cover_image_id is not None else None,
                    scan_session_id=int(scan_session.id or 0),
                    recommendation_type=stored.recommendation_type,  # type: ignore[arg-type]
                    priority=stored.priority,  # type: ignore[arg-type]
                    routing_status=stored.routing_status,  # type: ignore[arg-type]
                    evidence_json=dict(stored.evidence_json or {}),
                    created_at=stored.created_at,
                    updated_at=stored.updated_at,
                )
            )
            continue
        out.append(
            QueueRoutingRecommendationRead(
                id=None,
                scan_session_item_id=item_id,
                cover_image_id=ctx.cover_image_id,
                scan_session_id=int(scan_session.id or 0),
                recommendation_type=ctx.recommendation_type,
                priority=ctx.priority,
                routing_status="open",
                evidence_json={"reasons": ctx.reasons, "signals": ctx.signals},
                created_at=None,
                updated_at=None,
            )
        )
    return out


def _totals(rows: Sequence[QueueRoutingRecommendationRead]) -> tuple[dict[str, int], dict[str, int], int]:
    by_type: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    unresolved = 0
    for row in rows:
        by_type[row.recommendation_type] += 1
        by_status[row.routing_status] += 1
        if row.routing_status == "open":
            unresolved += 1
    return dict(sorted(by_type.items())), dict(sorted(by_status.items())), unresolved


def get_scan_session_routing(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_session_id: int,
) -> ScanSessionRoutingRead:
    scan_session = session.get(ScanSession, scan_session_id)
    if scan_session is None or (owner_user_id is not None and scan_session.owner_user_id != owner_user_id):
        raise HTTPException(status_code=404, detail="Scan session not found")
    persisted = {int(row.scan_session_item_id): row for row in _persisted_routing_rows_for_session(session, scan_session_id) if row.scan_session_item_id is not None}
    live_rows = _session_routing_summary_from_live(session, scan_session=scan_session, persisted_rows=persisted)
    totals_type, totals_status, unresolved = _totals(live_rows)
    persisted_run = bool(persisted)
    return ScanSessionRoutingRead(
        scan_session_id=int(scan_session.id),
        owner_user_id=int(scan_session.owner_user_id),
        persisted_run=persisted_run,
        items=live_rows,
        totals_by_recommendation=totals_type,
        totals_by_status=totals_status,
        unresolved_count=unresolved,
    )


def generate_scan_session_routing(
    session: Session,
    *,
    owner_user_id: int,
    scan_session_id: int,
) -> ScanSessionRoutingRead:
    scan_session = session.get(ScanSession, scan_session_id)
    if scan_session is None or scan_session.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan session not found")
    qa_rows = _qa_rows_for_session(session, scan_session)
    item_map = _item_map_for_session(session, int(scan_session.id or 0))
    existing = {
        int(row.scan_session_item_id): row
        for row in _persisted_routing_rows_for_session(session, scan_session_id)
        if row.scan_session_item_id is not None
    }

    now = utc_now()
    live_rows = _session_routing_summary_from_live(session, scan_session=scan_session, persisted_rows=existing)
    seen: set[int] = set()
    for item_id, (item, cover) in item_map.items():
        if item.id is None:
            continue
        seen.add(int(item.id))
        qa_row = _scan_qa_row_for_item(qa_rows, int(item.id))
        ctx = _recommendation_for_item(session, qa_row=qa_row, item=item, cover=cover)
        current = existing.get(int(item.id))
        if current is None:
            session.add(
                QueueRoutingRecommendation(
                    scan_session_item_id=int(item.id),
                    cover_image_id=ctx.cover_image_id,
                    recommendation_type=ctx.recommendation_type,
                    priority=ctx.priority,
                    routing_status="open",
                    evidence_json={"reasons": ctx.reasons, "signals": ctx.signals},
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            current.cover_image_id = ctx.cover_image_id
            current.recommendation_type = ctx.recommendation_type
            current.priority = ctx.priority
            current.evidence_json = {"reasons": ctx.reasons, "signals": ctx.signals}
            current.updated_at = now
            session.add(current)

    stale_ids = [rid for rid in existing.keys() if rid not in seen]
    if stale_ids:
        session.execute(delete(QueueRoutingRecommendation).where(QueueRoutingRecommendation.scan_session_item_id.in_(stale_ids)))

    session.commit()
    persisted = {int(row.scan_session_item_id): row for row in _persisted_routing_rows_for_session(session, scan_session_id) if row.scan_session_item_id is not None}
    refreshed = _session_routing_summary_from_live(session, scan_session=scan_session, persisted_rows=persisted)
    totals_type, totals_status, unresolved = _totals(refreshed)
    return ScanSessionRoutingRead(
        scan_session_id=int(scan_session.id),
        owner_user_id=int(scan_session.owner_user_id),
        persisted_run=True,
        items=refreshed,
        totals_by_recommendation=totals_type,
        totals_by_status=totals_status,
        unresolved_count=unresolved,
    )


def list_queue_routing_recommendations_owner(
    session: Session,
    *,
    owner_user_id: int,
) -> QueueRoutingListResponse:
    item_ids = session.exec(
        select(ScanSessionItem.id)
        .join(ScanSession, ScanSessionItem.scan_session_id == ScanSession.id)
        .where(ScanSession.owner_user_id == owner_user_id)
    ).all()
    item_ids_i = [int(rid) for rid in item_ids if rid is not None]
    rows = []
    if item_ids_i:
        rows = session.exec(
            select(QueueRoutingRecommendation)
            .where(QueueRoutingRecommendation.scan_session_item_id.in_(item_ids_i))
            .order_by(QueueRoutingRecommendation.updated_at.desc(), QueueRoutingRecommendation.id.desc())
        ).all()
    items = [
        QueueRoutingRecommendationRead(
            id=int(row.id or 0),
            scan_session_item_id=int(row.scan_session_item_id) if row.scan_session_item_id is not None else None,
            cover_image_id=int(row.cover_image_id) if row.cover_image_id is not None else None,
            recommendation_type=row.recommendation_type,  # type: ignore[arg-type]
            priority=row.priority,  # type: ignore[arg-type]
            routing_status=row.routing_status,  # type: ignore[arg-type]
            evidence_json=dict(row.evidence_json or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    totals_type, totals_status, unresolved = _totals(items)
    return QueueRoutingListResponse(
        items=items,
        totals_by_recommendation=totals_type,
        totals_by_status=totals_status,
        unresolved_count=unresolved,
    )


def list_queue_routing_recommendations_ops(session: Session) -> QueueRoutingListResponse:
    rows = session.exec(
        select(QueueRoutingRecommendation).order_by(
            QueueRoutingRecommendation.updated_at.desc(),
            QueueRoutingRecommendation.id.desc(),
        )
    ).all()
    items = [
        QueueRoutingRecommendationRead(
            id=int(row.id or 0),
            scan_session_item_id=int(row.scan_session_item_id) if row.scan_session_item_id is not None else None,
            cover_image_id=int(row.cover_image_id) if row.cover_image_id is not None else None,
            recommendation_type=row.recommendation_type,  # type: ignore[arg-type]
            priority=row.priority,  # type: ignore[arg-type]
            routing_status=row.routing_status,  # type: ignore[arg-type]
            evidence_json=dict(row.evidence_json or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    totals_type, totals_status, unresolved = _totals(items)
    return QueueRoutingListResponse(
        items=items,
        totals_by_recommendation=totals_type,
        totals_by_status=totals_status,
        unresolved_count=unresolved,
    )


def _set_routing_status(
    session: Session,
    *,
    recommendation_id: int,
    owner_user_id: int | None,
    new_status: QueueRoutingStatus,
) -> QueueRoutingRecommendationRead:
    stmt = select(QueueRoutingRecommendation).where(QueueRoutingRecommendation.id == recommendation_id)
    if owner_user_id is not None:
        stmt = (
            stmt.join(ScanSessionItem, QueueRoutingRecommendation.scan_session_item_id == ScanSessionItem.id)
            .join(ScanSession, ScanSessionItem.scan_session_id == ScanSession.id)
            .where(ScanSession.owner_user_id == owner_user_id)
        )
    row = session.exec(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Queue routing recommendation not found")
    if row.routing_status != "open":
        raise HTTPException(status_code=400, detail="Queue routing recommendation already resolved")
    row.routing_status = new_status
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return QueueRoutingRecommendationRead(
        id=int(row.id or 0),
        scan_session_item_id=int(row.scan_session_item_id) if row.scan_session_item_id is not None else None,
        cover_image_id=int(row.cover_image_id) if row.cover_image_id is not None else None,
        recommendation_type=row.recommendation_type,  # type: ignore[arg-type]
        priority=row.priority,  # type: ignore[arg-type]
        routing_status=row.routing_status,  # type: ignore[arg-type]
        evidence_json=dict(row.evidence_json or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def acknowledge_queue_routing_recommendation(
    session: Session,
    *,
    recommendation_id: int,
    owner_user_id: int | None,
) -> QueueRoutingRecommendationRead:
    return _set_routing_status(
        session,
        recommendation_id=recommendation_id,
        owner_user_id=owner_user_id,
        new_status="acknowledged",
    )


def dismiss_queue_routing_recommendation(
    session: Session,
    *,
    recommendation_id: int,
    owner_user_id: int | None,
) -> QueueRoutingRecommendationRead:
    return _set_routing_status(
        session,
        recommendation_id=recommendation_id,
        owner_user_id=owner_user_id,
        new_status="dismissed",
    )

