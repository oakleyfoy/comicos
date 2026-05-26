from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
import re

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import (
    MarketSaleMatchSuggestion,
    MarketSaleNormalizationIssue,
    MarketSaleRecord,
    MarketSaleReviewAction,
    MarketSource,
)
from app.schemas.market_sale_comp_eligibility import (
    MarketCompEligibilityClassification,
    MarketCompEligibilityStatus,
    MarketSaleCompEligibilityRead,
    MarketSaleCompEligibilitySummaryRead,
    MarketSaleCompEligibilityListResponse,
    comp_eligibility_classification_order,
    comp_eligibility_status_order,
)
from app.schemas.market_sale_match_suggestions import MarketSaleMatchSuggestionRead
from app.schemas.market_sales import (
    MarketSaleNormalizationIssueRead,
    MarketSaleRead,
    MarketSaleReviewActionRead,
)
from app.services.market_sales import SUPPORTED_CURRENCY_CODES, _market_sale_summary, ensure_system_market_sources
from app.services.market_sale_match_suggestions import _match_read

_HIGH_CONFIDENCE_BUCKETS = {"very_high", "high"}
_VALID_GRADING_COMPANIES = {"CGC", "CBCS", "PGX", "OTHER"}
_STATUS_RANK: dict[MarketCompEligibilityStatus, int] = {
    "eligible": 0,
    "needs_review": 1,
    "ineligible": 2,
}
_CLASSIFICATION_RANK: dict[MarketCompEligibilityClassification, int] = {
    classification: idx for idx, classification in enumerate(comp_eligibility_classification_order())
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True)
class _CompEligibilityEvaluation:
    status: MarketCompEligibilityStatus
    classification: MarketCompEligibilityClassification
    reasons: list[str]
    canonical_match_state: str
    canonical_match_suggestion: MarketSaleMatchSuggestion | None
    canonical_match_confidence_bucket: str | None
    canonical_match_review_state: str | None
    canonical_match_score: float | None
    evidence_json: dict[str, object]


def _market_sale_or_404(session: Session, *, market_sale_record_id: int) -> MarketSaleRecord:
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    return record


