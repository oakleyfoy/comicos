from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketSaleNormalizationIssue,
    MarketSaleRecord,
    MarketSaleReviewAction,
    MarketSource,
)
from app.schemas.market_sales import (
    MarketSaleIssueType,
    MarketSaleNormalizationIssueRead,
    MarketSaleNormalizationUpdatePayload,
    MarketSaleRead,
    MarketSaleReviewActionPayload,
    MarketSaleReviewActionRead,
    MarketSaleReviewClassification,
    MarketSaleReviewPriority,
    MarketSaleReviewQueueItemRead,
    MarketSaleReviewQueueResponse,
    MarketSaleReviewQueueSummaryRead,
    MarketSaleReviewStatus,
)
from app.services.market_sales import (
    SUPPORTED_CURRENCY_CODES,
    _market_sale_detail,
    _market_sale_summary,
    ensure_system_market_sources,
)

_CLASSIFICATION_ORDER: tuple[MarketSaleReviewClassification, ...] = (
    "unsupported_currency",
    "possible_duplicate",
    "needs_price_review",
    "needs_issue_review",
    "needs_title_review",
    "needs_variant_review",
    "needs_grade_review",
    "ready_for_comp_review",
    "ignored",
)

_PRIORITY_BY_CLASSIFICATION: dict[MarketSaleReviewClassification, MarketSaleReviewPriority] = {
    "unsupported_currency": "critical",
    "possible_duplicate": "high",
    "needs_price_review": "high",
    "needs_issue_review": "high",
    "needs_title_review": "medium",
    "needs_variant_review": "medium",
    "needs_grade_review": "medium",
    "ready_for_comp_review": "low",
    "ignored": "info",
}

