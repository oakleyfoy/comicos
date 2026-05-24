from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    ComicIssue,
    ComicTitle,
    CoverImage,
    CoverImageMatchCandidate,
    CoverImageOcrQualityAnalysis,
    CoverImageOcrResult,
    CoverRelationshipConflict,
    InventoryCopy,
    Order,
    OrderItem,
    Publisher,
    User,
    Variant,
)
from app.schemas.inventory_intelligence import KeyedCount
from app.schemas.inventory_risks import (
    InventoryRiskListResponse,
    InventoryRiskPriority,
    InventoryRiskRead,
    InventoryRiskStatus,
    InventoryRiskSummary,
    InventoryRiskSummaryItem,
    InventoryRiskType,
)
from app.services.duplicate_ownership_intelligence import (
    list_duplicate_ownership_ops,
    list_duplicate_ownership_owner,
)
from app.services.inventory_intelligence import (
    pending_canonical_inventory_ids,
    preorder_missing_release_calendar,
    normalize_ownership_state,
)
from app.services.run_detection import list_run_detection_ops, list_run_detection_owner

_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


@dataclass(frozen=True)
class RiskProjectionRow:
    inventory_copy_id: int
    owner_user_id: int | None
    primary_cover_image_id: int | None
    release_status: str
    order_status: str
    received_at: object | None
    release_date: object | None
    release_year: int | None
    grade_status: str
    publisher: str
    title: str
    issue_number: str


def _inventory_projection_rows(session: Session, *, user_id: int | None) -> list[RiskProjectionRow]:
    stmt = (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.user_id.label("owner_user_id"),
            InventoryCopy.primary_cover_image_id.label("primary_cover_image_id"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.received_at.label("received_at"),
            InventoryCopy.release_date.label("release_date"),
            InventoryCopy.release_year.label("release_year"),
            InventoryCopy.grade_status.label("grade_status"),
            Publisher.name.label("publisher"),
            ComicTitle.name.label("title"),
            ComicIssue.issue_number.label("issue_number"),
        )
        .select_from(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
    )
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    stmt = stmt.order_by(InventoryCopy.id.asc())
    rows = session.exec(stmt).all()
    return [
        RiskProjectionRow(
            inventory_copy_id=int(row.inventory_copy_id),
            owner_user_id=int(row.owner_user_id) if row.owner_user_id is not None else None,
            primary_cover_image_id=int(row.primary_cover_image_id) if row.primary_cover_image_id is not None else None,
            release_status=str(row.release_status),
            order_status=str(row.order_status),
            received_at=row.received_at,
            release_date=row.release_date,
            release_year=int(row.release_year) if row.release_year is not None else None,
            grade_status=str(row.grade_status),
            publisher=str(row.publisher),
            title=str(row.title),
            issue_number=str(row.issue_number),
        )
        for row in rows
    ]


def _projection_row_for_inventory(
    session: Session,
    *,
    current_user: User | None,
    inventory_copy_id: int,
) -> RiskProjectionRow | None:
    user_id = int(current_user.id) if current_user is not None and current_user.id is not None else None
    for row in _inventory_projection_rows(session, user_id=user_id):
        if row.inventory_copy_id == inventory_copy_id:
            return row
    return None


def _covers_by_inventory(session: Session, inventory_ids: Iterable[int]) -> dict[int, list[CoverImage]]:
    ids = sorted({int(item) for item in inventory_ids})
    if not ids:
        return {}
    rows = session.exec(select(CoverImage).where(CoverImage.inventory_copy_id.in_(ids))).all()
    out: defaultdict[int, list[CoverImage]] = defaultdict(list)
    for row in rows:
        if row.inventory_copy_id is None:
            continue
        out[int(row.inventory_copy_id)].append(row)
    for items in out.values():
        items.sort(key=lambda item: int(item.id or 0))
    return dict(out)


def _latest_ocr_by_cover(session: Session, cover_ids: Iterable[int]) -> dict[int, CoverImageOcrResult | None]:
    ids = sorted({int(item) for item in cover_ids})
    if not ids:
        return {}
    rows = session.exec(select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id.in_(ids))).all()
    bucket: defaultdict[int, list[CoverImageOcrResult]] = defaultdict(list)
    for row in rows:
        bucket[int(row.cover_image_id)].append(row)
    latest: dict[int, CoverImageOcrResult | None] = {}
    for cover_id in ids:
        candidates = bucket.get(cover_id, [])
        if not candidates:
            latest[cover_id] = None
            continue
        candidates.sort(key=lambda row: (row.processed_at or row.created_at, int(row.id or 0)), reverse=True)
        latest[cover_id] = candidates[0]
    return latest


