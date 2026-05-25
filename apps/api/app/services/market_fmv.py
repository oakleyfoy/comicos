from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models import (
    MarketFmvCompReference,
    MarketFmvSnapshot,
    MarketSaleMatchSuggestion,
    MarketSaleNormalizationIssue,
    MarketSaleRecord,
    MarketSource,
)
from app.schemas.market_fmv import (
    MarketFmvCompReferenceRead,
    MarketFmvGenerateResponse,
    MarketFmvSnapshotListResponse,
    MarketFmvSnapshotRead,
    MarketFmvSnapshotSummaryRead,
)
from app.services.inventory import quantize_money
from app.services.market_sale_comp_eligibility import _classification_for_record, _issue_rows_by_record, _suggestion_rows_by_record
from app.services.market_sales import _market_sale_summary, ensure_system_market_sources

SNAPSHOT_VERSION = "market-fmv-snapshot-v1"
STALE_COMP_DAYS = 365
STALE_SNAPSHOT_DAYS = 120

_SCOPE_RANK = {"raw": 0, "graded": 1, "graded_by_company": 2, "graded_by_grade": 3}
_METHOD_RANK = {"median_recent_sales": 0, "weighted_recent_sales": 1}
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True)
class _SaleComp:
    record: MarketSaleRecord
    suggestion: MarketSaleMatchSuggestion
    base_price: Decimal
    sale_date: date


@dataclass(frozen=True)
class _SnapshotKey:
    canonical_issue_id: int | None
    metadata_identity_key: str | None
    snapshot_scope: str
    grading_company: str | None
    normalized_grade: str | None
    currency_code: str
    valuation_method: str


