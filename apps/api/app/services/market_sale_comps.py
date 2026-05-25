from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import calendar
from math import sqrt

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    MarketFmvCompReference,
    MarketFmvSnapshot,
    MarketSaleMatchSuggestion,
    MarketSaleNormalizationIssue,
    MarketSaleRecord,
    MarketSaleReviewAction,
    MarketSource,
)
from app.schemas.market_fmv import MarketFmvSnapshotSummaryRead
from app.schemas.market_sale_comps import (
    MarketComparableClassification,
    MarketComparableDuplicateRiskBucket,
    MarketComparableGroupRead,
    MarketComparableGradeConsistencyBucket,
    MarketComparableListResponse,
    MarketComparablePriceSpreadBucket,
    MarketComparableQualitySignalsRead,
    MarketComparableRecencyBucket,
    MarketComparableSaleRead,
    MarketComparableScope,
    MarketComparableSourceDiversityBucket,
    MarketComparableSnapshotCompsResponse,
)
from app.services.market_sale_comp_eligibility import (
    _classification_for_record,
    _detail_read,
    _issue_rows_by_record,
    _market_sale_summary,
    _review_actions_by_record,
    _suggestion_rows_by_record,
)
from app.services.market_sales import SUPPORTED_CURRENCY_CODES, ensure_system_market_sources
from app.services.metadata_enrichment import (
    build_metadata_identity_components,
    build_metadata_identity_key,
    normalize_issue_number,
)