def _quality_rows_by_cover(session: Session, cover_ids: Iterable[int]) -> dict[int, list[CoverImageOcrQualityAnalysis]]:
    ids = sorted({int(item) for item in cover_ids})
    if not ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrQualityAnalysis).where(CoverImageOcrQualityAnalysis.cover_image_id.in_(ids))
    ).all()
    bucket: defaultdict[int, list[CoverImageOcrQualityAnalysis]] = defaultdict(list)
    for row in rows:
        bucket[int(row.cover_image_id)].append(row)
    for items in bucket.values():
        items.sort(
            key=lambda row: (
                0 if row.severity == "critical" else 1 if row.severity == "warning" else 2,
                row.deterministic_score,
                int(row.id or 0),
            )
        )
    return dict(bucket)


def _match_rows_by_cover(session: Session, cover_ids: Iterable[int]) -> dict[int, list[CoverImageMatchCandidate]]:
    ids = sorted({int(item) for item in cover_ids})
    if not ids:
        return {}
    rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(
            CoverImageMatchCandidate.source_cover_image_id.in_(ids),
            CoverImageMatchCandidate.dismissed_at.is_(None),
            CoverImageMatchCandidate.acknowledged_at.is_(None),
        )
        .order_by(
            CoverImageMatchCandidate.source_cover_image_id.asc(),
            CoverImageMatchCandidate.normalized_confidence_score.desc(),
            CoverImageMatchCandidate.ranking_score.desc(),
            CoverImageMatchCandidate.candidate_rank.asc(),
            CoverImageMatchCandidate.id.asc(),
        )
    ).all()
    bucket: defaultdict[int, list[CoverImageMatchCandidate]] = defaultdict(list)
    for row in rows:
        bucket[int(row.source_cover_image_id)].append(row)
    return dict(bucket)


def _open_conflicts_by_inventory(session: Session, inventory_ids: Iterable[int]) -> dict[int, list[CoverRelationshipConflict]]:
    ids = sorted({int(item) for item in inventory_ids})
    if not ids:
        return {}
    cover_rows = session.exec(
        select(CoverImage.id, CoverImage.inventory_copy_id).where(CoverImage.inventory_copy_id.in_(ids))
    ).all()
    cid_to_inv = {int(cid): int(inv) for cid, inv in cover_rows if cid is not None and inv is not None}
    conflicts = session.exec(select(CoverRelationshipConflict).where(CoverRelationshipConflict.status == "open")).all()
    bucket: defaultdict[int, list[CoverRelationshipConflict]] = defaultdict(list)
    for conflict in conflicts:
        hit_ids: set[int] = set()
        for cid in (conflict.source_cover_image_id, conflict.related_cover_image_id):
            if cid is None:
                continue
            mapped = cid_to_inv.get(int(cid))
            if mapped is not None:
                hit_ids.add(mapped)
        for inv_id in hit_ids:
            bucket[inv_id].append(conflict)
    return dict(bucket)


def _priority_max(left: InventoryRiskPriority, right: InventoryRiskPriority) -> InventoryRiskPriority:
    return left if _PRIORITY_ORDER[left] <= _PRIORITY_ORDER[right] else right


def _new_risk(
    *,
    inventory_copy_id: int,
    cover_image_id: int | None,
    risk_type: InventoryRiskType,
    priority: InventoryRiskPriority,
    ownership_state: str,
    publisher: str,
    title: str,
    issue_number: str,
    evidence_json: dict[str, Any],
) -> InventoryRiskRead:
    return InventoryRiskRead(
        risk_key=f"inv:{inventory_copy_id}:{risk_type}",
        inventory_copy_id=inventory_copy_id,
        cover_image_id=cover_image_id,
        risk_type=risk_type,
        priority=priority,
        status="open",
        ownership_state=ownership_state,  # type: ignore[arg-type]
        publisher=publisher,
        title=title,
        issue_number=issue_number,
        evidence_json=evidence_json,
    )