_PRIORITY_SORT: dict[MarketSaleReviewPriority, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _require_access(*, ops_mode: bool, owner_user_id: int | None) -> None:
    if not ops_mode and owner_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _issue_rows_by_record(session: Session, record_ids: Iterable[int]) -> dict[int, list[MarketSaleNormalizationIssue]]:
    ids = sorted({int(record_id) for record_id in record_ids})
    if not ids:
        return {}
    rows = session.exec(
        select(MarketSaleNormalizationIssue)
        .where(MarketSaleNormalizationIssue.market_sale_record_id.in_(ids))
        .order_by(
            MarketSaleNormalizationIssue.market_sale_record_id.asc(),
            MarketSaleNormalizationIssue.created_at.asc(),
            MarketSaleNormalizationIssue.id.asc(),
        )
    ).all()
    bucket: defaultdict[int, list[MarketSaleNormalizationIssue]] = defaultdict(list)
    for row in rows:
        bucket[int(row.market_sale_record_id)].append(row)
    return dict(bucket)


def _record_snapshot(record: MarketSaleRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "market_source_id": record.market_source_id,
        "source_listing_id": record.source_listing_id,
        "listing_type": record.listing_type,
        "raw_title": record.raw_title,
        "normalized_title": record.normalized_title,
        "raw_issue": record.raw_issue,
        "normalized_issue": record.normalized_issue,
        "raw_publisher": record.raw_publisher,
        "normalized_publisher": record.normalized_publisher,
        "raw_variant": record.raw_variant,
        "normalized_variant": record.normalized_variant,
        "raw_grade": record.raw_grade,
        "normalized_grade": record.normalized_grade,
        "raw_cert_number": record.raw_cert_number,
        "normalized_cert_number": record.normalized_cert_number,
        "sale_price": str(record.sale_price) if record.sale_price is not None else None,
        "shipping_price": str(record.shipping_price) if record.shipping_price is not None else None,
        "total_price": str(record.total_price) if record.total_price is not None else None,
        "currency_code": record.currency_code,
        "sale_date": record.sale_date.isoformat() if record.sale_date is not None else None,
        "is_graded": record.is_graded,
        "grading_company": record.grading_company,
        "is_signed": record.is_signed,
        "normalization_status": record.normalization_status,
        "review_status": record.review_status,
        "updated_at": record.updated_at.isoformat() if record.updated_at is not None else None,
    }


def _market_sale_review_action_read(row: MarketSaleReviewAction) -> MarketSaleReviewActionRead:
    return MarketSaleReviewActionRead.model_validate(row, from_attributes=True)


def _classification_for_record(
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
) -> tuple[MarketSaleReviewClassification, list[str]]:
    issue_types = [str(row.issue_type) for row in issue_rows]
    issue_set = set(issue_types)
    review_status = record.review_status
    normalized_title = record.normalized_title
    normalized_issue = record.normalized_issue
    normalized_variant = record.normalized_variant
    normalized_grade = record.normalized_grade

    reasons: list[str] = []

    if review_status == "ignored" or record.normalization_status == "ignored":
        return "ignored", ["review_status_ignored"]

    if review_status == "duplicate_flagged":
        reasons.append("review_status_duplicate_flagged")
        return "possible_duplicate", reasons

    if "unsupported_currency" in issue_set or record.currency_code.upper() not in SUPPORTED_CURRENCY_CODES:
        reasons.append("unsupported_currency")
        return "unsupported_currency", reasons

    if "duplicate_listing" in issue_set:
        reasons.append("duplicate_listing")
        return "possible_duplicate", reasons

    if record.sale_price is None or record.total_price is None or "missing_sale_price" in issue_set:
        if record.sale_price is None:
            reasons.append("missing_sale_price_value")
        if record.total_price is None:
            reasons.append("missing_total_price_value")
        if "missing_sale_price" in issue_set:
            reasons.append("missing_sale_price_issue")
        return "needs_price_review", reasons

    if normalized_title is None or "malformed_title" in issue_set:
        if normalized_title is None:
            reasons.append("missing_normalized_title")
        if "malformed_title" in issue_set:
            reasons.append("malformed_title_issue")
        return "needs_title_review", reasons

    if normalized_issue is None or "missing_issue_number" in issue_set:
        if normalized_issue is None:
            reasons.append("missing_normalized_issue")
        if "missing_issue_number" in issue_set:
            reasons.append("missing_issue_number_issue")
        return "needs_issue_review", reasons

    if record.raw_variant is not None and (normalized_variant is None or "ambiguous_variant" in issue_set):
        if normalized_variant is None:
            reasons.append("missing_normalized_variant")
        if "ambiguous_variant" in issue_set:
            reasons.append("ambiguous_variant_issue")
        return "needs_variant_review", reasons

    if record.raw_grade is not None and (normalized_grade is None or "invalid_grade" in issue_set):
        if normalized_grade is None:
            reasons.append("missing_normalized_grade")
        if "invalid_grade" in issue_set:
            reasons.append("invalid_grade_issue")
        return "needs_grade_review", reasons

    reasons.append("ready_for_comparison")
    return "ready_for_comp_review", reasons


def _priority_for_classification(classification: MarketSaleReviewClassification) -> MarketSaleReviewPriority:
    return _PRIORITY_BY_CLASSIFICATION[classification]


def _queue_item_for_record(
    session: Session,
    *,
    record: MarketSaleRecord,
    source: MarketSource,
    issue_rows: list[MarketSaleNormalizationIssue],
) -> MarketSaleReviewQueueItemRead:
    classification, reasons = _classification_for_record(record, issue_rows)
    summary = _market_sale_summary(record=record, source=source, issue_count=len(issue_rows))
    return MarketSaleReviewQueueItemRead(
        **summary.model_dump(),
        review_status=record.review_status,  # type: ignore[arg-type]
        queue_classification=classification,
        queue_priority=_priority_for_classification(classification),
        queue_reasons=reasons,
        issue_types=[row.issue_type for row in issue_rows],  # type: ignore[list-item]
    )


def _queue_records(session: Session) -> list[tuple[MarketSaleRecord, MarketSource, list[MarketSaleNormalizationIssue], MarketSaleReviewClassification]]:
    ensure_system_market_sources(session)
    rows = session.exec(
        select(MarketSaleRecord, MarketSource)
        .join(MarketSource, MarketSaleRecord.market_source_id == MarketSource.id)
        .order_by(
            MarketSaleRecord.updated_at.desc(),
            MarketSaleRecord.id.asc(),
        )
    ).all()
    record_ids = [int(record.id) for record, _source in rows if record.id is not None]
    issues_by_record = _issue_rows_by_record(session, record_ids)
    out: list[tuple[MarketSaleRecord, MarketSource, list[MarketSaleNormalizationIssue], MarketSaleReviewClassification]] = []
    for record, source in rows:
        issue_rows = issues_by_record.get(int(record.id or 0), [])
        classification, _reasons = _classification_for_record(record, issue_rows)
        out.append((record, source, issue_rows, classification))
    out.sort(
        key=lambda row: (
            _PRIORITY_SORT[_priority_for_classification(row[3])],
            row[0].updated_at or datetime.min.replace(tzinfo=timezone.utc),
            int(row[0].id or 0),
        )
    )
    return out


def list_market_sale_review_queue(
    session: Session,
    *,
    ops_mode: bool,
    owner_user_id: int | None,
    classification: MarketSaleReviewClassification | None = None,
    priority: MarketSaleReviewPriority | None = None,
    review_status: MarketSaleReviewStatus | None = None,
    source: str | None = None,
    source_type: str | None = None,
    issue_type: MarketSaleIssueType | None = None,
) -> MarketSaleReviewQueueResponse:
    _require_access(ops_mode=ops_mode, owner_user_id=owner_user_id)
    items: list[MarketSaleReviewQueueItemRead] = []
    for record, source_row, issue_rows, item_classification in _queue_records(session):
        item_priority = _priority_for_classification(item_classification)
        if classification is not None and item_classification != classification:
            continue
        if priority is not None and item_priority != priority:
            continue
        if review_status is not None and record.review_status != review_status:
            continue
        if source is not None and source.strip().lower() not in {
            source_row.source_name.lower(),
            source_row.source_type.lower(),
        }:
            continue
        if source_type is not None and source_row.source_type != source_type:
            continue
        if issue_type is not None and issue_type not in {row.issue_type for row in issue_rows}:
            continue
        items.append(_queue_item_for_record(session, record=record, source=source_row, issue_rows=issue_rows))
    return MarketSaleReviewQueueResponse(items=items, total=len(items))


def market_sale_review_queue_summary(
    session: Session,
    *,
    ops_mode: bool,
    owner_user_id: int | None,
    classification: MarketSaleReviewClassification | None = None,
    priority: MarketSaleReviewPriority | None = None,
    review_status: MarketSaleReviewStatus | None = None,
    source: str | None = None,
    source_type: str | None = None,
    issue_type: MarketSaleIssueType | None = None,
) -> MarketSaleReviewQueueSummaryRead:
    queue = list_market_sale_review_queue(
        session,
        ops_mode=ops_mode,
        owner_user_id=owner_user_id,
        classification=classification,
        priority=priority,
        review_status=review_status,
        source=source,
        source_type=source_type,
        issue_type=issue_type,
    )
    by_classification: Counter[MarketSaleReviewClassification] = Counter()
    by_priority: Counter[MarketSaleReviewPriority] = Counter()
    for item in queue.items:
        by_classification[item.queue_classification] += 1
        by_priority[item.queue_priority] += 1
    return MarketSaleReviewQueueSummaryRead(
        total=queue.total,
        by_classification={classification: int(by_classification.get(classification, 0)) for classification in _CLASSIFICATION_ORDER},
        by_priority={priority: int(by_priority.get(priority, 0)) for priority in _PRIORITY_SORT},
    )


def list_market_sale_normalization_issues(
    session: Session,
    *,
    market_sale_record_id: int,
    ops_mode: bool,
    owner_user_id: int | None,
) -> list[MarketSaleNormalizationIssueRead]:
    _require_access(ops_mode=ops_mode, owner_user_id=owner_user_id)
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    issue_rows = session.exec(
        select(MarketSaleNormalizationIssue)
        .where(MarketSaleNormalizationIssue.market_sale_record_id == market_sale_record_id)
        .order_by(MarketSaleNormalizationIssue.created_at.asc(), MarketSaleNormalizationIssue.id.asc())
    ).all()
    return [MarketSaleNormalizationIssueRead.model_validate(row, from_attributes=True) for row in issue_rows]


def _market_sale_review_detail(session: Session, *, record: MarketSaleRecord) -> MarketSaleRead:
    detail = _market_sale_detail(session, record=record)
    action_rows = session.exec(
        select(MarketSaleReviewAction)
        .where(MarketSaleReviewAction.market_sale_record_id == record.id)
        .order_by(MarketSaleReviewAction.created_at.asc(), MarketSaleReviewAction.id.asc())
    ).all()
    return MarketSaleRead(**detail.model_dump(exclude={"review_actions"}), review_actions=[_market_sale_review_action_read(row) for row in action_rows])


def get_market_sale_review_detail(
    session: Session,
    *,
    market_sale_record_id: int,
    ops_mode: bool,
    owner_user_id: int | None,
) -> MarketSaleRead:
    _require_access(ops_mode=ops_mode, owner_user_id=owner_user_id)
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    return _market_sale_review_detail(session, record=record)


def _append_review_action(
    session: Session,
    *,
    record: MarketSaleRecord,
    action_type: str,
    actor_user_id: int | None,
    details_json: dict[str, object] | None,
    before_snapshot_json: dict[str, object],
    after_snapshot_json: dict[str, object],
) -> None:
    if record.id is None:
        raise ValueError("market sale record must be flushed before review logging")
    session.add(
        MarketSaleReviewAction(
            market_sale_record_id=record.id,
            action_type=action_type,
            actor_user_id=actor_user_id,
            details_json=dict(details_json or {}),
            before_snapshot_json=before_snapshot_json,
            after_snapshot_json=after_snapshot_json,
            created_at=utc_now(),
        )
    )


def update_market_sale_normalization(
    session: Session,
    *,
    market_sale_record_id: int,
    actor_user_id: int | None,
    payload: MarketSaleNormalizationUpdatePayload,
) -> MarketSaleRead:
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    if payload.normalization_status == "ignored":
        raise HTTPException(status_code=400, detail="Use the ignore endpoint to set normalization_status to ignored")

    before = _record_snapshot(record)
    changed_fields: list[str] = []
    for field_name in (
        "normalized_title",
        "normalized_issue",
        "normalized_publisher",
        "normalized_variant",
        "normalized_grade",
        "normalized_cert_number",
        "normalization_status",
    ):
        if field_name not in payload.model_fields_set:
            continue
        next_value = getattr(payload, field_name)
        if field_name == "normalization_status" and next_value is None:
            continue
        current_value = getattr(record, field_name)
        if current_value != next_value:
            setattr(record, field_name, next_value)
            changed_fields.append(field_name)

    should_mark_reviewed = payload.mark_reviewed or bool(changed_fields)
    if should_mark_reviewed and record.review_status != "reviewed":
        record.review_status = "reviewed"
        changed_fields.append("review_status")

    if not changed_fields and _trim(payload.review_note) is None:
        raise HTTPException(status_code=400, detail="No normalization fields were provided")

    record.updated_at = utc_now()
    session.add(record)
    session.flush()

    after = _record_snapshot(record)
    _append_review_action(
        session,
        record=record,
        action_type="manual_normalization_update" if changed_fields else "mark_reviewed",
        actor_user_id=actor_user_id,
        details_json={
            "changed_fields": sorted(set(changed_fields)),
            "mark_reviewed": payload.mark_reviewed,
            "review_note": _trim(payload.review_note),
        },
        before_snapshot_json=before,
        after_snapshot_json=after,
    )
    session.commit()
    session.refresh(record)
    return _market_sale_review_detail(session, record=record)


def ignore_market_sale_record(
    session: Session,
    *,
    market_sale_record_id: int,
    actor_user_id: int | None,
    payload: MarketSaleReviewActionPayload | None = None,
) -> MarketSaleRead:
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    before = _record_snapshot(record)
    record.review_status = "ignored"
    record.normalization_status = "ignored"
    record.updated_at = utc_now()
    session.add(record)
    session.flush()
    after = _record_snapshot(record)
    _append_review_action(
        session,
        record=record,
        action_type="ignore_record",
        actor_user_id=actor_user_id,
        details_json={"reason": _trim(payload.reason) if payload is not None else None},
        before_snapshot_json=before,
        after_snapshot_json=after,
    )
    session.commit()
    session.refresh(record)
    return _market_sale_review_detail(session, record=record)


def flag_duplicate_market_sale_record(
    session: Session,
    *,
    market_sale_record_id: int,
    actor_user_id: int | None,
    payload: MarketSaleReviewActionPayload | None = None,
) -> MarketSaleRead:
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    before = _record_snapshot(record)
    record.review_status = "duplicate_flagged"
    record.updated_at = utc_now()
    session.add(record)
    session.flush()
    after = _record_snapshot(record)
    _append_review_action(
        session,
        record=record,
        action_type="flag_duplicate",
        actor_user_id=actor_user_id,
        details_json={"reason": _trim(payload.reason) if payload is not None else None},
        before_snapshot_json=before,
        after_snapshot_json=after,
    )
    session.commit()
    session.refresh(record)
    return _market_sale_review_detail(session, record=record)