STALE_COMP_DAYS = 365
_SCOPE_RANK: dict[MarketComparableScope, int] = {
    "raw": 0,
    "graded": 1,
    "graded_by_company": 2,
    "graded_by_grade": 3,
}
_CLASSIFICATION_RANK: dict[MarketComparableClassification, int] = {
    "included_comp": 0,
    "excluded_duplicate": 1,
    "excluded_review_required": 2,
    "excluded_missing_price": 3,
    "excluded_unsupported_currency": 4,
    "excluded_unresolved_identity": 5,
    "excluded_wrong_scope": 6,
    "excluded_wrong_grade": 7,
    "excluded_stale": 8,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _month_window(value: date | None) -> tuple[date | None, date | None]:
    if value is None:
        return None, None
    last_day = calendar.monthrange(value.year, value.month)[1]
    return date(value.year, value.month, 1), date(value.year, value.month, last_day)


def _identity_key_for_record(record: MarketSaleRecord) -> str | None:
    publisher = _trim(record.normalized_publisher or record.raw_publisher)
    title = _trim(record.normalized_title or record.raw_title)
    issue = normalize_issue_number(record.normalized_issue or record.raw_issue).canonical_value
    variant = _trim(record.normalized_variant)
    if publisher is None or title is None or issue is None:
        return None
    return build_metadata_identity_key(
        build_metadata_identity_components(
            publisher=publisher,
            series_title=title,
            issue_number=issue,
            variant=variant,
        )
    )


def _sale_scope(record: MarketSaleRecord) -> MarketComparableScope:
    if not record.is_graded:
        return "raw"
    if _trim(record.grading_company) is not None and _trim(record.normalized_grade) is not None:
        return "graded_by_grade"
    if _trim(record.grading_company) is not None:
        return "graded_by_company"
    return "graded"


def _base_price(record: MarketSaleRecord) -> Decimal | None:
    if record.total_price is not None:
        return Decimal(record.total_price)
    if record.sale_price is not None:
        return Decimal(record.sale_price)
    return None


def _sort_key_for_record(record: MarketSaleRecord) -> tuple:
    return (
        0 if record.sale_date is None else -record.sale_date.toordinal(),
        record.source_listing_id or "",
        record.source_snapshot_id or -1,
        record.id or -1,
    )


def _group_window_label(window_start: date | None, window_end: date | None) -> str:
    if window_start is None or window_end is None:
        return "unknown window"
    return f"{window_start.isoformat()}..{window_end.isoformat()}"


def _group_key(
    *,
    metadata_identity_key: str | None,
    canonical_issue_id: int | None,
    comp_scope: MarketComparableScope,
    grading_company: str | None,
    normalized_grade: str | None,
    currency_code: str,
    sale_window_start: date | None,
    sale_window_end: date | None,
) -> str:
    return "|".join(
        [
            metadata_identity_key or "unresolved",
            str(canonical_issue_id) if canonical_issue_id is not None else "no-canonical-issue",
            comp_scope,
            _trim(grading_company) or "raw",
            _trim(normalized_grade) or "no-grade",
            currency_code.upper(),
            sale_window_start.isoformat() if sale_window_start else "unknown-start",
            sale_window_end.isoformat() if sale_window_end else "unknown-end",
        ]
    )


def _group_label(
    *,
    metadata_identity_key: str | None,
    canonical_issue_id: int | None,
    comp_scope: MarketComparableScope,
    grading_company: str | None,
    normalized_grade: str | None,
    currency_code: str,
    sale_window_start: date | None,
    sale_window_end: date | None,
) -> str:
    parts = [
        metadata_identity_key or "unresolved identity",
        f"issue {canonical_issue_id}" if canonical_issue_id is not None else "no canonical issue",
        comp_scope,
    ]
    if grading_company:
        parts.append(grading_company)
    if normalized_grade:
        parts.append(normalized_grade)
    parts.append(currency_code.upper())
    parts.append(_group_window_label(sale_window_start, sale_window_end))
    return " · ".join(parts)


def _recency_bucket(days: int | None) -> MarketComparableRecencyBucket:
    if days is None:
        return "stale"
    if days <= 30:
        return "fresh"
    if days <= 90:
        return "recent"
    if days <= 180:
        return "aged"
    return "stale"


def _spread_bucket(ratio: float) -> MarketComparablePriceSpreadBucket:
    if ratio <= 0.08:
        return "tight"
    if ratio <= 0.20:
        return "moderate"
    if ratio <= 0.40:
        return "wide"
    return "volatile"


def _source_diversity_bucket(count: int) -> MarketComparableSourceDiversityBucket:
    if count <= 1:
        return "single_source"
    if count == 2:
        return "low"
    if count <= 4:
        return "medium"
    return "high"


def _grade_consistency_bucket(records: list[MarketSaleRecord]) -> MarketComparableGradeConsistencyBucket:
    graded_records = [record for record in records if record.is_graded]
    if not graded_records:
        return "consistent"
    values = {_trim(record.normalized_grade) for record in graded_records if _trim(record.normalized_grade) is not None}
    if len(values) <= 1:
        return "consistent"
    if len(values) == len(graded_records):
        return "mixed"
    return "mismatched"


def _duplicate_risk_bucket(records: list[MarketSaleRecord]) -> MarketComparableDuplicateRiskBucket:
    duplicate_hits = 0
    seen_listing_ids: set[str] = set()
    seen_cert_numbers: set[str] = set()
    seen_signature: set[tuple[str | None, str | None, str | None, str | None, str | None]] = set()
    for record in records:
        listing_id = _trim(record.source_listing_id)
        if listing_id is not None:
            if listing_id in seen_listing_ids:
                duplicate_hits += 1
            seen_listing_ids.add(listing_id)
        cert_number = _trim(record.normalized_cert_number or record.raw_cert_number)
        if cert_number is not None:
            if cert_number in seen_cert_numbers:
                duplicate_hits += 1
            seen_cert_numbers.add(cert_number)
        signature = (
            _trim(record.normalized_title or record.raw_title),
            _trim(record.normalized_issue or record.raw_issue),
            _trim(record.normalized_publisher or record.raw_publisher),
            _trim(record.normalized_variant),
            _trim(record.currency_code),
        )
        if signature in seen_signature:
            duplicate_hits += 1
        seen_signature.add(signature)
    if duplicate_hits >= 3:
        return "high"
    if duplicate_hits >= 1:
        return "medium"
    return "low"


def _volatility_signal(records: list[MarketSaleRecord]) -> str:
    prices = [price for price in (_base_price(record) for record in records) if price is not None]
    if len(prices) <= 1:
        return "stable"
    low = min(prices)
    high = max(prices)
    if low <= 0:
        return "volatile"
    ratio = float((high - low) / low)
    if ratio <= 0.10:
        return "stable"
    if ratio <= 0.25:
        return "moderate"
    return "volatile"


def _quality_signals(
    *,
    included_records: list[MarketSaleRecord],
    excluded_records: list[MarketSaleRecord],
    source_names: list[str],
    latest_sale_date: date | None,
) -> MarketComparableQualitySignalsRead:
    prices = [price for price in (_base_price(record) for record in included_records) if price is not None]
    if prices:
        low = min(prices)
        high = max(prices)
        spread = high - low
        ratio = float((spread / low) if low > 0 else 0)
    else:
        spread = Decimal("0")
        ratio = 0.0
    source_diversity_count = len({name for name in source_names if name})
    recency_days: int | None = None
    stale_warning = False
    if latest_sale_date is not None:
        recency_days = max((date.today() - latest_sale_date).days, 0)
        stale_warning = recency_days > STALE_COMP_DAYS
    return MarketComparableQualitySignalsRead(
        comp_count=len(included_records),
        included_count=len(included_records),
        excluded_count=len(excluded_records),
        source_diversity_count=source_diversity_count,
        source_diversity_bucket=_source_diversity_bucket(source_diversity_count),  # type: ignore[arg-type]
        sale_recency_days=recency_days,
        sale_recency_bucket=_recency_bucket(recency_days),
        price_spread=spread,
        price_spread_ratio=ratio,
        price_spread_bucket=_spread_bucket(ratio),
        grade_consistency_bucket=_grade_consistency_bucket(included_records),
        duplicate_risk_bucket=_duplicate_risk_bucket(included_records),
        volatility_signal=_volatility_signal(included_records),
        stale_data_warning=stale_warning,
    )


def _market_source_or_404(session: Session, *, market_source_id: int) -> MarketSource:
    source = session.get(MarketSource, market_source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Market source not found")
    return source


def _sale_summary(session: Session, *, record: MarketSaleRecord, issue_count: int) -> MarketSaleSummaryRead:
    source = _market_source_or_404(session, market_source_id=record.market_source_id)
    return _market_sale_summary(record=record, source=source, issue_count=issue_count)


@dataclass(frozen=True)
class _ComparableCandidate:
    record: MarketSaleRecord
    source_name: str
    source_type: str
    issue_rows: list[MarketSaleNormalizationIssue]
    suggestion_rows: list[MarketSaleMatchSuggestion]
    review_action_rows: list[MarketSaleReviewAction]
    detail: MarketComparableSaleRead
    identity_key: str | None
    canonical_issue_id: int | None
    comp_scope: MarketComparableScope
    grading_company: str | None
    normalized_grade: str | None
    currency_code: str
    sale_window_start: date | None
    sale_window_end: date | None
    group_key: str
    group_label: str
    base_bucket: tuple[str | None, int | None, date | None, date | None]


def _eligible_or_relevant_sale_rows(session: Session, rows: list[tuple[MarketSaleRecord, MarketSource]]) -> list[_ComparableCandidate]:
    record_ids = [int(record.id) for record, _source in rows if record.id is not None]
    issue_map = _issue_rows_by_record(session, record_ids)
    suggestion_map = _suggestion_rows_by_record(session, record_ids)
    review_map = _review_actions_by_record(session, record_ids)
    candidates: list[_ComparableCandidate] = []

    for record, _source in rows:
        if record.id is None or record.sale_date is None:
            continue
        issue_rows = issue_map.get(int(record.id), [])
        suggestion_rows = suggestion_map.get(int(record.id), [])
        review_action_rows = review_map.get(int(record.id), [])
        evaluation = _classification_for_record(record, issue_rows, suggestion_rows)
        detail = _detail_read(
            session,
            record=record,
            issue_rows=issue_rows,
            suggestion_rows=suggestion_rows,
            review_action_rows=review_action_rows,
        )
        canonical_issue_id = evaluation.canonical_match_suggestion.canonical_issue_id if evaluation.canonical_match_suggestion else None
        identity_key = (
            _trim(evaluation.canonical_match_suggestion.suggested_identity_key)
            if evaluation.canonical_match_suggestion is not None
            else None
        ) or _identity_key_for_record(record)
        comp_scope = _sale_scope(record)
        grading_company = _trim(record.grading_company)
        normalized_grade = _trim(record.normalized_grade)
        sale_window_start, sale_window_end = _month_window(record.sale_date)
        group_key = _group_key(
            metadata_identity_key=identity_key,
            canonical_issue_id=canonical_issue_id,
            comp_scope=comp_scope,
            grading_company=grading_company,
            normalized_grade=normalized_grade,
            currency_code=record.currency_code.upper(),
            sale_window_start=sale_window_start,
            sale_window_end=sale_window_end,
        )
        group_label = _group_label(
            metadata_identity_key=identity_key,
            canonical_issue_id=canonical_issue_id,
            comp_scope=comp_scope,
            grading_company=grading_company,
            normalized_grade=normalized_grade,
            currency_code=record.currency_code.upper(),
            sale_window_start=sale_window_start,
            sale_window_end=sale_window_end,
        )
        comp_classification, comp_reason = _classify_comp(
            record=record,
            evaluation=evaluation,
            issue_rows=issue_rows,
            suggestion_rows=suggestion_rows,
            identity_key=identity_key,
            canonical_issue_id=canonical_issue_id,
            comp_scope=comp_scope,
            grading_company=grading_company,
            normalized_grade=normalized_grade,
        )
        sale_read = MarketComparableSaleRead(
            **detail.model_dump(),
            market_sale_record_id=int(record.id),
            comp_classification=comp_classification,
            comp_reason=comp_reason,
            comp_scope=comp_scope,
            comp_group_key=group_key,
            comp_group_label=group_label,
            comp_window_start=sale_window_start,
            comp_window_end=sale_window_end,
            comp_included=comp_classification == "included_comp",
            comp_group_order=0,
            comp_evidence_json={
                "identity_key": identity_key,
                "canonical_issue_id": canonical_issue_id,
                "scope": comp_scope,
                "grading_company": grading_company,
                "normalized_grade": normalized_grade,
                "currency_code": record.currency_code.upper(),
                "sale_window_start": sale_window_start.isoformat() if sale_window_start else None,
                "sale_window_end": sale_window_end.isoformat() if sale_window_end else None,
                "issue_types": [row.issue_type for row in issue_rows],
                "suggestion_ids": [row.id for row in suggestion_rows],
                "canonical_match_state": evaluation.canonical_match_state,
            },
        )
        candidates.append(
            _ComparableCandidate(
                record=record,
                source_name=_source.source_name,
                source_type=_source.source_type,
                issue_rows=issue_rows,
                suggestion_rows=suggestion_rows,
                review_action_rows=review_action_rows,
                detail=sale_read,
                identity_key=identity_key,
                canonical_issue_id=canonical_issue_id,
                comp_scope=comp_scope,
                grading_company=grading_company,
                normalized_grade=normalized_grade,
                currency_code=record.currency_code.upper(),
                sale_window_start=sale_window_start,
                sale_window_end=sale_window_end,
                group_key=group_key,
                group_label=group_label,
                base_bucket=(identity_key, canonical_issue_id, sale_window_start, sale_window_end),
            )
        )
    return candidates


def _classify_comp(
    *,
    record: MarketSaleRecord,
    evaluation,
    issue_rows: list[MarketSaleNormalizationIssue],
    suggestion_rows: list[MarketSaleMatchSuggestion],
    identity_key: str | None,
    canonical_issue_id: int | None,
    comp_scope: MarketComparableScope,
    grading_company: str | None,
    normalized_grade: str | None,
) -> tuple[MarketComparableClassification, str]:
    issue_types = {str(row.issue_type) for row in issue_rows}
    if record.sale_price is None and record.total_price is None:
        return "excluded_missing_price", "missing price"
    if record.currency_code.upper() not in SUPPORTED_CURRENCY_CODES:
        return "excluded_unsupported_currency", "unsupported currency"
    if record.review_status == "duplicate_flagged" or "duplicate_listing" in issue_types:
        return "excluded_duplicate", "duplicate listing"
    if evaluation.status == "needs_review":
        return "excluded_review_required", "review required before comp"
    if evaluation.status != "eligible":
        if evaluation.classification == "ineligible_unresolved_identity" or identity_key is None or canonical_issue_id is None:
            return "excluded_unresolved_identity", "unresolved identity"
        if evaluation.classification == "ineligible_missing_price":
            return "excluded_missing_price", "missing price"
        if evaluation.classification == "ineligible_unsupported_currency":
            return "excluded_unsupported_currency", "unsupported currency"
        return "excluded_review_required", "review required before comp"
    if record.sale_date is not None and max((date.today() - record.sale_date).days, 0) > STALE_COMP_DAYS:
        return "excluded_stale", "stale comp"
    if record.is_graded and comp_scope == "raw":
        return "excluded_wrong_scope", "graded sale does not fit raw scope"
    if not record.is_graded and comp_scope != "raw":
        return "excluded_wrong_scope", "raw sale does not fit graded scope"
    if comp_scope == "graded_by_company" and grading_company is not None:
        if _trim(record.grading_company) != grading_company:
            return "excluded_wrong_grade", "grading company mismatch"
    if comp_scope == "graded_by_grade" and normalized_grade is not None:
        if _trim(record.normalized_grade) != normalized_grade:
            return "excluded_wrong_grade", "grade mismatch"
    if canonical_issue_id is None or identity_key is None:
        return "excluded_unresolved_identity", "unresolved identity"
    return "included_comp", "included comp"


def _build_groups(
    candidates: list[_ComparableCandidate],
    *,
    include_excluded: bool,
) -> list[MarketComparableGroupRead]:
    buckets: defaultdict[tuple[str | None, int | None, date | None, date | None], list[_ComparableCandidate]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate.base_bucket].append(candidate)

    groups: list[MarketComparableGroupRead] = []
    for base_bucket, bucket_candidates in sorted(
        buckets.items(),
        key=lambda item: (
            item[0][2].toordinal() if item[0][2] is not None else 0,
            item[0][0] or "",
            item[0][1] or -1,
        ),
    ):
        by_group: defaultdict[str, list[_ComparableCandidate]] = defaultdict(list)
        for candidate in bucket_candidates:
            by_group[candidate.group_key].append(candidate)

        for group_key, group_candidates in sorted(by_group.items(), key=lambda item: item[0]):
            first = sorted(group_candidates, key=lambda cand: _sort_key_for_record(cand.record))[0]
            included_candidates = [candidate for candidate in group_candidates if candidate.detail.comp_classification == "included_comp"]
            if not included_candidates and not include_excluded:
                continue
            excluded_candidates: list[_ComparableCandidate] = []
            if include_excluded:
                excluded_candidates = [
                    candidate
                    for candidate in bucket_candidates
                    if candidate.group_key != group_key
                    and candidate.identity_key == first.identity_key
                    and candidate.canonical_issue_id == first.canonical_issue_id
                    and candidate.currency_code == first.currency_code
                    and candidate.sale_window_start == first.sale_window_start
                    and candidate.sale_window_end == first.sale_window_end
                ]
                if not included_candidates:
                    excluded_candidates = list(group_candidates)
            included_sales = [candidate.detail for candidate in sorted(included_candidates, key=lambda cand: _sort_key_for_record(cand.record))]
            excluded_sales = [
                candidate.detail.model_copy(
                    update={
                        "comp_classification": _reclassify_for_group(candidate, first),
                        "comp_reason": _reason_for_group(candidate, first),
                        "comp_group_key": first.group_key,
                        "comp_group_label": first.group_label,
                        "comp_included": False,
                    }
                )
                for candidate in sorted(excluded_candidates, key=lambda cand: _sort_key_for_record(cand.record))
            ]
            if not included_sales and not excluded_sales:
                continue
            latest_candidates = [candidate.record.sale_date for candidate in included_candidates if candidate.record.sale_date is not None]
            if not latest_candidates:
                latest_candidates = [candidate.record.sale_date for candidate in excluded_candidates if candidate.record.sale_date is not None]
            latest_sale_date = max(latest_candidates) if latest_candidates else None
            quality_source_names = sorted(
                {
                    candidate.source_name
                    for candidate in (included_candidates if included_candidates else excluded_candidates)
                }
            )
            quality_signals = _quality_signals(
                included_records=[candidate.record for candidate in included_candidates],
                excluded_records=[candidate.record for candidate in excluded_candidates],
                source_names=quality_source_names,
                latest_sale_date=latest_sale_date,
            )
            groups.append(
                MarketComparableGroupRead(
                    group_key=first.group_key,
                    group_label=first.group_label,
                    metadata_identity_key=first.identity_key,
                    canonical_issue_id=first.canonical_issue_id,
                    comp_scope=first.comp_scope,
                    grading_company=first.grading_company,
                    normalized_grade=first.normalized_grade,
                    currency_code=first.currency_code,
                    sale_window_start=first.sale_window_start,
                    sale_window_end=first.sale_window_end,
                    included_count=len(included_sales),
                    excluded_count=len(excluded_sales),
                    comp_count=len(included_sales),
                    source_names=sorted({candidate.source_name for candidate in included_candidates}),
                    source_types=sorted({candidate.source_type for candidate in included_candidates}),
                    quality_signals=quality_signals,
                    included_comps=included_sales,
                    excluded_comps=excluded_sales if include_excluded else [],
                )
            )
    groups.sort(
        key=lambda group: (
            0 if group.sale_window_start is None else -group.sale_window_start.toordinal(),
            _SCOPE_RANK[group.comp_scope],
            group.group_key,
        )
    )
    return groups


def _reclassify_for_group(candidate: _ComparableCandidate, group: _ComparableCandidate) -> MarketComparableClassification:
    classification, _reason = _classify_comp(
        record=candidate.record,
        evaluation=_classification_for_record(candidate.record, candidate.issue_rows, candidate.suggestion_rows),
        issue_rows=candidate.issue_rows,
        suggestion_rows=candidate.suggestion_rows,
        identity_key=group.identity_key,
        canonical_issue_id=group.canonical_issue_id,
        comp_scope=group.comp_scope,
        grading_company=group.grading_company,
        normalized_grade=group.normalized_grade,
    )
    return classification


def _reason_for_group(candidate: _ComparableCandidate, group: _ComparableCandidate) -> str:
    _classification, reason = _classify_comp(
        record=candidate.record,
        evaluation=_classification_for_record(candidate.record, candidate.issue_rows, candidate.suggestion_rows),
        issue_rows=candidate.issue_rows,
        suggestion_rows=candidate.suggestion_rows,
        identity_key=group.identity_key,
        canonical_issue_id=group.canonical_issue_id,
        comp_scope=group.comp_scope,
        grading_company=group.grading_company,
        normalized_grade=group.normalized_grade,
    )
    return reason


def _response_from_groups(groups: list[MarketComparableGroupRead]) -> MarketComparableListResponse:
    classification_counter: Counter[MarketComparableClassification] = Counter()
    scope_counter: Counter[MarketComparableScope] = Counter()
    total_comps = 0
    for group in groups:
        total_comps += group.included_count + group.excluded_count
        scope_counter[group.comp_scope] += group.included_count + group.excluded_count
        for comp in group.included_comps:
            classification_counter[comp.comp_classification] += 1
        for comp in group.excluded_comps:
            classification_counter[comp.comp_classification] += 1
    return MarketComparableListResponse(
        items=groups,
        total_groups=len(groups),
        total_comps=total_comps,
        by_classification={key: int(value) for key, value in classification_counter.items()},
        by_scope={key: int(value) for key, value in scope_counter.items()},
    )


def _base_list_query(
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
        stmt = stmt.where(MarketSaleRecord.grading_company.is_not(None))
        stmt = stmt.where(MarketSaleRecord.grading_company.ilike(grading_company.strip()))
    if is_graded is not None:
        stmt = stmt.where(MarketSaleRecord.is_graded.is_(is_graded))
    if currency is not None:
        stmt = stmt.where(MarketSaleRecord.currency_code.ilike(currency.strip()))
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


def _filter_candidates_by_identity(
    candidates: list[_ComparableCandidate],
    *,
    metadata_identity_key: str | None,
) -> list[_ComparableCandidate]:
    if metadata_identity_key is None:
        return candidates
    identity_term = metadata_identity_key.strip()
    if not identity_term:
        return candidates
    filtered: list[_ComparableCandidate] = []
    for candidate in candidates:
        if candidate.identity_key == identity_term:
            filtered.append(candidate)
            continue
        suggestion_identity_keys = {
            _trim(row.suggested_identity_key) for row in candidate.suggestion_rows if _trim(row.suggested_identity_key) is not None
        }
        if identity_term in suggestion_identity_keys:
            filtered.append(candidate)
    return filtered


def list_market_comps(
    session: Session,
    *,
    source: str | None = None,
    metadata_identity_key: str | None = None,
    is_graded: bool | None = None,
    grading_company: str | None = None,
    normalized_grade: str | None = None,
    currency: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
    include_excluded: bool = False,
) -> MarketComparableListResponse:
    rows = _base_list_query(
        session,
        source=source,
        grading_company=grading_company,
        is_graded=is_graded,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    candidates = _eligible_or_relevant_sale_rows(session, rows)
    candidates = _filter_candidates_by_identity(candidates, metadata_identity_key=metadata_identity_key)
    if normalized_grade is not None:
        normalized_grade = normalized_grade.strip()
        candidates = [candidate for candidate in candidates if _trim(candidate.normalized_grade) == normalized_grade]
    groups = _build_groups(candidates, include_excluded=include_excluded)
    return _response_from_groups(groups)


def _snapshot_market_fmv_or_404(session: Session, *, snapshot_id: int) -> MarketFmvSnapshot:
    snapshot = session.get(MarketFmvSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Market FMV snapshot not found")
    return snapshot


def _comp_reference_classification(reason: str | None, record: MarketSaleRecord) -> tuple[MarketComparableClassification, str]:
    if reason is None:
        return "included_comp", "included comp"
    if reason == "stale_comp":
        return "excluded_stale", "stale comp"
    if reason == "duplicate_comp":
        return "excluded_duplicate", "duplicate comp"
    if reason == "wrong_grade":
        return "excluded_wrong_grade", "wrong grade"
    if reason == "wrong_scope":
        return "excluded_wrong_scope", "wrong scope"
    if reason == "missing_price":
        return "excluded_missing_price", "missing price"
    if reason == "unsupported_currency":
        return "excluded_unsupported_currency", "unsupported currency"
    if reason == "review_required":
        return "excluded_review_required", "review required"
    if reason == "unresolved_identity":
        return "excluded_unresolved_identity", "unresolved identity"
    return "excluded_review_required", reason.replace("_", " ")


def get_market_fmv_snapshot_comps(
    session: Session,
    *,
    snapshot_id: int,
    include_excluded: bool = False,
) -> MarketComparableSnapshotCompsResponse:
    snapshot = _snapshot_market_fmv_or_404(session, snapshot_id=snapshot_id)
    refs = session.exec(
        select(MarketFmvCompReference)
        .where(MarketFmvCompReference.market_fmv_snapshot_id == snapshot_id)
        .order_by(
            MarketFmvCompReference.excluded_reason.asc(),
            MarketFmvCompReference.weighting_factor.desc(),
            MarketFmvCompReference.market_sale_record_id.asc(),
            MarketFmvCompReference.id.asc(),
        )
    ).all()
    record_ids = [int(ref.market_sale_record_id) for ref in refs]
    if not record_ids:
        return MarketComparableSnapshotCompsResponse(
            snapshot=MarketFmvSnapshotSummaryRead.model_validate(snapshot, from_attributes=True),
        )
    sales = session.exec(
        select(MarketSaleRecord, MarketSource)
        .join(MarketSource, MarketSaleRecord.market_source_id == MarketSource.id)
        .where(MarketSaleRecord.id.in_(record_ids))
        .order_by(MarketSaleRecord.sale_date.desc().nullslast(), MarketSaleRecord.id.asc())
    ).all()
    candidates = _eligible_or_relevant_sale_rows(session, sales)
    ref_by_sale_id = {int(ref.market_sale_record_id): ref for ref in refs}
    by_id = {int(candidate.record.id or 0): candidate for candidate in candidates}
    for sale_id, ref in ref_by_sale_id.items():
        candidate = by_id.get(sale_id)
        if candidate is None:
            continue
        classification, reason = _comp_reference_classification(ref.excluded_reason, candidate.record)
        updated = candidate.detail.model_copy(
            update={
                "comp_classification": classification,
                "comp_reason": reason,
                "comp_included": classification == "included_comp",
                "comp_evidence_json": {
                    **candidate.detail.comp_evidence_json,
                    "snapshot_id": snapshot_id,
                    "weighting_factor": ref.weighting_factor,
                    "included_reason": ref.included_reason,
                    "excluded_reason": ref.excluded_reason,
                },
            }
        )
        by_id[sale_id] = candidate.__class__(
            record=candidate.record,
            source_name=candidate.source_name,
            source_type=candidate.source_type,
            issue_rows=candidate.issue_rows,
            suggestion_rows=candidate.suggestion_rows,
            review_action_rows=candidate.review_action_rows,
            detail=updated,
            identity_key=candidate.identity_key,
            canonical_issue_id=candidate.canonical_issue_id,
            comp_scope=candidate.comp_scope,
            grading_company=candidate.grading_company,
            normalized_grade=candidate.normalized_grade,
            currency_code=candidate.currency_code,
            sale_window_start=candidate.sale_window_start,
            sale_window_end=candidate.sale_window_end,
            group_key=candidate.group_key,
            group_label=candidate.group_label,
            base_bucket=candidate.base_bucket,
        )
    updated_candidates = list(by_id.values())
    groups = _build_groups(updated_candidates, include_excluded=include_excluded)
    response = _response_from_groups(groups)
    return MarketComparableSnapshotCompsResponse(
        snapshot=MarketFmvSnapshotSummaryRead.model_validate(snapshot, from_attributes=True),
        items=groups,
        total_groups=response.total_groups,
        total_comps=response.total_comps,
        by_classification=response.by_classification,
        by_scope=response.by_scope,
    )