def _aggregate_risks(
    inventory_rows: list[RiskProjectionRow],
    *,
    session: Session,
    current_user: User | None,
) -> tuple[list[InventoryRiskRead], dict[int, list[InventoryRiskRead]]]:
    risk_rows: list[InventoryRiskRead] = []
    risks_by_inventory: defaultdict[int, list[InventoryRiskRead]] = defaultdict(list)

    inventory_ids = [row.inventory_copy_id for row in inventory_rows]
    covers_by_inventory = _covers_by_inventory(session, inventory_ids)
    primary_cover_by_inventory: dict[int, int] = {}
    for row in inventory_rows:
        covers = covers_by_inventory.get(row.inventory_copy_id, [])
        chosen_cover = None
        if row.primary_cover_image_id is not None:
            chosen_cover = next(
                (item for item in covers if int(item.id or -1) == int(row.primary_cover_image_id)),
                None,
            )
        if chosen_cover is None and covers:
            chosen_cover = covers[0]
        if chosen_cover is not None and chosen_cover.id is not None:
            primary_cover_by_inventory[row.inventory_copy_id] = int(chosen_cover.id)
    primary_cover_ids = set(primary_cover_by_inventory.values())
    latest_ocr = _latest_ocr_by_cover(session, primary_cover_ids)
    quality_by_cover = _quality_rows_by_cover(session, primary_cover_ids)
    match_by_cover = _match_rows_by_cover(session, primary_cover_ids)
    open_conflicts = _open_conflicts_by_inventory(session, inventory_ids)

    if current_user is None:
        duplicate_ownership = list_duplicate_ownership_ops(
            session,
            dup_scan_classification="all",
            classification=None,
        )
        run_detection = list_run_detection_ops(session, series_status=None)
    else:
        duplicate_ownership = list_duplicate_ownership_owner(
            session,
            user=current_user,
            dup_scan_classification="all",
            classification=None,
        )
        run_detection = list_run_detection_owner(session, user=current_user, series_status=None)

    duplicate_groups_by_inventory: defaultdict[int, list[str]] = defaultdict(list)
    duplicate_class_by_inventory: dict[int, str] = {}
    for group in duplicate_ownership.groups:
        if group.classification == "intentional_multi_copy":
            continue
        for inv_id in group.inventory_copy_ids:
            duplicate_groups_by_inventory[int(inv_id)].append(group.group_key)
            duplicate_class_by_inventory[int(inv_id)] = group.classification

    run_groups_by_inventory: defaultdict[int, list[tuple[str, str, list[str], list[str]]]] = defaultdict(list)
    for group in run_detection.series_groups:
        gap_labels = [
            item.issue_number or "identity gap"
            for item in group.missing_issues
            if item.classification in ("confirmed_missing", "likely_missing", "unresolved_identity_gap")
        ]
        pending_labels = [
            item.issue_number or "pending"
            for item in group.missing_issues
            if item.classification in ("preorder_pending", "unreleased_future_issue")
        ]
        if not gap_labels and not pending_labels:
            continue
        for inv_id in group.inventory_copy_ids:
            run_groups_by_inventory[int(inv_id)].append((group.series_key, group.series_status, gap_labels, pending_labels))

    canonical_ids = pending_canonical_inventory_ids(
        session,
        inventory_ids=set(inventory_ids),
    )

    for row in inventory_rows:
        inv_id = row.inventory_copy_id
        covers = covers_by_inventory.get(inv_id, [])
        primary_cover_id = primary_cover_by_inventory.get(inv_id)
        primary_cover = next((item for item in covers if int(item.id or -1) == int(primary_cover_id or -1)), None)

        ownership_state = normalize_ownership_state(
            release_status=row.release_status,
            order_status=row.order_status,
            received_at=row.received_at,
        )
        preorder_missing_calendar = preorder_missing_release_calendar(
            ownership=ownership_state,
            release_date=row.release_date,
            release_year=row.release_year,
        )

        has_cover_scan = bool(covers)
        cover_processing_failed = primary_cover is not None and getattr(primary_cover, "processing_status", "") == "failed"
        ocr_row = latest_ocr.get(primary_cover_id) if primary_cover_id is not None else None
        ocr_failed = ocr_row is not None and getattr(ocr_row, "processing_status", "") == "failed"
        ocr_complete = ocr_row is not None and getattr(ocr_row, "processing_status", "") == "processed"

        if inv_id in canonical_ids:
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="needs_canonical_review",
                    priority="high",
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "pending_canonical_suggestion": True,
                        "inventory_copy_id": inv_id,
                    },
                )
            )

        conflicts = open_conflicts.get(inv_id, [])
        if conflicts:
            severity = "info"
            if any(conflict.severity == "critical" for conflict in conflicts):
                severity = "critical"
            elif any(conflict.severity == "warning" for conflict in conflicts):
                severity = "high"
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="needs_conflict_review",
                    priority=severity,  # type: ignore[arg-type]
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "open_conflict_count": len(conflicts),
                        "critical_count": sum(1 for conflict in conflicts if conflict.severity == "critical"),
                        "warning_count": sum(1 for conflict in conflicts if conflict.severity == "warning"),
                        "info_count": sum(1 for conflict in conflicts if conflict.severity == "info"),
                        "conflict_types": sorted({str(conflict.conflict_type) for conflict in conflicts}),
                        "conflict_ids": [int(conflict.id) for conflict in conflicts if conflict.id is not None],
                    },
                )
            )

        if not has_cover_scan:
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=None,
                    risk_type="needs_scan",
                    priority="medium",
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={"has_cover_scan": False},
                )
            )

        if cover_processing_failed:
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="needs_cover_processing_review",
                    priority="critical",
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "processing_status": "failed",
                        "primary_cover_image_id": primary_cover_id,
                    },
                )
            )

        if ocr_failed:
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="needs_ocr_retry",
                    priority="high",
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "ocr_processing_status": "failed",
                        "ocr_result_id": int(ocr_row.id) if ocr_row and ocr_row.id is not None else None,
                        "primary_cover_image_id": primary_cover_id,
                    },
                )
            )

        if preorder_missing_calendar:
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="preorder_missing_release_date",
                    priority="low",
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "release_date": None if row.release_date is None else str(row.release_date),
                        "release_year": row.release_year,
                    },
                )
            )

        if ownership_state == "ordered_not_received" and row.release_status == "released":
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="released_not_received",
                    priority="high",
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "release_status": row.release_status,
                        "order_status": row.order_status,
                        "received_at": None if row.received_at is None else str(row.received_at),
                    },
                )
            )

        if inv_id in duplicate_groups_by_inventory:
            classification = duplicate_class_by_inventory.get(inv_id, "intentional_multi_copy")
            priority = "medium"
            if classification == "unresolved_duplicate":
                priority = "critical"
            elif classification in ("probable_accidental_duplicate", "duplicate_scan_only"):
                priority = "high"
            risk_rows.append(
                _new_risk(
                    inventory_copy_id=inv_id,
                    cover_image_id=primary_cover_id,
                    risk_type="duplicate_uncertainty",
                    priority=priority,  # type: ignore[arg-type]
                    ownership_state=ownership_state,
                    publisher=row.publisher,
                    title=row.title,
                    issue_number=row.issue_number,
                    evidence_json={
                        "duplicate_group_keys": duplicate_groups_by_inventory.get(inv_id, []),
                        "duplicate_classification": classification,
                    },
                )
            )

        if inv_id in run_groups_by_inventory:
            groups = run_groups_by_inventory[inv_id]
            gap_series = [
                {
                    "series_key": series_key,
                    "series_status": series_status,
                    "missing_issue_numbers": gaps,
                    "pending_issue_numbers": pending,
                }
                for series_key, series_status, gaps, pending in groups
            ]
            if any(item["missing_issue_numbers"] for item in gap_series):
                severity = "medium"
                if any(item["series_status"] == "incomplete_limited_series" for item in gap_series):
                    severity = "high"
                risk_rows.append(
                    _new_risk(
                        inventory_copy_id=inv_id,
                        cover_image_id=primary_cover_id,
                        risk_type="run_gap_detected",
                        priority=severity,  # type: ignore[arg-type]
                        ownership_state=ownership_state,
                        publisher=row.publisher,
                        title=row.title,
                        issue_number=row.issue_number,
                        evidence_json={
                            "series_groups": gap_series,
                        },
                    )
                )

        quality_rows = quality_by_cover.get(primary_cover_id or -1, []) if primary_cover_id is not None else []
        if quality_rows:
            if any(row.severity in ("warning", "critical") for row in quality_rows):
                severity = "medium"
                if any(row.severity == "critical" for row in quality_rows):
                    severity = "critical"
                risk_rows.append(
                    _new_risk(
                        inventory_copy_id=inv_id,
                        cover_image_id=primary_cover_id,
                        risk_type="low_quality_scan",
                        priority=severity,  # type: ignore[arg-type]
                        ownership_state=ownership_state,
                        publisher=row.publisher,
                        title=row.title,
                        issue_number=row.issue_number,
                        evidence_json={
                            "analysis_count": len(quality_rows),
                            "severity_levels": sorted({str(item.severity) for item in quality_rows}),
                            "quality_types": sorted({str(item.quality_type) for item in quality_rows}),
                            "analysis_ids": [int(item.id) for item in quality_rows if item.id is not None],
                        },
                    )
                )

        match_rows = match_by_cover.get(primary_cover_id or -1, []) if primary_cover_id is not None else []
        if match_rows:
            high_conf_matches = [
                item
                for item in match_rows
                if item.confidence_bucket in ("high", "very_high")
            ]
            if high_conf_matches:
                highest = high_conf_matches[0]
                risk_rows.append(
                    _new_risk(
                        inventory_copy_id=inv_id,
                        cover_image_id=primary_cover_id,
                        risk_type="high_confidence_match_unreviewed",
                        priority="high",
                        ownership_state=ownership_state,
                        publisher=row.publisher,
                        title=row.title,
                        issue_number=row.issue_number,
                        evidence_json={
                            "candidate_count": len(high_conf_matches),
                            "confidence_buckets": sorted({str(item.confidence_bucket) for item in high_conf_matches}),
                            "candidate_ids": [int(item.id) for item in high_conf_matches if item.id is not None],
                            "top_candidate": {
                                "candidate_cover_image_id": int(highest.candidate_cover_image_id),
                                "candidate_type": str(highest.candidate_type),
                                "confidence_bucket": str(highest.confidence_bucket),
                                "normalized_confidence_score": float(highest.normalized_confidence_score),
                            },
                        },
                    )
                )

    risk_rows.sort(
        key=lambda item: (
            _PRIORITY_ORDER[item.priority],
            item.risk_type,
            item.inventory_copy_id,
        )
    )
    for item in risk_rows:
        risks_by_inventory[item.inventory_copy_id].append(item)
    return risk_rows, dict(risks_by_inventory)