def _market_source_or_404(session: Session, *, market_source_id: int) -> MarketSource:
    source = session.get(MarketSource, market_source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Market source not found")
    return source


def _sale_summary(session: Session, *, record: MarketSaleRecord, issue_count: int) -> MarketFmvCompReferenceRead | None:
    del session, record, issue_count
    return None


def _bucketed_counts(items: list[MarketFmvSnapshotSummaryRead], attr: str) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for row in items:
        counts[str(getattr(row, attr))] += 1
    return dict(counts)


def _all_sale_rows(session: Session) -> list[MarketSaleRecord]:
    return session.exec(select(MarketSaleRecord).order_by(MarketSaleRecord.id.asc())).all()


def _eligible_sale_rows(session: Session) -> list[_SaleComp]:
    records = _all_sale_rows(session)
    if not records:
        return []
    record_ids = [int(row.id or 0) for row in records]
    issues_by_record = _issue_rows_by_record(session, record_ids)
    suggestions_by_record = _suggestion_rows_by_record(session, record_ids)
    eligible: list[_SaleComp] = []
    for record in records:
        if record.id is None:
            continue
        issue_rows = issues_by_record.get(int(record.id), [])
        suggestion_rows = suggestions_by_record.get(int(record.id), [])
        evaluation = _classification_for_record(record, issue_rows, suggestion_rows)
        if evaluation.status != "eligible":
            continue
        suggestion = evaluation.canonical_match_suggestion
        if suggestion is None:
            continue
        base_price = record.total_price if record.total_price is not None else record.sale_price
        if base_price is None or record.sale_date is None:
            continue
        eligible.append(
            _SaleComp(
                record=record,
                suggestion=suggestion,
                base_price=Decimal(base_price),
                sale_date=record.sale_date,
            )
        )
    return eligible


def _snapshot_keys_for_comp(comp: _SaleComp) -> list[_SnapshotKey]:
    record = comp.record
    suggestion = comp.suggestion
    identity_key = _trim(suggestion.suggested_identity_key)
    keys: list[_SnapshotKey] = []
    base_kwargs = {
        "canonical_issue_id": suggestion.canonical_issue_id,
        "metadata_identity_key": identity_key,
        "currency_code": record.currency_code,
    }
    if record.is_graded:
        keys.append(
            _SnapshotKey(
                **base_kwargs,
                snapshot_scope="graded",
                grading_company=None,
                normalized_grade=None,
                valuation_method="median_recent_sales",
            )
        )
        keys.append(
            _SnapshotKey(
                **base_kwargs,
                snapshot_scope="graded",
                grading_company=None,
                normalized_grade=None,
                valuation_method="weighted_recent_sales",
            )
        )
        if record.grading_company is not None:
            keys.append(
                _SnapshotKey(
                    **base_kwargs,
                    snapshot_scope="graded_by_company",
                    grading_company=record.grading_company,
                    normalized_grade=None,
                    valuation_method="median_recent_sales",
                )
            )
            keys.append(
                _SnapshotKey(
                    **base_kwargs,
                    snapshot_scope="graded_by_company",
                    grading_company=record.grading_company,
                    normalized_grade=None,
                    valuation_method="weighted_recent_sales",
                )
            )
        if record.grading_company is not None and record.normalized_grade is not None:
            keys.append(
                _SnapshotKey(
                    **base_kwargs,
                    snapshot_scope="graded_by_grade",
                    grading_company=record.grading_company,
                    normalized_grade=record.normalized_grade,
                    valuation_method="median_recent_sales",
                )
            )
            keys.append(
                _SnapshotKey(
                    **base_kwargs,
                    snapshot_scope="graded_by_grade",
                    grading_company=record.grading_company,
                    normalized_grade=record.normalized_grade,
                    valuation_method="weighted_recent_sales",
                )
            )
    else:
        keys.append(
            _SnapshotKey(
                **base_kwargs,
                snapshot_scope="raw",
                grading_company=None,
                normalized_grade=None,
                valuation_method="median_recent_sales",
            )
        )
        keys.append(
            _SnapshotKey(
                **base_kwargs,
                snapshot_scope="raw",
                grading_company=None,
                normalized_grade=None,
                valuation_method="weighted_recent_sales",
            )
        )
    return keys


def _date_decay_weight(*, snapshot_date: date, sale_date: date) -> float:
    age_days = max((snapshot_date - sale_date).days, 0)
    return round(1.0 / (1.0 + (age_days / 30.0)), 6)


def _median_value(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")


def _weighted_value(values: list[Decimal], weights: list[float]) -> Decimal:
    numerator = sum(value * Decimal(str(weight)) for value, weight in zip(values, weights, strict=True))
    denominator = sum(Decimal(str(weight)) for weight in weights)
    if denominator == 0:
        return values[-1]
    return numerator / denominator


def _volatility_bucket(values: list[Decimal]) -> str:
    if len(values) <= 1:
        return "stable"
    max_value = max(values)
    min_value = min(values)
    if min_value <= 0:
        return "volatile"
    spread_ratio = (max_value - min_value) / min_value
    if spread_ratio <= Decimal("0.15"):
        return "stable"
    if spread_ratio <= Decimal("0.35"):
        return "moderate"
    return "volatile"


def _liquidity_bucket(*, comp_count: int, newest: date, oldest: date, snapshot_date: date) -> str:
    newest_age = max((snapshot_date - newest).days, 0)
    cadence_window = max((newest - oldest).days, 0)
    if comp_count >= 8 and newest_age <= 30 and cadence_window <= 180:
        return "very_high"
    if comp_count >= 5 and newest_age <= 60:
        return "high"
    if comp_count >= 3 and newest_age <= 120:
        return "medium"
    if comp_count >= 2:
        return "low"
    return "very_low"


def _confidence_bucket(*, comp_count: int, stale_data: bool, volatility_bucket: str, liquidity_bucket: str) -> str:
    score = 0
    if comp_count >= 8:
        score += 4
    elif comp_count >= 5:
        score += 3
    elif comp_count >= 3:
        score += 2
    elif comp_count >= 2:
        score += 1
    if not stale_data:
        score += 2
    if volatility_bucket == "stable":
        score += 2
    elif volatility_bucket == "moderate":
        score += 1
    if liquidity_bucket in {"very_high", "high"}:
        score += 2
    elif liquidity_bucket == "medium":
        score += 1
    if score >= 9:
        return "very_high"
    if score >= 7:
        return "high"
    if score >= 5:
        return "medium"
    if score >= 3:
        return "low"
    return "very_low"


def _signature_match(snapshot: MarketFmvSnapshot, key: _SnapshotKey, *, snapshot_date: date) -> bool:
    return (
        snapshot.canonical_issue_id == key.canonical_issue_id
        and snapshot.metadata_identity_key == key.metadata_identity_key
        and snapshot.snapshot_scope == key.snapshot_scope
        and snapshot.grading_company == key.grading_company
        and snapshot.normalized_grade == key.normalized_grade
        and snapshot.currency_code == key.currency_code
        and snapshot.snapshot_date == snapshot_date
        and snapshot.valuation_method == key.valuation_method
    )


def _snapshot_summary_read(row: MarketFmvSnapshot) -> MarketFmvSnapshotSummaryRead:
    return MarketFmvSnapshotSummaryRead.model_validate(row, from_attributes=True)


def _load_snapshot(session: Session, *, snapshot_id: int) -> MarketFmvSnapshot:
    row = session.get(MarketFmvSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market FMV snapshot not found")
    return row


def _load_comp_references(session: Session, snapshot_id: int) -> list[MarketFmvCompReference]:
    return session.exec(
        select(MarketFmvCompReference)
        .where(MarketFmvCompReference.market_fmv_snapshot_id == snapshot_id)
        .order_by(MarketFmvCompReference.excluded_reason.asc(), MarketFmvCompReference.weighting_factor.desc(), MarketFmvCompReference.market_sale_record_id.asc(), MarketFmvCompReference.id.asc())
    ).all()


def _comp_reference_read(session: Session, row: MarketFmvCompReference) -> MarketFmvCompReferenceRead:
    sale = session.get(MarketSaleRecord, row.market_sale_record_id)
    sale_summary = None
    if sale is not None:
        source = _market_source_or_404(session, market_source_id=sale.market_source_id)
        sale_summary = _market_sale_summary(record=sale, source=source, issue_count=0)
    return MarketFmvCompReferenceRead(
        id=int(row.id or 0),
        market_fmv_snapshot_id=row.market_fmv_snapshot_id,
        market_sale_record_id=row.market_sale_record_id,
        weighting_factor=row.weighting_factor,
        included_reason=row.included_reason,
        excluded_reason=row.excluded_reason,
        created_at=row.created_at,
        market_sale_record=sale_summary,
    )


def _snapshot_read(session: Session, row: MarketFmvSnapshot) -> MarketFmvSnapshotRead:
    refs = _load_comp_references(session, int(row.id or 0))
    return MarketFmvSnapshotRead(
        **_snapshot_summary_read(row).model_dump(),
        evidence_json=dict(row.evidence_json or {}),
        comp_references=[_comp_reference_read(session, ref) for ref in refs],
    )


def generate_market_fmv_snapshots(session: Session) -> MarketFmvGenerateResponse:
    ensure_system_market_sources(session)
    snapshot_date = date.today()
    eligible_sales = _eligible_sale_rows(session)
    grouped: defaultdict[_SnapshotKey, list[_SaleComp]] = defaultdict(list)
    for comp in eligible_sales:
        for key in _snapshot_keys_for_comp(comp):
            if key.canonical_issue_id is None and key.metadata_identity_key is None:
                continue
            grouped[key].append(comp)

    existing_rows = session.exec(
        select(MarketFmvSnapshot).where(MarketFmvSnapshot.snapshot_date == snapshot_date)
    ).all()

    touched_rows: list[MarketFmvSnapshot] = []
    now = utc_now()
    for key, comps in grouped.items():
        included: list[_SaleComp] = []
        excluded: list[tuple[_SaleComp, str]] = []
        for comp in sorted(comps, key=lambda row: (row.sale_date, int(row.record.id or 0))):
            age_days = max((snapshot_date - comp.sale_date).days, 0)
            if age_days > STALE_COMP_DAYS:
                excluded.append((comp, "stale_comp"))
                continue
            included.append(comp)
        if not included:
            continue

        prices = [comp.base_price for comp in included]
        weights = [
            1.0 if key.valuation_method == "median_recent_sales" else _date_decay_weight(snapshot_date=snapshot_date, sale_date=comp.sale_date)
            for comp in included
        ]
        estimated = _median_value(prices) if key.valuation_method == "median_recent_sales" else _weighted_value(prices, weights)
        estimated = quantize_money(estimated)
        newest_sale = max(comp.sale_date for comp in included)
        oldest_sale = min(comp.sale_date for comp in included)
        stale_data = max((snapshot_date - newest_sale).days, 0) > STALE_SNAPSHOT_DAYS
        volatility_bucket = _volatility_bucket(prices)
        liquidity_bucket = _liquidity_bucket(
            comp_count=len(included),
            newest=newest_sale,
            oldest=oldest_sale,
            snapshot_date=snapshot_date,
        )
        confidence_bucket = _confidence_bucket(
            comp_count=len(included),
            stale_data=stale_data,
            volatility_bucket=volatility_bucket,
            liquidity_bucket=liquidity_bucket,
        )
        evidence_json = {
            "valuation_version": SNAPSHOT_VERSION,
            "included_sale_ids": [int(comp.record.id or 0) for comp in included],
            "excluded_sale_ids": [int(comp.record.id or 0) for comp, _reason in excluded],
            "excluded_reasons": {str(comp.record.id): reason for comp, reason in excluded if comp.record.id is not None},
            "newest_sale_date": newest_sale.isoformat(),
            "oldest_sale_date": oldest_sale.isoformat(),
            "comp_prices": [str(price) for price in prices],
            "weighting_factors": weights,
            "stale_comp_days": STALE_COMP_DAYS,
            "stale_snapshot_days": STALE_SNAPSHOT_DAYS,
            "confidence_bucket": confidence_bucket,
            "liquidity_bucket": liquidity_bucket,
            "volatility_bucket": volatility_bucket,
        }

        row = next((candidate for candidate in existing_rows if _signature_match(candidate, key, snapshot_date=snapshot_date)), None)
        if row is None:
            row = MarketFmvSnapshot(
                canonical_issue_id=key.canonical_issue_id,
                metadata_identity_key=key.metadata_identity_key,
                snapshot_scope=key.snapshot_scope,
                grading_company=key.grading_company,
                normalized_grade=key.normalized_grade,
                currency_code=key.currency_code,
                snapshot_date=snapshot_date,
                created_at=now,
            )
            existing_rows.append(row)
        row.comp_count = len(included)
        row.valuation_method = key.valuation_method
        row.estimated_fmv = estimated
        row.confidence_bucket = confidence_bucket
        row.liquidity_bucket = liquidity_bucket
        row.volatility_bucket = volatility_bucket
        row.stale_data = stale_data
        row.evidence_json = evidence_json
        row.updated_at = now
        session.add(row)
        session.flush()

        session.exec(delete(MarketFmvCompReference).where(MarketFmvCompReference.market_fmv_snapshot_id == row.id))
        for comp, weight in zip(included, weights, strict=True):
            session.add(
                MarketFmvCompReference(
                    market_fmv_snapshot_id=int(row.id or 0),
                    market_sale_record_id=int(comp.record.id or 0),
                    weighting_factor=weight,
                    included_reason="eligible_comp",
                    excluded_reason=None,
                    created_at=now,
                )
            )
        for comp, reason in excluded:
            session.add(
                MarketFmvCompReference(
                    market_fmv_snapshot_id=int(row.id or 0),
                    market_sale_record_id=int(comp.record.id or 0),
                    weighting_factor=0.0,
                    included_reason="excluded_comp",
                    excluded_reason=reason,
                    created_at=now,
                )
            )
        touched_rows.append(row)

    session.commit()
    summaries = [_snapshot_summary_read(row) for row in touched_rows]
    summaries.sort(
        key=lambda row: (
            -row.snapshot_date.toordinal(),
            _SCOPE_RANK.get(row.snapshot_scope, 99),
            _METHOD_RANK.get(row.valuation_method, 99),
            row.id,
        )
    )
    return MarketFmvGenerateResponse(snapshot_count=len(summaries), snapshots=summaries)


def _list_base(session: Session):
    ensure_system_market_sources(session)
    return session.exec(select(MarketFmvSnapshot)).all()


def list_market_fmv_snapshots(
    session: Session,
    *,
    snapshot_scope: str | None = None,
    grading_company: str | None = None,
    normalized_grade: str | None = None,
    confidence_bucket: str | None = None,
    liquidity_bucket: str | None = None,
    stale_data: bool | None = None,
    currency: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    metadata_identity_key: str | None = None,
) -> MarketFmvSnapshotListResponse:
    rows = _list_base(session)
    filtered: list[MarketFmvSnapshot] = []
    for row in rows:
        if snapshot_scope is not None and row.snapshot_scope != snapshot_scope:
            continue
        if grading_company is not None and _trim(row.grading_company or "") != _trim(grading_company):
            continue
        if normalized_grade is not None and _trim(row.normalized_grade or "") != _trim(normalized_grade):
            continue
        if confidence_bucket is not None and row.confidence_bucket != confidence_bucket:
            continue
        if liquidity_bucket is not None and row.liquidity_bucket != liquidity_bucket:
            continue
        if stale_data is not None and bool(row.stale_data) != stale_data:
            continue
        if currency is not None and row.currency_code.upper() != currency.strip().upper():
            continue
        if snapshot_date_from is not None and row.snapshot_date < snapshot_date_from:
            continue
        if snapshot_date_to is not None and row.snapshot_date > snapshot_date_to:
            continue
        if metadata_identity_key is not None and row.metadata_identity_key != metadata_identity_key:
            continue
        filtered.append(row)

    summaries = [_snapshot_summary_read(row) for row in filtered]
    summaries.sort(
        key=lambda row: (
            -row.snapshot_date.toordinal(),
            _SCOPE_RANK.get(row.snapshot_scope, 99),
            _METHOD_RANK.get(row.valuation_method, 99),
            row.id,
        )
    )
    return MarketFmvSnapshotListResponse(
        items=summaries,
        total=len(summaries),
        by_confidence_bucket=_bucketed_counts(summaries, "confidence_bucket"),  # type: ignore[arg-type]
        by_liquidity_bucket=_bucketed_counts(summaries, "liquidity_bucket"),  # type: ignore[arg-type]
        stale_count=sum(1 for row in summaries if row.stale_data),
    )


def get_market_fmv_snapshot(session: Session, *, snapshot_id: int) -> MarketFmvSnapshotRead:
    return _snapshot_read(session, _load_snapshot(session, snapshot_id=snapshot_id))