def _market_source_or_404(session: Session, *, market_source_id: int) -> MarketSource:
    source = session.get(MarketSource, market_source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Market source not found")
    return source


def _issue_rows_by_record(session: Session, record_ids: list[int]) -> dict[int, list[MarketSaleNormalizationIssue]]:
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


def _suggestion_rows_by_record(session: Session, record_ids: list[int]) -> dict[int, list[MarketSaleMatchSuggestion]]:
    ids = sorted({int(record_id) for record_id in record_ids})
    if not ids:
        return {}
    rows = session.exec(
        select(MarketSaleMatchSuggestion)
        .where(MarketSaleMatchSuggestion.market_sale_record_id.in_(ids))
        .order_by(
            MarketSaleMatchSuggestion.market_sale_record_id.asc(),
            MarketSaleMatchSuggestion.deterministic_score.desc(),
            MarketSaleMatchSuggestion.id.asc(),
        )
    ).all()
    bucket: defaultdict[int, list[MarketSaleMatchSuggestion]] = defaultdict(list)
    for row in rows:
        bucket[int(row.market_sale_record_id)].append(row)
    return dict(bucket)


def _review_actions_by_record(session: Session, record_ids: list[int]) -> dict[int, list[MarketSaleReviewAction]]:
    ids = sorted({int(record_id) for record_id in record_ids})
    if not ids:
        return {}
    rows = session.exec(
        select(MarketSaleReviewAction)
        .where(MarketSaleReviewAction.market_sale_record_id.in_(ids))
        .order_by(
            MarketSaleReviewAction.market_sale_record_id.asc(),
            MarketSaleReviewAction.created_at.asc(),
            MarketSaleReviewAction.id.asc(),
        )
    ).all()
    bucket: defaultdict[int, list[MarketSaleReviewAction]] = defaultdict(list)
    for row in rows:
        bucket[int(row.market_sale_record_id)].append(row)
    return dict(bucket)


def _market_sale_read(
    session: Session,
    *,
    record: MarketSaleRecord,
    issue_count: int,
) -> MarketSaleRead:
    source = _market_source_or_404(session, market_source_id=record.market_source_id)
    return _market_sale_summary(record=record, source=source, issue_count=issue_count)


def _is_valid_grade_company(value: str | None) -> bool:
    if value is None:
        return False
    normalized = _trim(value)
    if normalized is None:
        return False
    return normalized.upper() in _VALID_GRADING_COMPANIES


def _is_valid_normalized_grade(value: str | None) -> bool:
    normalized = _trim(value)
    if normalized is None:
        return False
    grade_token = re.sub(r"\s+", "", normalized)
    return bool(grade_token) and any(char.isdigit() for char in grade_token)


def _canonical_match_evaluation(
    suggestions: list[MarketSaleMatchSuggestion],
) -> tuple[str, MarketSaleMatchSuggestion | None]:
    if not suggestions:
        return "missing", None

    approved = next((row for row in suggestions if row.review_state == "approved"), None)
    if approved is not None:
        return "approved", approved

    high_confidence = next(
        (
            row
            for row in suggestions
            if row.review_state == "pending" and row.confidence_bucket in _HIGH_CONFIDENCE_BUCKETS
        ),
        None,
    )
    if high_confidence is not None:
        return "high_confidence", high_confidence

    return "needs_review", suggestions[0]


def _classification_for_record(
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
    suggestions: list[MarketSaleMatchSuggestion],
) -> _CompEligibilityEvaluation:
    issue_types = [str(row.issue_type) for row in issue_rows]
    issue_type_set = set(issue_types)
    reasons: list[str] = []

    if record.review_status == "ignored" or record.normalization_status == "ignored":
        reasons.append("ignored_review_state")
        return _CompEligibilityEvaluation(
            status="ineligible",
            classification="ineligible_ignored_record",
            reasons=reasons,
            canonical_match_state="missing" if not suggestions else "needs_review",
            canonical_match_suggestion=None if not suggestions else suggestions[0],
            canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
            canonical_match_review_state=suggestions[0].review_state if suggestions else None,
            canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
            evidence_json={
                "review_status": record.review_status,
                "normalization_status": record.normalization_status,
                "trigger": "ignored_record",
            },
        )

    if record.sale_price is None and record.total_price is None:
        reasons.append("missing_sale_or_total_price")
        return _CompEligibilityEvaluation(
            status="ineligible",
            classification="ineligible_missing_price",
            reasons=reasons,
            canonical_match_state="missing" if not suggestions else "needs_review",
            canonical_match_suggestion=None if not suggestions else suggestions[0],
            canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
            canonical_match_review_state=suggestions[0].review_state if suggestions else None,
            canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
            evidence_json={
                "sale_price": str(record.sale_price) if record.sale_price is not None else None,
                "total_price": str(record.total_price) if record.total_price is not None else None,
                "trigger": "missing_price",
            },
        )

    normalized_currency = _trim(record.currency_code)
    if normalized_currency is None or normalized_currency.upper() not in SUPPORTED_CURRENCY_CODES:
        reasons.append("unsupported_currency_code")
        return _CompEligibilityEvaluation(
            status="ineligible",
            classification="ineligible_unsupported_currency",
            reasons=reasons,
            canonical_match_state="missing" if not suggestions else "needs_review",
            canonical_match_suggestion=None if not suggestions else suggestions[0],
            canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
            canonical_match_review_state=suggestions[0].review_state if suggestions else None,
            canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
            evidence_json={
                "currency_code": record.currency_code,
                "normalized_currency_code": normalized_currency.upper() if normalized_currency else None,
                "supported_currency_codes": sorted(SUPPORTED_CURRENCY_CODES),
                "trigger": "unsupported_currency",
            },
        )

    if record.review_status == "duplicate_flagged" or (
        "duplicate_listing" in issue_type_set and record.review_status != "reviewed"
    ):
        reasons.append("duplicate_listing")
        return _CompEligibilityEvaluation(
            status="ineligible",
            classification="ineligible_duplicate_listing",
            reasons=reasons,
            canonical_match_state="missing" if not suggestions else "needs_review",
            canonical_match_suggestion=None if not suggestions else suggestions[0],
            canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
            canonical_match_review_state=suggestions[0].review_state if suggestions else None,
            canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
            evidence_json={
                "review_status": record.review_status,
                "normalization_issue_types": issue_types,
                "trigger": "duplicate_listing",
            },
        )

    if record.normalization_status == "normalization_failed":
        reasons.append("normalization_failed")
        return _CompEligibilityEvaluation(
            status="ineligible",
            classification="ineligible_unresolved_identity",
            reasons=reasons,
            canonical_match_state="missing" if not suggestions else "needs_review",
            canonical_match_suggestion=None if not suggestions else suggestions[0],
            canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
            canonical_match_review_state=suggestions[0].review_state if suggestions else None,
            canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
            evidence_json={
                "normalization_status": record.normalization_status,
                "normalization_issue_types": issue_types,
                "trigger": "normalization_failed",
            },
        )

    if record.normalized_title is None or record.normalized_issue is None or record.normalized_publisher is None:
        if record.normalized_title is None:
            reasons.append("missing_normalized_title")
        if record.normalized_issue is None:
            reasons.append("missing_normalized_issue")
        if record.normalized_publisher is None:
            reasons.append("missing_normalized_publisher")
        return _CompEligibilityEvaluation(
            status="ineligible",
            classification="ineligible_unresolved_identity",
            reasons=reasons,
            canonical_match_state="missing" if not suggestions else "needs_review",
            canonical_match_suggestion=None if not suggestions else suggestions[0],
            canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
            canonical_match_review_state=suggestions[0].review_state if suggestions else None,
            canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
            evidence_json={
                "normalized_title": record.normalized_title,
                "normalized_issue": record.normalized_issue,
                "normalized_publisher": record.normalized_publisher,
                "normalization_issue_types": issue_types,
                "trigger": "missing_normalized_identity",
            },
        )

    invalid_grade_reasons: list[str] = []
    if record.is_graded:
        if not _is_valid_grade_company(record.grading_company):
            invalid_grade_reasons.append("invalid_grading_company")
        if not _is_valid_normalized_grade(record.normalized_grade):
            invalid_grade_reasons.append("invalid_normalized_grade")
        if "invalid_grade" in issue_type_set:
            invalid_grade_reasons.append("invalid_grade_issue")
        if invalid_grade_reasons:
            reasons.extend(invalid_grade_reasons)
            return _CompEligibilityEvaluation(
                status="ineligible",
                classification="ineligible_invalid_grade",
                reasons=reasons,
                canonical_match_state="missing" if not suggestions else "needs_review",
                canonical_match_suggestion=None if not suggestions else suggestions[0],
                canonical_match_confidence_bucket=suggestions[0].confidence_bucket if suggestions else None,
                canonical_match_review_state=suggestions[0].review_state if suggestions else None,
                canonical_match_score=suggestions[0].deterministic_score if suggestions else None,
                evidence_json={
                    "is_graded": record.is_graded,
                    "grading_company": record.grading_company,
                    "normalized_grade": record.normalized_grade,
                    "trigger": "invalid_grade",
                },
            )

    canonical_match_state, canonical_match_suggestion = _canonical_match_evaluation(suggestions)
    if canonical_match_state not in {"approved", "high_confidence"}:
        reasons.append("missing_approved_or_high_confidence_canonical_match")
        return _CompEligibilityEvaluation(
            status="needs_review",
            classification="needs_review_before_comp",
            reasons=reasons,
            canonical_match_state=canonical_match_state,
            canonical_match_suggestion=canonical_match_suggestion,
            canonical_match_confidence_bucket=(
                canonical_match_suggestion.confidence_bucket if canonical_match_suggestion is not None else None
            ),
            canonical_match_review_state=(
                canonical_match_suggestion.review_state if canonical_match_suggestion is not None else None
            ),
            canonical_match_score=(
                canonical_match_suggestion.deterministic_score if canonical_match_suggestion is not None else None
            ),
            evidence_json={
                "canonical_match_state": canonical_match_state,
                "canonical_match_suggestion_id": canonical_match_suggestion.id if canonical_match_suggestion else None,
                "canonical_match_review_state": (
                    canonical_match_suggestion.review_state if canonical_match_suggestion else None
                ),
                "canonical_match_confidence_bucket": (
                    canonical_match_suggestion.confidence_bucket if canonical_match_suggestion else None
                ),
                "trigger": "needs_canonical_match_review",
            },
        )

    return _CompEligibilityEvaluation(
        status="eligible",
        classification="eligible_graded_comp" if record.is_graded else "eligible_raw_comp",
        reasons=[],
        canonical_match_state=canonical_match_state,
        canonical_match_suggestion=canonical_match_suggestion,
        canonical_match_confidence_bucket=(
            canonical_match_suggestion.confidence_bucket if canonical_match_suggestion is not None else None
        ),
        canonical_match_review_state=(
            canonical_match_suggestion.review_state if canonical_match_suggestion is not None else None
        ),
        canonical_match_score=canonical_match_suggestion.deterministic_score if canonical_match_suggestion else None,
        evidence_json={
            "canonical_match_state": canonical_match_state,
            "canonical_match_suggestion_id": canonical_match_suggestion.id if canonical_match_suggestion else None,
            "canonical_match_review_state": (
                canonical_match_suggestion.review_state if canonical_match_suggestion else None
            ),
            "canonical_match_confidence_bucket": (
                canonical_match_suggestion.confidence_bucket if canonical_match_suggestion else None
            ),
            "normalization_issue_types": issue_type_set and sorted(issue_type_set) or [],
            "is_graded": record.is_graded,
            "grading_company": record.grading_company,
        },
    )


def _summary_read(
    session: Session,
    *,
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
    suggestion_rows: list[MarketSaleMatchSuggestion],
) -> MarketSaleCompEligibilitySummaryRead:
    if record.id is None:
        raise ValueError("market sale record must be flushed before serialization")
    evaluation = _classification_for_record(record, issue_rows, suggestion_rows)
    summary = _market_sale_summary(record=record, source=_market_source_or_404(session, market_source_id=record.market_source_id), issue_count=len(issue_rows))
    return MarketSaleCompEligibilitySummaryRead(
        **summary.model_dump(),
        review_status=record.review_status,  # type: ignore[arg-type]
        eligibility_status=evaluation.status,
        eligibility_classification=evaluation.classification,
        eligibility_reasons=evaluation.reasons,
        canonical_match_state=evaluation.canonical_match_state,  # type: ignore[arg-type]
        canonical_match_suggestion_id=evaluation.canonical_match_suggestion.id if evaluation.canonical_match_suggestion else None,
        canonical_match_confidence_bucket=evaluation.canonical_match_confidence_bucket,  # type: ignore[arg-type]
        canonical_match_review_state=evaluation.canonical_match_review_state,  # type: ignore[arg-type]
        canonical_match_deterministic_score=evaluation.canonical_match_score,
        match_suggestion_count=len(suggestion_rows),
    )


def _detail_read(
    session: Session,
    *,
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
    suggestion_rows: list[MarketSaleMatchSuggestion],
    review_action_rows: list[MarketSaleReviewAction],
) -> MarketSaleCompEligibilityRead:
    summary = _summary_read(
        session,
        record=record,
        issue_rows=issue_rows,
        suggestion_rows=suggestion_rows,
    )
    return MarketSaleCompEligibilityRead(
        **summary.model_dump(),
        raw_publisher=record.raw_publisher,
        normalized_publisher=record.normalized_publisher,
        raw_variant=record.raw_variant,
        normalized_variant=record.normalized_variant,
        raw_grade=record.raw_grade,
        normalized_grade=record.normalized_grade,
        raw_cert_number=record.raw_cert_number,
        normalized_cert_number=record.normalized_cert_number,
        seller_name=record.seller_name,
        buyer_name=record.buyer_name,
        source_url=record.source_url,
        source_metadata_json=record.source_metadata_json or {},
        images=[],
        normalization_issues=[MarketSaleNormalizationIssueRead.model_validate(row, from_attributes=True) for row in issue_rows],
        review_actions=[MarketSaleReviewActionRead.model_validate(row, from_attributes=True) for row in review_action_rows],
        source_snapshot=None,
        eligibility_evidence_json={
            "record": {
                "id": record.id,
                "market_source_id": record.market_source_id,
                "source_listing_id": record.source_listing_id,
                "listing_type": record.listing_type,
                "sale_price": str(record.sale_price) if record.sale_price is not None else None,
                "shipping_price": str(record.shipping_price) if record.shipping_price is not None else None,
                "total_price": str(record.total_price) if record.total_price is not None else None,
                "currency_code": record.currency_code,
                "sale_date": record.sale_date.isoformat() if record.sale_date is not None else None,
                "is_graded": record.is_graded,
                "grading_company": record.grading_company,
                "normalization_status": record.normalization_status,
                "review_status": record.review_status,
            },
            "normalization_issues": [
                {
                    "issue_type": row.issue_type,
                    "severity": row.severity,
                    "details_json": row.details_json,
                }
                for row in issue_rows
            ],
            "canonical_match_suggestions": [
                {
                    "id": row.id,
                    "review_state": row.review_state,
                    "confidence_bucket": row.confidence_bucket,
                    "deterministic_score": row.deterministic_score,
                    "suggestion_type": row.suggestion_type,
                }
                for row in suggestion_rows
            ],
            "review_actions": [
                {
                    "id": row.id,
                    "action_type": row.action_type,
                    "details_json": row.details_json,
                }
                for row in review_action_rows
            ],
            "evaluation": summary.model_dump(
                exclude={
                    "id",
                    "market_source_id",
                    "source_name",
                    "source_type",
                    "source_listing_id",
                    "source_snapshot_id",
                    "listing_type",
                    "raw_title",
                    "normalized_title",
                    "raw_issue",
                    "normalized_issue",
                    "sale_price",
                    "shipping_price",
                    "total_price",
                    "currency_code",
                    "sale_date",
                    "is_graded",
                    "grading_company",
                    "is_signed",
                    "normalization_status",
                    "normalization_issue_count",
                    "created_at",
                    "updated_at",
                }
            ),
        },
        match_suggestions=[_match_read(session, row=row, issue_count=len(issue_rows)) for row in suggestion_rows],
    )


def _list_base_query(
    session: Session,
    *,
    source: str | None = None,
    grading_company: str | None = None,
    is_graded: bool | None = None,
    currency: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
) -> list[tuple[MarketSaleRecord, MarketSource]]:
    ensure_system_market_sources(session)
    stmt = select(MarketSaleRecord, MarketSource).join(MarketSource, MarketSaleRecord.market_source_id == MarketSource.id)
    if source is not None:
        source_term = source.strip()
        if source_term:
            stmt = stmt.where(
                or_(
                    MarketSource.source_name.ilike(f"%{source_term}%"),
                    MarketSource.source_type.ilike(f"%{source_term}%"),
                )
            )
    if grading_company is not None:
        stmt = stmt.where(func.upper(MarketSaleRecord.grading_company) == grading_company.strip().upper())
    if is_graded is not None:
        stmt = stmt.where(MarketSaleRecord.is_graded.is_(is_graded))
    if currency is not None:
        stmt = stmt.where(func.upper(MarketSaleRecord.currency_code) == currency.strip().upper())
    if sale_date_from is not None:
        stmt = stmt.where(MarketSaleRecord.sale_date >= sale_date_from)
    if sale_date_to is not None:
        stmt = stmt.where(MarketSaleRecord.sale_date <= sale_date_to)
    stmt = stmt.order_by(
        MarketSaleRecord.sale_date.desc().nullslast(),
        MarketSource.source_name.asc(),
        MarketSaleRecord.normalized_title.asc(),
        MarketSaleRecord.normalized_issue.asc(),
        MarketSaleRecord.id.asc(),
    )
    return session.exec(stmt).all()


def _list_items(
    session: Session,
    *,
    source: str | None = None,
    eligibility_status: MarketCompEligibilityStatus | None = None,
    eligibility_classification: MarketCompEligibilityClassification | None = None,
    grading_company: str | None = None,
    is_graded: bool | None = None,
    currency: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
) -> list[MarketSaleCompEligibilitySummaryRead]:
    rows = _list_base_query(
        session,
        source=source,
        grading_company=grading_company,
        is_graded=is_graded,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    record_ids = [int(record.id) for record, _source in rows if record.id is not None]
    issue_map = _issue_rows_by_record(session, record_ids)
    suggestion_map = _suggestion_rows_by_record(session, record_ids)
    items = [
        _summary_read(
            session,
            record=record,
            issue_rows=issue_map.get(int(record.id or 0), []),
            suggestion_rows=suggestion_map.get(int(record.id or 0), []),
        )
        for record, _source in rows
    ]
    if eligibility_status is not None:
        items = [row for row in items if row.eligibility_status == eligibility_status]
    if eligibility_classification is not None:
        items = [row for row in items if row.eligibility_classification == eligibility_classification]
    items.sort(
        key=lambda row: (
            _STATUS_RANK[row.eligibility_status],
            _CLASSIFICATION_RANK[row.eligibility_classification],
            0 if row.sale_date is None else -row.sale_date.toordinal(),
            row.source_name,
            row.normalized_title or row.raw_title,
            row.normalized_issue or row.raw_issue,
            row.id,
        )
    )
    return items


def list_market_comp_eligibility(
    session: Session,
    *,
    source: str | None = None,
    eligibility_status: MarketCompEligibilityStatus | None = None,
    eligibility_classification: MarketCompEligibilityClassification | None = None,
    grading_company: str | None = None,
    is_graded: bool | None = None,
    currency: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
) -> MarketSaleCompEligibilityListResponse:
    items = _list_items(
        session,
        source=source,
        eligibility_status=eligibility_status,
        eligibility_classification=eligibility_classification,
        grading_company=grading_company,
        is_graded=is_graded,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    by_status_counter: Counter[MarketCompEligibilityStatus] = Counter(row.eligibility_status for row in items)
    by_classification_counter: Counter[MarketCompEligibilityClassification] = Counter(
        row.eligibility_classification for row in items
    )
    return MarketSaleCompEligibilityListResponse(
        items=items,
        total=len(items),
        by_eligibility_status={
            status: int(by_status_counter.get(status, 0)) for status in comp_eligibility_status_order()
        },
        by_eligibility_classification={
            classification: int(by_classification_counter.get(classification, 0))
            for classification in comp_eligibility_classification_order()
        },
    )


def get_market_comp_eligibility_for_owner(
    session: Session,
    *,
    market_sale_record_id: int,
    owner_user_id: int | None,
) -> MarketSaleCompEligibilityRead:
    del owner_user_id
    record = _market_sale_or_404(session, market_sale_record_id=market_sale_record_id)
    issue_rows = session.exec(
        select(MarketSaleNormalizationIssue)
        .where(MarketSaleNormalizationIssue.market_sale_record_id == market_sale_record_id)
        .order_by(MarketSaleNormalizationIssue.created_at.asc(), MarketSaleNormalizationIssue.id.asc())
    ).all()
    suggestion_rows = session.exec(
        select(MarketSaleMatchSuggestion)
        .where(MarketSaleMatchSuggestion.market_sale_record_id == market_sale_record_id)
        .order_by(MarketSaleMatchSuggestion.deterministic_score.desc(), MarketSaleMatchSuggestion.id.asc())
    ).all()
    review_action_rows = session.exec(
        select(MarketSaleReviewAction)
        .where(MarketSaleReviewAction.market_sale_record_id == market_sale_record_id)
        .order_by(MarketSaleReviewAction.created_at.asc(), MarketSaleReviewAction.id.asc())
    ).all()
    return _detail_read(
        session,
        record=record,
        issue_rows=issue_rows,
        suggestion_rows=suggestion_rows,
        review_action_rows=review_action_rows,
    )


def get_market_comp_eligibility_for_ops(
    session: Session,
    *,
    market_sale_record_id: int,
) -> MarketSaleCompEligibilityRead:
    return get_market_comp_eligibility_for_owner(
        session,
        market_sale_record_id=market_sale_record_id,
        owner_user_id=None,
    )