def _risk_filter_matches(
    risk: InventoryRiskRead,
    *,
    priority: InventoryRiskPriority | None,
    risk_type: InventoryRiskType | None,
    ownership_state: str | None,
    publisher: str | None,
    in_hand_only: bool,
    open_only: bool,
) -> bool:
    if priority is not None and risk.priority != priority:
        return False
    if risk_type is not None and risk.risk_type != risk_type:
        return False
    if ownership_state is not None and risk.ownership_state != ownership_state:
        return False
    if publisher is not None and risk.publisher != publisher:
        return False
    if in_hand_only and risk.ownership_state != "in_hand":
        return False
    if open_only and risk.status != "open":
        return False
    return True


def _summary_from_risks(
    *,
    scope_user_id: int | None,
    scope: str,
    risks: list[InventoryRiskRead],
    total_inventory_copies: int,
) -> InventoryRiskSummary:
    by_priority: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    highest_by_inventory: dict[int, InventoryRiskPriority] = {}
    risks_by_inventory: defaultdict[int, list[InventoryRiskRead]] = defaultdict(list)
    for risk in risks:
        by_priority[risk.priority] += 1
        by_type[risk.risk_type] += 1
        risks_by_inventory[risk.inventory_copy_id].append(risk)
        if risk.inventory_copy_id not in highest_by_inventory:
            highest_by_inventory[risk.inventory_copy_id] = risk.priority
        else:
            highest_by_inventory[risk.inventory_copy_id] = _priority_max(
                highest_by_inventory[risk.inventory_copy_id],
                risk.priority,
            )

    summary = InventoryRiskSummary(
        scope_user_id=scope_user_id,
        scope=scope,
        generated_as_of_date=date.today().isoformat(),
        total_inventory_copies=total_inventory_copies,
        total_risk_items=len(risks),
        copies_with_risk=len(risks_by_inventory),
        critical_copies=sum(1 for pri in highest_by_inventory.values() if pri == "critical"),
        high_copies=sum(1 for pri in highest_by_inventory.values() if pri == "high"),
        medium_copies=sum(1 for pri in highest_by_inventory.values() if pri == "medium"),
        low_copies=sum(1 for pri in highest_by_inventory.values() if pri == "low"),
        info_copies=sum(1 for pri in highest_by_inventory.values() if pri == "info"),
        by_priority=[KeyedCount(key=key, count=by_priority[key]) for key in ("critical", "high", "medium", "low", "info") if key in by_priority],
        by_risk_type=[KeyedCount(key=key, count=by_type[key]) for key in sorted(by_type.keys())],
    )

    top_items: list[InventoryRiskSummaryItem] = []
    for inv_id, items in risks_by_inventory.items():
        ordered = sorted(items, key=lambda item: (_PRIORITY_ORDER[item.priority], item.risk_type, item.cover_image_id or -1))
        top = ordered[0]
        top_items.append(
            InventoryRiskSummaryItem(
                inventory_copy_id=inv_id,
                publisher=top.publisher,
                title=top.title,
                issue_number=top.issue_number,
                ownership_state=top.ownership_state,
                highest_priority=highest_by_inventory[inv_id],
                risk_count=len(items),
                risk_types=sorted({item.risk_type for item in items}),
                evidence_preview=[f"{item.risk_type}: {item.priority}" for item in ordered[:3]],
            )
        )
    top_items.sort(
        key=lambda item: (
            _PRIORITY_ORDER[item.highest_priority],
            -item.risk_count,
            item.publisher,
            item.title,
            item.inventory_copy_id,
        )
    )
    summary.top_action_items = top_items[:10]
    return summary


