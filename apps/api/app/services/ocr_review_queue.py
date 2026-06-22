"""Centralized OCR human-review queue reads (deterministic UNION queries + summaries + safe bulk wrappers)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Literal

from fastapi import HTTPException
from sqlalchemy import Float, asc, cast, desc, func, literal, union_all
from sqlalchemy import and_, case as sa_case, or_
from sqlmodel import Session, select

from app.models import (
    CatalogPublisher,
    ComicIssue,
    ComicTitle,
    CoverImage,
    CoverImageBarcodeCandidate,
    CoverImageMatchCandidate,
    CoverImageOcrCandidate,
    CoverImageOcrQualityAnalysis,
    CoverImageOcrReconciliationWarning,
    DraftImport,
    InventoryCopy,
    OcrBatch,
    OcrReplayRun,
    Publisher,
    User,
    Variant,
)
from app.services.inventory_canonical_spine import apply_inventory_spine_joins
from app.schemas.ocr_review_queue import (
    BulkIdsPayload,
    BulkMutationResult,
    OcrReviewQueueResponse,
    OcrReviewSummaryResponse,
    OcrReviewQueueItem,
)
from app.services.cover_images import (
    acknowledge_ocr_reconciliation_warning_for_ops,
    acknowledge_ocr_reconciliation_warning_for_owner,
    approve_cover_image_barcode_candidate_for_ops,
    approve_cover_image_barcode_candidate_for_owner,
    cover_barcode_candidate_entity_to_read,
    cover_match_candidate_entity_to_read,
    cover_ocr_candidate_entity_to_read,
    cover_ocr_quality_analysis_entity_to_read,
    cover_ocr_reconciliation_warning_entity_to_read,
    dismiss_ocr_reconciliation_warning_for_ops,
    dismiss_ocr_reconciliation_warning_for_owner,
    reject_cover_image_barcode_candidate_for_ops,
    reject_cover_image_barcode_candidate_for_owner,
)

_KIND_OCR = "ocr_candidate"
_KIND_WARN = "reconciliation_warning"
_KIND_BARCODE = "barcode_candidate"
_KIND_MATCH = "match_candidate"
_KIND_QUALITY = "ocr_quality_analysis"
_ALL_KINDS: frozenset[str] = frozenset(
    {_KIND_OCR, _KIND_WARN, _KIND_BARCODE, _KIND_MATCH, _KIND_QUALITY}
)


def parse_item_kinds(values: Iterable[str] | None) -> frozenset[str]:
    if values is None:
        return _ALL_KINDS
    out: set[str] = set()
    for raw in values:
        trimmed = raw.strip()
        if not trimmed:
            continue
        if trimmed not in _ALL_KINDS:
            raise HTTPException(status_code=400, detail=f"Unsupported OCR review item_kind: {trimmed}")
        out.add(trimmed)
    return frozenset(out) if out else _ALL_KINDS


def _owner_uid_clause():
    return sa_case(
        (CoverImage.inventory_copy_id.is_not(None), InventoryCopy.user_id),
        else_=DraftImport.user_id,
    )


def _confidence_bucket_float(value: float | None) -> Literal["high", "medium", "low", "unknown"]:
    if value is None:
        return "unknown"
    if value >= 0.75:
        return "high"
    if value >= 0.40:
        return "medium"
    return "low"


def _ocr_barcode_bucket_tier_expression(conf_col):
    return sa_case(
        (conf_col >= 0.75, 0),
        (conf_col >= 0.40, 1),
        (conf_col.is_(None), 3),
        else_=2,
    )


def _match_bucket_tier_expression():
    return sa_case(
        (CoverImageMatchCandidate.confidence_bucket == "very_high", 0),
        (CoverImageMatchCandidate.confidence_bucket == "high", 1),
        (CoverImageMatchCandidate.confidence_bucket == "medium", 2),
        (CoverImageMatchCandidate.confidence_bucket == "low", 3),
        else_=4,
    )


def _warning_severity_tier_expression():
    return sa_case(
        (CoverImageOcrReconciliationWarning.severity == "critical", 0),
        (CoverImageOcrReconciliationWarning.severity == "warning", 1),
        else_=2,
    )


def _quality_severity_tier_expression():
    return sa_case(
        (CoverImageOcrQualityAnalysis.severity == "critical", 0),
        (CoverImageOcrQualityAnalysis.severity == "warning", 1),
        else_=2,
    )


def _confidence_numeric_predicate(column: Any, bucket: Literal["high", "medium", "low", "unknown"]) -> Any:
    if bucket == "high":
        return column >= 0.75
    if bucket == "medium":
        return (column >= 0.40) & (column < 0.75)
    if bucket == "low":
        return (column.is_not(None)) & (column < 0.40)
    return column.is_(None)


def _apply_publisher_filter(stmt: Any, publisher_id: int | None) -> Any:
    if publisher_id is None:
        return stmt
    stmt = apply_inventory_spine_joins(stmt)
    return stmt.where(
        or_(
            Publisher.id == publisher_id,
            CatalogPublisher.id == publisher_id,
        )
    )


@dataclass
class OcrReviewQueueFilters:
    queue_scope: Literal["attention", "all"]
    kinds: frozenset[str]
    ops_mode: bool
    owner_user_id: int | None

    publisher_id: int | None = None
    extraction_version: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None

    confidence_bucket: Literal["high", "medium", "low", "unknown"] | None = None
    severity: Literal["critical", "warning", "info"] | None = None

    candidate_type: str | None = None
    warning_type: str | None = None
    quality_type: str | None = None

    ocr_candidate_review_status: Literal["pending", "approved", "rejected"] | None = None
    warning_status: Literal["open", "acknowledged", "dismissed"] | None = None
    barcode_review_state: Literal["pending", "approved", "rejected"] | None = None
    match_review: Literal["pending", "acknowledged", "dismissed"] | None = None


def _effective_ocr_review_status(filters: OcrReviewQueueFilters) -> list[str] | None:
    if filters.ocr_candidate_review_status is not None:
        return [filters.ocr_candidate_review_status]
    if filters.queue_scope == "attention":
        return ["pending"]
    return None


def _effective_warning_status(filters: OcrReviewQueueFilters) -> list[str] | None:
    if filters.warning_status is not None:
        return [filters.warning_status]
    if filters.queue_scope == "attention":
        return ["open"]
    return None


def _effective_barcode_state(filters: OcrReviewQueueFilters) -> list[str] | None:
    if filters.barcode_review_state is not None:
        return [filters.barcode_review_state]
    if filters.queue_scope == "attention":
        return ["pending"]
    return None


def _match_preds(filters: OcrReviewQueueFilters) -> list[Any]:
    preds: list[Any] = []
    mr = filters.match_review
    if mr is not None:
        if mr == "pending":
            preds.extend(
                [
                    CoverImageMatchCandidate.dismissed_at.is_(None),
                    CoverImageMatchCandidate.acknowledged_at.is_(None),
                ]
            )
        elif mr == "acknowledged":
            preds.append(CoverImageMatchCandidate.acknowledged_at.is_not(None))
        elif mr == "dismissed":
            preds.append(CoverImageMatchCandidate.dismissed_at.is_not(None))
    elif filters.queue_scope == "attention":
        preds.extend(
            [
                CoverImageMatchCandidate.dismissed_at.is_(None),
                CoverImageMatchCandidate.acknowledged_at.is_(None),
            ]
        )
    return preds


def _match_confidence_bucket_predicate(bucket: str) -> Any:
    if bucket == "high":
        return CoverImageMatchCandidate.confidence_bucket.in_(("very_high", "high"))
    if bucket == "medium":
        return CoverImageMatchCandidate.confidence_bucket == "medium"
    if bucket == "low":
        return CoverImageMatchCandidate.confidence_bucket.in_(("low", "very_low"))
    return CoverImageMatchCandidate.confidence_bucket == bucket


def _quality_predicates(filters: OcrReviewQueueFilters) -> list[Any]:
    preds: list[Any] = []
    if filters.severity is not None:
        preds.append(CoverImageOcrQualityAnalysis.severity == filters.severity)
    elif filters.queue_scope == "attention":
        preds.append(CoverImageOcrQualityAnalysis.severity.in_(("warning", "critical")))
    if filters.quality_type is not None:
        preds.append(CoverImageOcrQualityAnalysis.quality_type == filters.quality_type.strip())
    if filters.extraction_version is not None:
        preds.append(CoverImageOcrQualityAnalysis.extraction_version == filters.extraction_version.strip())
    return preds


def _append_created(predicate_col, filters: OcrReviewQueueFilters, bucket: list[Any]) -> None:
    if filters.created_after is not None:
        bucket.append(predicate_col >= filters.created_after)
    if filters.created_before is not None:
        bucket.append(predicate_col <= filters.created_before)


def _cover_access_preds(filters: OcrReviewQueueFilters) -> list[Any]:
    preds: list[Any] = [
        or_(
            CoverImage.inventory_copy_id.is_not(None),
            CoverImage.draft_import_id.is_not(None),
        ),
    ]
    if not filters.ops_mode and filters.owner_user_id is not None:
        preds.append(_owner_uid_clause() == filters.owner_user_id)
    return preds


def _scalar_branch_count(session: Session, branch: Any | None) -> int:
    if branch is None:
        return 0
    return int(
        session.execute(select(func.count()).select_from(branch.subquery())).scalar_one(),
    )


def _branch_ocr(filters: OcrReviewQueueFilters) -> Any | None:
    if _KIND_OCR not in filters.kinds:
        return None
    preds = _cover_access_preds(filters)
    statuses = _effective_ocr_review_status(filters)
    if statuses is not None:
        preds.append(CoverImageOcrCandidate.review_status.in_(statuses))
    if filters.candidate_type:
        preds.append(CoverImageOcrCandidate.candidate_type == filters.candidate_type.strip())
    if filters.extraction_version:
        preds.append(CoverImageOcrCandidate.extraction_version == filters.extraction_version.strip())
    if filters.confidence_bucket is not None:
        preds.append(
            _confidence_numeric_predicate(CoverImageOcrCandidate.confidence_score, filters.confidence_bucket)
        )
    _append_created(CoverImageOcrCandidate.created_at, filters, preds)

    stmt = (
        select(
            literal(_KIND_OCR).label("item_kind"),
            CoverImageOcrCandidate.id.label("entity_id"),
            CoverImageOcrCandidate.cover_image_id.label("cover_image_id"),
            _ocr_barcode_bucket_tier_expression(CoverImageOcrCandidate.confidence_score).label("sort_tier"),
            cast(
                func.coalesce(CoverImageOcrCandidate.confidence_score, -1.0),
                Float,
            ).label("norm_score"),
            CoverImageOcrCandidate.created_at.label("created_at"),
            CoverImageOcrCandidate.id.label("tie_break_id"),
        )
        .select_from(CoverImageOcrCandidate)
        .join(CoverImage, CoverImage.id == CoverImageOcrCandidate.cover_image_id)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
    )
    stmt = _apply_publisher_filter(stmt, filters.publisher_id)
    return stmt.where(and_(*preds))


def _branch_warning(filters: OcrReviewQueueFilters) -> Any | None:
    if _KIND_WARN not in filters.kinds:
        return None
    preds = _cover_access_preds(filters)
    statuses = _effective_warning_status(filters)
    if statuses is not None:
        preds.append(CoverImageOcrReconciliationWarning.status.in_(statuses))
    if filters.severity:
        preds.append(CoverImageOcrReconciliationWarning.severity == filters.severity)
    if filters.warning_type:
        preds.append(CoverImageOcrReconciliationWarning.warning_type == filters.warning_type.strip())
    _append_created(CoverImageOcrReconciliationWarning.created_at, filters, preds)

    stmt = (
        select(
            literal(_KIND_WARN).label("item_kind"),
            CoverImageOcrReconciliationWarning.id.label("entity_id"),
            CoverImageOcrReconciliationWarning.cover_image_id.label("cover_image_id"),
            _warning_severity_tier_expression().label("sort_tier"),
            literal(0.0).label("norm_score"),
            CoverImageOcrReconciliationWarning.created_at.label("created_at"),
            CoverImageOcrReconciliationWarning.id.label("tie_break_id"),
        )
        .select_from(CoverImageOcrReconciliationWarning)
        .join(CoverImage, CoverImage.id == CoverImageOcrReconciliationWarning.cover_image_id)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
    )
    stmt = _apply_publisher_filter(stmt, filters.publisher_id)
    return stmt.where(and_(*preds))


def _branch_barcode(filters: OcrReviewQueueFilters) -> Any | None:
    if _KIND_BARCODE not in filters.kinds:
        return None
    preds = _cover_access_preds(filters)
    statuses = _effective_barcode_state(filters)
    if statuses is not None:
        preds.append(CoverImageBarcodeCandidate.review_state.in_(statuses))
    if filters.extraction_version:
        preds.append(CoverImageBarcodeCandidate.extraction_version == filters.extraction_version.strip())
    if filters.confidence_bucket is not None:
        preds.append(_confidence_numeric_predicate(CoverImageBarcodeCandidate.confidence, filters.confidence_bucket))
    _append_created(CoverImageBarcodeCandidate.created_at, filters, preds)

    stmt = (
        select(
            literal(_KIND_BARCODE).label("item_kind"),
            CoverImageBarcodeCandidate.id.label("entity_id"),
            CoverImageBarcodeCandidate.cover_image_id.label("cover_image_id"),
            _ocr_barcode_bucket_tier_expression(CoverImageBarcodeCandidate.confidence).label("sort_tier"),
            cast(
                func.coalesce(CoverImageBarcodeCandidate.confidence, -1.0),
                Float,
            ).label("norm_score"),
            CoverImageBarcodeCandidate.created_at.label("created_at"),
            CoverImageBarcodeCandidate.id.label("tie_break_id"),
        )
        .select_from(CoverImageBarcodeCandidate)
        .join(CoverImage, CoverImage.id == CoverImageBarcodeCandidate.cover_image_id)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
    )
    stmt = _apply_publisher_filter(stmt, filters.publisher_id)
    return stmt.where(and_(*preds))


def _branch_match(filters: OcrReviewQueueFilters) -> Any | None:
    if _KIND_MATCH not in filters.kinds:
        return None
    preds = _cover_access_preds(filters)
    preds.extend(_match_preds(filters))
    if filters.candidate_type:
        preds.append(CoverImageMatchCandidate.candidate_type == filters.candidate_type.strip())
    if filters.extraction_version:
        preds.append(CoverImageMatchCandidate.extraction_version == filters.extraction_version.strip())
    if filters.confidence_bucket is not None:
        preds.append(_match_confidence_bucket_predicate(filters.confidence_bucket))
    _append_created(CoverImageMatchCandidate.created_at, filters, preds)

    stmt = (
        select(
            literal(_KIND_MATCH).label("item_kind"),
            CoverImageMatchCandidate.id.label("entity_id"),
            CoverImageMatchCandidate.source_cover_image_id.label("cover_image_id"),
            _match_bucket_tier_expression().label("sort_tier"),
            cast(CoverImageMatchCandidate.normalized_confidence_score, Float).label("norm_score"),
            CoverImageMatchCandidate.created_at.label("created_at"),
            CoverImageMatchCandidate.id.label("tie_break_id"),
        )
        .select_from(CoverImageMatchCandidate)
        .join(CoverImage, CoverImage.id == CoverImageMatchCandidate.source_cover_image_id)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
    )
    stmt = _apply_publisher_filter(stmt, filters.publisher_id)
    return stmt.where(and_(*preds))


def _branch_quality(filters: OcrReviewQueueFilters) -> Any | None:
    if _KIND_QUALITY not in filters.kinds:
        return None
    preds = _cover_access_preds(filters)
    preds.extend(_quality_predicates(filters))
    _append_created(CoverImageOcrQualityAnalysis.created_at, filters, preds)

    stmt = (
        select(
            literal(_KIND_QUALITY).label("item_kind"),
            CoverImageOcrQualityAnalysis.id.label("entity_id"),
            CoverImageOcrQualityAnalysis.cover_image_id.label("cover_image_id"),
            _quality_severity_tier_expression().label("sort_tier"),
            cast(CoverImageOcrQualityAnalysis.deterministic_score, Float).label("norm_score"),
            CoverImageOcrQualityAnalysis.created_at.label("created_at"),
            CoverImageOcrQualityAnalysis.id.label("tie_break_id"),
        )
        .select_from(CoverImageOcrQualityAnalysis)
        .join(CoverImage, CoverImage.id == CoverImageOcrQualityAnalysis.cover_image_id)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
    )
    stmt = _apply_publisher_filter(stmt, filters.publisher_id)
    return stmt.where(and_(*preds))


def _build_union(filters: OcrReviewQueueFilters) -> Any:
    parts: list[Any] = []
    for builder in (_branch_ocr, _branch_warning, _branch_barcode, _branch_match, _branch_quality):
        sel = builder(filters)
        if sel is not None:
            parts.append(sel)
    if not parts:
        raise HTTPException(status_code=400, detail="No OCR review item kinds resolved for query")
    return union_all(*parts).subquery("ocr_review_queue_union")


def _hydrate_items(session: Session, mappings: list[Any]) -> list[OcrReviewQueueItem]:
    kind_to_ids: dict[str, list[int]] = defaultdict(list)
    normalized_rows: list[dict[str, Any]] = []
    for mapping in mappings:
        rowdict = dict(mapping)
        kind_to_ids[rowdict["item_kind"]].append(rowdict["entity_id"])
        normalized_rows.append(rowdict)

    ocr_by_id: dict[int, CoverImageOcrCandidate] = {}
    if kind_to_ids[_KIND_OCR]:
        objs = session.exec(
            select(CoverImageOcrCandidate).where(CoverImageOcrCandidate.id.in_(kind_to_ids[_KIND_OCR]))
        ).all()
        ocr_by_id = {int(o.id): o for o in objs if o.id is not None}

    warn_by_id: dict[int, CoverImageOcrReconciliationWarning] = {}
    if kind_to_ids[_KIND_WARN]:
        objs = session.exec(
            select(CoverImageOcrReconciliationWarning).where(
                CoverImageOcrReconciliationWarning.id.in_(kind_to_ids[_KIND_WARN])
            )
        ).all()
        warn_by_id = {int(o.id): o for o in objs if o.id is not None}

    barcode_by_id: dict[int, CoverImageBarcodeCandidate] = {}
    if kind_to_ids[_KIND_BARCODE]:
        objs = session.exec(
            select(CoverImageBarcodeCandidate).where(
                CoverImageBarcodeCandidate.id.in_(kind_to_ids[_KIND_BARCODE])
            )
        ).all()
        barcode_by_id = {int(o.id): o for o in objs if o.id is not None}

    match_by_id: dict[int, CoverImageMatchCandidate] = {}
    if kind_to_ids[_KIND_MATCH]:
        objs = session.exec(
            select(CoverImageMatchCandidate).where(CoverImageMatchCandidate.id.in_(kind_to_ids[_KIND_MATCH]))
        ).all()
        match_by_id = {int(o.id): o for o in objs if o.id is not None}

    quality_by_id: dict[int, CoverImageOcrQualityAnalysis] = {}
    if kind_to_ids[_KIND_QUALITY]:
        objs = session.exec(
            select(CoverImageOcrQualityAnalysis).where(
                CoverImageOcrQualityAnalysis.id.in_(kind_to_ids[_KIND_QUALITY])
            )
        ).all()
        quality_by_id = {int(o.id): o for o in objs if o.id is not None}

    out: list[OcrReviewQueueItem] = []
    for m in normalized_rows:
        kind = m["item_kind"]
        eid = int(m["entity_id"])
        cover_id = int(m["cover_image_id"])
        sort_tier = int(m["sort_tier"])
        norm_score = float(m["norm_score"])
        created_at = m["created_at"]

        if kind == _KIND_OCR:
            obj = ocr_by_id[eid]
            read = cover_ocr_candidate_entity_to_read(obj)
            bucket = _confidence_bucket_float(obj.confidence_score)
            out.append(
                OcrReviewQueueItem(
                    item_kind=kind,
                    entity_id=eid,
                    cover_image_id=cover_id,
                    created_at=created_at,
                    sort_tier=sort_tier,
                    norm_score=None if bucket == "unknown" else obj.confidence_score,
                    extraction_version=obj.extraction_version,
                    candidate_type=obj.candidate_type,
                    confidence_bucket=bucket,
                    ocr_candidate_review_status=obj.review_status,
                    ocr_candidate=read,
                )
            )
        elif kind == _KIND_WARN:
            obj = warn_by_id[eid]
            read = cover_ocr_reconciliation_warning_entity_to_read(obj)
            out.append(
                OcrReviewQueueItem(
                    item_kind=kind,
                    entity_id=eid,
                    cover_image_id=cover_id,
                    created_at=created_at,
                    sort_tier=sort_tier,
                    norm_score=norm_score,
                    severity=obj.severity,
                    warning_type=obj.warning_type,
                    reconciliation_status=obj.status,
                    reconciliation_warning=read,
                )
            )
        elif kind == _KIND_BARCODE:
            obj = barcode_by_id[eid]
            read = cover_barcode_candidate_entity_to_read(obj)
            bucket = _confidence_bucket_float(obj.confidence)
            out.append(
                OcrReviewQueueItem(
                    item_kind=kind,
                    entity_id=eid,
                    cover_image_id=cover_id,
                    created_at=created_at,
                    sort_tier=sort_tier,
                    norm_score=None if bucket == "unknown" else obj.confidence,
                    extraction_version=obj.extraction_version,
                    confidence_bucket=bucket,
                    barcode_review_state=obj.review_state,
                    barcode_candidate=read,
                )
            )
        elif kind == _KIND_MATCH:
            mobj = match_by_id[eid]
            read = cover_match_candidate_entity_to_read(mobj)
            out.append(
                OcrReviewQueueItem(
                    item_kind=kind,
                    entity_id=eid,
                    cover_image_id=cover_id,
                    created_at=created_at,
                    sort_tier=sort_tier,
                    norm_score=norm_score,
                    extraction_version=mobj.extraction_version,
                    candidate_type=mobj.candidate_type,
                    confidence_bucket=mobj.confidence_bucket,
                    acknowledged_at=mobj.acknowledged_at,
                    dismissed_at=mobj.dismissed_at,
                    match_candidate=read,
                )
            )
        elif kind == _KIND_QUALITY:
            obj = quality_by_id[eid]
            read = cover_ocr_quality_analysis_entity_to_read(obj)
            out.append(
                OcrReviewQueueItem(
                    item_kind=kind,
                    entity_id=eid,
                    cover_image_id=cover_id,
                    created_at=created_at,
                    sort_tier=sort_tier,
                    norm_score=norm_score,
                    extraction_version=obj.extraction_version,
                    severity=obj.severity,
                    quality_type=obj.quality_type,
                    ocr_quality_analysis=read,
                )
            )
        else:
            raise HTTPException(status_code=500, detail=f"Unknown OCR review union kind {kind}")

    return out


def list_ocr_review_queue(
    session: Session,
    *,
    filters: OcrReviewQueueFilters,
    page: int,
    page_size: int,
) -> OcrReviewQueueResponse:
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    capped = max(1, min(page_size, 100))

    sq = _build_union(filters)

    total_val = session.execute(select(func.count()).select_from(sq)).scalar_one()
    total = int(total_val)

    stmt = (
        select(sq)
        .order_by(
            asc(sq.c.sort_tier),
            desc(sq.c.norm_score),
            asc(sq.c.created_at),
            asc(sq.c.tie_break_id),
            asc(sq.c.item_kind),
        )
        .offset((page - 1) * capped)
        .limit(capped)
    )
    result = session.execute(stmt)
    mapping_rows = list(result.mappings().all())
    return OcrReviewQueueResponse(
        items=_hydrate_items(session, mapping_rows),
        total=total,
        page=page,
        page_size=capped,
    )


def _summary_attn_base(*, ops_mode: bool, owner_user_id: int | None) -> OcrReviewQueueFilters:
    if not ops_mode and owner_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return OcrReviewQueueFilters(
        queue_scope="attention",
        kinds=_ALL_KINDS,
        ops_mode=ops_mode,
        owner_user_id=None if ops_mode else owner_user_id,
    )


def build_ocr_review_summary(
    session: Session,
    *,
    ops_mode: bool,
    owner_user_id: int | None,
) -> OcrReviewSummaryResponse:
    attn = _summary_attn_base(ops_mode=ops_mode, owner_user_id=owner_user_id)

    pending_ocr = _scalar_branch_count(session, _branch_ocr(attn))

    warn_open_filters = OcrReviewQueueFilters(
        queue_scope="all",
        kinds=frozenset({_KIND_WARN}),
        ops_mode=attn.ops_mode,
        owner_user_id=attn.owner_user_id,
        warning_status="open",
    )
    open_warnings = _scalar_branch_count(session, _branch_warning(warn_open_filters))

    crit_quality = OcrReviewQueueFilters(
        queue_scope="all",
        kinds=frozenset({_KIND_QUALITY}),
        ops_mode=attn.ops_mode,
        owner_user_id=attn.owner_user_id,
        severity="critical",
    )
    critical_quality = _scalar_branch_count(session, _branch_quality(crit_quality))

    high_pending_match = OcrReviewQueueFilters(
        queue_scope="attention",
        kinds=frozenset({_KIND_MATCH}),
        ops_mode=attn.ops_mode,
        owner_user_id=attn.owner_user_id,
        confidence_bucket="high",
    )
    hi_match_pending = _scalar_branch_count(session, _branch_match(high_pending_match))

    batch_stmt = select(func.count(OcrBatch.id)).where(OcrBatch.failed_count > 0)
    if not ops_mode:
        batch_stmt = batch_stmt.where(OcrBatch.created_by == owner_user_id)
    failed_batches = int(session.execute(batch_stmt).scalar_one())

    replay_stmt = select(func.coalesce(func.sum(OcrReplayRun.changed_items), 0)).where(OcrReplayRun.status == "completed")
    if not ops_mode:
        replay_stmt = replay_stmt.where(OcrReplayRun.created_by == owner_user_id)
    replay_total = int(session.execute(replay_stmt).scalar_one())

    return OcrReviewSummaryResponse(
        pending_ocr_candidates=pending_ocr,
        open_reconciliation_warnings=open_warnings,
        critical_ocr_quality_analyses=critical_quality,
        pending_high_bucket_match_candidates=hi_match_pending,
        batches_with_failed_items=failed_batches,
        replay_changed_items_completed_runs_total=replay_total,
    )


def _warn_skip_not_open(session: Session, warning_id: int) -> bool:
    row = session.get(CoverImageOcrReconciliationWarning, warning_id)
    return row is None or row.status != "open"


def bulk_ack_warnings_for_owner(session: Session, *, current_user: User, payload: BulkIdsPayload) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for wid in sorted(set(payload.ids)):
        if _warn_skip_not_open(session, wid):
            skipped[str(wid)] = "missing_or_not_open"
            continue
        try:
            acknowledge_ocr_reconciliation_warning_for_owner(session, current_user=current_user, warning_id=wid)
        except HTTPException as exc:
            skipped[str(wid)] = str(exc.detail)
        else:
            succeeded.append(wid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def bulk_dismiss_warnings_for_owner(session: Session, *, current_user: User, payload: BulkIdsPayload) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for wid in sorted(set(payload.ids)):
        if _warn_skip_not_open(session, wid):
            skipped[str(wid)] = "missing_or_not_open"
            continue
        try:
            dismiss_ocr_reconciliation_warning_for_owner(session, current_user=current_user, warning_id=wid)
        except HTTPException as exc:
            skipped[str(wid)] = str(exc.detail)
        else:
            succeeded.append(wid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def bulk_ack_warnings_for_ops(
    session: Session, *, actor_user_id: int, payload: BulkIdsPayload
) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for wid in sorted(set(payload.ids)):
        if _warn_skip_not_open(session, wid):
            skipped[str(wid)] = "missing_or_not_open"
            continue
        try:
            acknowledge_ocr_reconciliation_warning_for_ops(session, warning_id=wid, actor_user_id=actor_user_id)
        except HTTPException as exc:
            skipped[str(wid)] = str(exc.detail)
        else:
            succeeded.append(wid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def bulk_dismiss_warnings_for_ops(
    session: Session, *, actor_user_id: int, payload: BulkIdsPayload
) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for wid in sorted(set(payload.ids)):
        if _warn_skip_not_open(session, wid):
            skipped[str(wid)] = "missing_or_not_open"
            continue
        try:
            dismiss_ocr_reconciliation_warning_for_ops(session, warning_id=wid, actor_user_id=actor_user_id)
        except HTTPException as exc:
            skipped[str(wid)] = str(exc.detail)
        else:
            succeeded.append(wid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def _barcode_skip_not_pending(session: Session, barcode_id: int) -> bool:
    row = session.get(CoverImageBarcodeCandidate, barcode_id)
    return row is None or row.review_state != "pending"


def bulk_approve_barcodes_for_owner(session: Session, *, current_user: User, payload: BulkIdsPayload) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for bid in sorted(set(payload.ids)):
        if _barcode_skip_not_pending(session, bid):
            skipped[str(bid)] = "missing_or_not_pending"
            continue
        try:
            approve_cover_image_barcode_candidate_for_owner(session, current_user=current_user, barcode_candidate_id=bid)
        except HTTPException as exc:
            skipped[str(bid)] = str(exc.detail)
        else:
            succeeded.append(bid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def bulk_reject_barcodes_for_owner(session: Session, *, current_user: User, payload: BulkIdsPayload) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for bid in sorted(set(payload.ids)):
        if _barcode_skip_not_pending(session, bid):
            skipped[str(bid)] = "missing_or_not_pending"
            continue
        try:
            reject_cover_image_barcode_candidate_for_owner(session, current_user=current_user, barcode_candidate_id=bid)
        except HTTPException as exc:
            skipped[str(bid)] = str(exc.detail)
        else:
            succeeded.append(bid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def bulk_approve_barcodes_for_ops(session: Session, *, actor_user_id: int, payload: BulkIdsPayload) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for bid in sorted(set(payload.ids)):
        if _barcode_skip_not_pending(session, bid):
            skipped[str(bid)] = "missing_or_not_pending"
            continue
        try:
            approve_cover_image_barcode_candidate_for_ops(session, barcode_candidate_id=bid, actor_user_id=actor_user_id)
        except HTTPException as exc:
            skipped[str(bid)] = str(exc.detail)
        else:
            succeeded.append(bid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def bulk_reject_barcodes_for_ops(session: Session, *, actor_user_id: int, payload: BulkIdsPayload) -> BulkMutationResult:
    skipped: dict[str, str] = {}
    succeeded: list[int] = []
    for bid in sorted(set(payload.ids)):
        if _barcode_skip_not_pending(session, bid):
            skipped[str(bid)] = "missing_or_not_pending"
            continue
        try:
            reject_cover_image_barcode_candidate_for_ops(session, barcode_candidate_id=bid, actor_user_id=actor_user_id)
        except HTTPException as exc:
            skipped[str(bid)] = str(exc.detail)
        else:
            succeeded.append(bid)
    return BulkMutationResult(succeeded=succeeded, skipped=skipped)


def build_filters_from_http(
    *,
    queue_scope: Literal["attention", "all"],
    ops_mode: bool,
    owner_user_id: int | None,
    item_kind: list[str] | None,
    publisher_id: int | None,
    extraction_version: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    confidence_bucket: Literal["high", "medium", "low", "unknown"] | None,
    severity: Literal["critical", "warning", "info"] | None,
    candidate_type: str | None,
    warning_type: str | None,
    quality_type: str | None,
    ocr_candidate_review_status: Literal["pending", "approved", "rejected"] | None,
    reconciliation_warning_status: Literal["open", "acknowledged", "dismissed"] | None,
    barcode_review_state: Literal["pending", "approved", "rejected"] | None,
    match_review: Literal["pending", "acknowledged", "dismissed"] | None,
) -> OcrReviewQueueFilters:
    if not ops_mode and owner_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    trimmed_version = extraction_version.strip() if extraction_version else None
    ct = candidate_type.strip() if candidate_type else None
    wt = warning_type.strip() if warning_type else None
    qt = quality_type.strip() if quality_type else None
    return OcrReviewQueueFilters(
        queue_scope=queue_scope,
        kinds=parse_item_kinds(item_kind),
        ops_mode=ops_mode,
        owner_user_id=None if ops_mode else owner_user_id,
        publisher_id=publisher_id,
        extraction_version=trimmed_version or None,
        created_after=created_after,
        created_before=created_before,
        confidence_bucket=confidence_bucket,
        severity=severity,
        candidate_type=ct,
        warning_type=wt,
        quality_type=qt,
        ocr_candidate_review_status=ocr_candidate_review_status,
        warning_status=reconciliation_warning_status,
        barcode_review_state=barcode_review_state,
        match_review=match_review,
    )