def compute_inventory_risks(
    session: Session,
    *,
    current_user: User | None,
    priority: InventoryRiskPriority | None = None,
    risk_type: InventoryRiskType | None = None,
    ownership_state: str | None = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> tuple[InventoryRiskSummary, list[InventoryRiskRead], dict[int, list[InventoryRiskRead]]]:
    user_id = int(current_user.id) if current_user is not None and current_user.id is not None else None
    scope = "owner" if current_user is not None else "ops"
    rows = _inventory_projection_rows(session, user_id=user_id)
    total_inventory_copies = len(rows)
    all_risks, risks_by_inventory = _aggregate_risks(rows, session=session, current_user=current_user)
    filtered = [
        risk
        for risk in all_risks
        if _risk_filter_matches(
            risk,
            priority=priority,
            risk_type=risk_type,
            ownership_state=ownership_state,
            publisher=publisher,
            in_hand_only=in_hand_only,
            open_only=open_only,
        )
    ]
    filtered_by_inventory: defaultdict[int, list[InventoryRiskRead]] = defaultdict(list)
    for risk in filtered:
        filtered_by_inventory[risk.inventory_copy_id].append(risk)
    summary = _summary_from_risks(
        scope_user_id=user_id,
        scope=scope,
        risks=filtered,
        total_inventory_copies=total_inventory_copies,
    )
    return summary, filtered, dict(filtered_by_inventory)


def inventory_risks_for_inventory(
    session: Session,
    *,
    current_user: User | None,
    inventory_copy_id: int,
    priority: InventoryRiskPriority | None = None,
    risk_type: InventoryRiskType | None = None,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    summary, risks, _ = compute_inventory_risks(
        session,
        current_user=current_user,
        priority=priority,
        risk_type=risk_type,
        open_only=open_only,
    )
    filtered = [risk for risk in risks if risk.inventory_copy_id == inventory_copy_id]
    if current_user is not None:
        if current_user.id is None:
            raise HTTPException(status_code=404, detail="Inventory copy not found")
        owned_ids = {int(row.inventory_copy_id) for row in _inventory_projection_rows(session, user_id=int(current_user.id))}
        if inventory_copy_id not in owned_ids:
            raise HTTPException(status_code=404, detail="Inventory copy not found")
    else:
        all_ids = {int(row.inventory_copy_id) for row in _inventory_projection_rows(session, user_id=None)}
        if inventory_copy_id not in all_ids:
            raise HTTPException(status_code=404, detail="Inventory copy not found")
    if filtered:
        risk_owner = filtered[0].ownership_state
        publisher = filtered[0].publisher
    else:
        row = next((row for row in _inventory_projection_rows(session, user_id=int(current_user.id) if current_user and current_user.id is not None else None) if row.inventory_copy_id == inventory_copy_id), None)
        if row is None:
            raise HTTPException(status_code=404, detail="Inventory copy not found")
        risk_owner = normalize_ownership_state(
            release_status=row.release_status,
            order_status=row.order_status,
            received_at=row.received_at,
        )
        publisher = row.publisher
    return InventoryRiskListResponse(
        scope_user_id=int(current_user.id) if current_user is not None and current_user.id is not None else None,
        scope="owner" if current_user is not None else "ops",
        generated_as_of_date=date.today().isoformat(),
        total_count=len(filtered),
        priority=priority or "all",
        risk_type=risk_type or "all",
        ownership_state=risk_owner,
        publisher=publisher,
        in_hand_only=False,
        open_only=open_only,
        summary=summary,
        risks=filtered,
    )


def get_inventory_risks_owner(
    session: Session,
    *,
    user: User,
    priority: InventoryRiskPriority | None = None,
    risk_type: InventoryRiskType | None = None,
    ownership_state: str | None = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    summary, risks, _ = compute_inventory_risks(
        session,
        current_user=user,
        priority=priority,
        risk_type=risk_type,
        ownership_state=ownership_state,
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
    )
    return InventoryRiskListResponse(
        scope_user_id=int(user.id) if user.id is not None else None,
        scope="owner",
        generated_as_of_date=summary.generated_as_of_date,
        total_count=len(risks),
        priority=priority or "all",
        risk_type=risk_type or "all",
        ownership_state=ownership_state or "all",
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
        summary=summary,
        risks=risks,
    )


def get_inventory_risks_ops(
    session: Session,
    *,
    priority: InventoryRiskPriority | None = None,
    risk_type: InventoryRiskType | None = None,
    ownership_state: str | None = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    summary, risks, _ = compute_inventory_risks(
        session,
        current_user=None,
        priority=priority,
        risk_type=risk_type,
        ownership_state=ownership_state,
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
    )
    return InventoryRiskListResponse(
        scope_user_id=None,
        scope="ops",
        generated_as_of_date=summary.generated_as_of_date,
        total_count=len(risks),
        priority=priority or "all",
        risk_type=risk_type or "all",
        ownership_state=ownership_state or "all",
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
        summary=summary,
        risks=risks,
    )


def get_inventory_risk_detail_owner(
    session: Session,
    *,
    user: User,
    inventory_copy_id: int,
    priority: InventoryRiskPriority | None = None,
    risk_type: InventoryRiskType | None = None,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    projection_row = _projection_row_for_inventory(
        session,
        current_user=user,
        inventory_copy_id=inventory_copy_id,
    )
    if projection_row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    response = get_inventory_risks_owner(
        session,
        user=user,
        priority=priority,
        risk_type=risk_type,
        open_only=open_only,
    )
    risks = [risk for risk in response.risks if risk.inventory_copy_id == inventory_copy_id]
    response.risks = risks
    response.total_count = len(risks)
    response.summary = _summary_from_risks(
        scope_user_id=response.scope_user_id,
        scope=response.scope,
        risks=risks,
        total_inventory_copies=1,
    )
    response.ownership_state = normalize_ownership_state(
        release_status=projection_row.release_status,
        order_status=projection_row.order_status,
        received_at=projection_row.received_at,
    )
    response.publisher = projection_row.publisher
    return response


def get_inventory_risk_detail_ops(
    session: Session,
    *,
    inventory_copy_id: int,
    priority: InventoryRiskPriority | None = None,
    risk_type: InventoryRiskType | None = None,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    projection_row = _projection_row_for_inventory(
        session,
        current_user=None,
        inventory_copy_id=inventory_copy_id,
    )
    if projection_row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    response = get_inventory_risks_ops(
        session,
        priority=priority,
        risk_type=risk_type,
        open_only=open_only,
    )
    risks = [risk for risk in response.risks if risk.inventory_copy_id == inventory_copy_id]
    response.risks = risks
    response.total_count = len(risks)
    response.summary = _summary_from_risks(
        scope_user_id=response.scope_user_id,
        scope=response.scope,
        risks=risks,
        total_inventory_copies=1,
    )
    response.ownership_state = normalize_ownership_state(
        release_status=projection_row.release_status,
        order_status=projection_row.order_status,
        received_at=projection_row.received_at,
    )
    response.publisher = projection_row.publisher
    return response

