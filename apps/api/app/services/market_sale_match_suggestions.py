from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    CanonicalSeries,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
    InventoryCopy,
    MarketSaleMatchSuggestion,
    MarketSaleNormalizationIssue,
    MarketSaleRecord,
    MarketSource,
)
from app.schemas.market_sale_match_suggestions import (
    MarketSaleMatchSuggestionConfidenceBucket,
    MarketSaleMatchSuggestionGenerateResponse,
    MarketSaleMatchSuggestionOpsListResponse,
    MarketSaleMatchSuggestionRead,
    MarketSaleMatchSuggestionReviewActionResponse,
    MarketSaleMatchSuggestionReviewState,
    MarketSaleMatchSuggestionType,
)
from app.schemas.market_sales import MarketSaleSummaryRead
from app.services.market_sales import _market_sale_summary, ensure_system_market_sources
from app.services.metadata_enrichment import (
    build_metadata_identity_components,
    build_metadata_identity_key,
    normalize_issue_number,
    normalize_publisher_name,
    normalize_series_title_with_aliases,
)

CONFIDENCE_VERSION = "market-sale-match-suggestion-v1"

_CONFIDENCE_BUCKET_ORDER: tuple[MarketSaleMatchSuggestionConfidenceBucket, ...] = (
    "very_high",
    "high",
    "medium",
    "low",
    "very_low",
)

_TYPE_BASE_SCORE: dict[MarketSaleMatchSuggestionType, float] = {
    "exact_identity_key": 0.97,
    "normalized_title_issue_publisher": 0.91,
    "publisher_series_issue": 0.84,
    "normalized_title_issue": 0.68,
    "barcode_supported": 0.58,
    "inventory_context_supported": 0.63,
    "unresolved_ambiguous": 0.18,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True)
class _IssueRegistryRow:
    canonical_issue_id: int
    canonical_series_id: int | None
    canonical_publisher_id: int | None
    title: str
    publisher: str
    issue_number: str


@dataclass(frozen=True)
class _InventoryContextRow:
    inventory_copy_id: int
    metadata_identity_key: str | None
    canonical_issue_id: int
    canonical_series_id: int | None
    canonical_publisher_id: int | None
    title: str
    publisher: str
    issue_number: str


@dataclass(frozen=True)
class _SuggestionSpec:
    market_sale_record_id: int
    canonical_issue_id: int | None
    canonical_series_id: int | None
    canonical_publisher_id: int | None
    suggested_identity_key: str | None
    suggestion_type: MarketSaleMatchSuggestionType
    confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket
    deterministic_score: float
    evidence_json: dict[str, object]


def _bucket_for_score(score: float) -> MarketSaleMatchSuggestionConfidenceBucket:
    if score >= 0.9:
        return "very_high"
    if score >= 0.8:
        return "high"
    if score >= 0.65:
        return "medium"
    if score >= 0.45:
        return "low"
    return "very_low"


def _issue_rows_by_record(session: Session, record_id: int) -> list[MarketSaleNormalizationIssue]:
    return session.exec(
        select(MarketSaleNormalizationIssue)
        .where(MarketSaleNormalizationIssue.market_sale_record_id == record_id)
        .order_by(MarketSaleNormalizationIssue.created_at.asc(), MarketSaleNormalizationIssue.id.asc())
    ).all()


def _market_sale_row_or_404(session: Session, market_sale_record_id: int) -> MarketSaleRecord:
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    return record


def _get_market_source_or_404(session: Session, market_source_id: int) -> MarketSource:
    source = session.get(MarketSource, market_source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Market source not found")
    return source


def _market_sale_read(
    session: Session,
    *,
    record: MarketSaleRecord,
    issue_count: int,
) -> MarketSaleSummaryRead:
    source = _get_market_source_or_404(session, int(record.market_source_id))
    return _market_sale_summary(record=record, source=source, issue_count=issue_count)


def _match_read(
    session: Session,
    *,
    row: MarketSaleMatchSuggestion,
    issue_count: int | None = None,
) -> MarketSaleMatchSuggestionRead:
    sale = _market_sale_row_or_404(session, int(row.market_sale_record_id))
    source = _get_market_source_or_404(session, int(sale.market_source_id))
    if issue_count is None:
        issue_count = len(_issue_rows_by_record(session, int(sale.id)))
    summary = _market_sale_read(session, record=sale, issue_count=issue_count)
    return MarketSaleMatchSuggestionRead(
        id=int(row.id or 0),
        market_sale_record_id=int(row.market_sale_record_id),
        market_source_id=summary.market_source_id,
        source_name=summary.source_name,
        source_type=summary.source_type,
        source_listing_id=summary.source_listing_id,
        listing_type=summary.listing_type,
        raw_title=summary.raw_title,
        normalized_title=summary.normalized_title,
        raw_issue=summary.raw_issue,
        normalized_issue=summary.normalized_issue,
        raw_publisher=sale.raw_publisher,
        normalized_publisher=sale.normalized_publisher,
        raw_variant=sale.raw_variant,
        normalized_variant=sale.normalized_variant,
        raw_grade=sale.raw_grade,
        normalized_grade=sale.normalized_grade,
        raw_cert_number=sale.raw_cert_number,
        normalized_cert_number=sale.normalized_cert_number,
        sale_price=summary.sale_price,
        shipping_price=summary.shipping_price,
        total_price=summary.total_price,
        currency_code=summary.currency_code,
        sale_date=summary.sale_date,
        is_graded=summary.is_graded,
        grading_company=sale.grading_company,
        is_signed=summary.is_signed,
        normalization_status=summary.normalization_status,
        normalization_issue_count=issue_count,
        canonical_issue_id=row.canonical_issue_id,
        canonical_series_id=row.canonical_series_id,
        canonical_publisher_id=row.canonical_publisher_id,
        suggested_identity_key=row.suggested_identity_key,
        suggestion_type=row.suggestion_type,  # type: ignore[arg-type]
        confidence_bucket=row.confidence_bucket,  # type: ignore[arg-type]
        deterministic_score=row.deterministic_score,
        confidence_version=row.confidence_version,
        evidence_json=dict(row.evidence_json or {}),
        review_state=row.review_state,  # type: ignore[arg-type]
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _canonical_title(value: str | None, *, session: Session) -> str | None:
    if value is None:
        return None
    normalized = normalize_series_title_with_aliases(value, session=session).canonical_value
    return _trim(normalized)


def _canonical_publisher(value: str | None, *, session: Session) -> str | None:
    if value is None:
        return None
    normalized = normalize_publisher_name(value, session=session).canonical_value
    return _trim(normalized)


def _canonical_issue(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_issue_number(value).canonical_value


def _sale_identity_components(
    *,
    publisher: str | None,
    title: str | None,
    issue: str | None,
    variant: str | None,
) -> str | None:
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


def _sale_identity_prefix(*, publisher: str | None, title: str | None, issue: str | None) -> str | None:
    if publisher is None or title is None or issue is None:
        return None
    return build_metadata_identity_key(
        build_metadata_identity_components(
            publisher=publisher,
            series_title=title,
            issue_number=issue,
            variant=None,
        )
    )


def _barcode_values(record: MarketSaleRecord) -> list[str]:
    values: list[str] = []
    for raw_value in (
        record.normalized_cert_number,
        record.raw_cert_number,
        str((record.source_metadata_json or {}).get("barcode") or ""),
        str((record.source_metadata_json or {}).get("upc") or ""),
        str((record.source_metadata_json or {}).get("normalized_upc") or ""),
        str((record.source_metadata_json or {}).get("barcode_value") or ""),
    ):
        trimmed = _trim(raw_value)
        if trimmed:
            values.append(re.sub(r"\s+", "", trimmed).upper())
    return sorted(dict.fromkeys(values))


def _load_canonical_issue_rows(
    session: Session,
    *,
    title: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
) -> list[_IssueRegistryRow]:
    stmt = (
        select(
            CatalogIssue.id,
            CanonicalSeries.id,
            CatalogPublisher.id,
            CatalogSeries.name,
            CatalogPublisher.name,
            CatalogIssue.issue_number,
        )
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
        .join(
            CanonicalSeries,
            and_(
                CanonicalSeries.canonical_title == CatalogSeries.name,
                CanonicalSeries.canonical_publisher == CatalogPublisher.name,
            ),
            isouter=True,
        )
    )
    if title is not None:
        stmt = stmt.where(CatalogSeries.name == title)
    if issue_number is not None:
        stmt = stmt.where(CatalogIssue.issue_number == issue_number)
    if publisher is not None:
        stmt = stmt.where(CatalogPublisher.name == publisher)
    rows = session.exec(
        stmt.order_by(
            CatalogPublisher.name.asc(),
            CatalogSeries.name.asc(),
            CatalogIssue.issue_number.asc(),
            CatalogIssue.id.asc(),
        )
    ).all()
    return [
        _IssueRegistryRow(
            canonical_issue_id=int(issue_id),
            canonical_series_id=int(series_id) if series_id is not None else None,
            canonical_publisher_id=int(publisher_id) if publisher_id is not None else None,
            title=str(title_name),
            publisher=str(publisher_name),
            issue_number=str(issue_num),
        )
        for issue_id, series_id, publisher_id, title_name, publisher_name, issue_num in rows
    ]


def _load_inventory_rows(
    session: Session,
    *,
    identity_key: str | None,
    prefix_only: bool,
) -> list[_InventoryContextRow]:
    if identity_key is None:
        return []
    stmt = (
        select(
            InventoryCopy.id,
            InventoryCopy.metadata_identity_key,
            InventoryCopy.canonical_series_id,
            CatalogIssue.id,
            CatalogPublisher.id,
            CatalogSeries.name,
            CatalogPublisher.name,
            CatalogIssue.issue_number,
        )
        .join(CatalogIssue, InventoryCopy.catalog_issue_id == CatalogIssue.id, isouter=True)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id, isouter=True)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
    )
    if prefix_only:
        stmt = stmt.where(InventoryCopy.metadata_identity_key.like(f"{identity_key}%"))
        stmt = stmt.where(InventoryCopy.metadata_identity_key != identity_key)
    else:
        stmt = stmt.where(InventoryCopy.metadata_identity_key == identity_key)
    rows = session.exec(stmt.order_by(InventoryCopy.id.asc())).all()
    return [
        _InventoryContextRow(
            inventory_copy_id=int(inventory_copy_id),
            metadata_identity_key=str(metadata_identity_key) if metadata_identity_key is not None else None,
            canonical_issue_id=int(issue_id),
            canonical_series_id=int(series_id) if series_id is not None else None,
            canonical_publisher_id=int(publisher_id) if publisher_id is not None else None,
            title=str(title_name),
            publisher=str(publisher_name),
            issue_number=str(issue_num),
        )
        for inventory_copy_id, metadata_identity_key, series_id, issue_id, publisher_id, title_name, publisher_name, issue_num in rows
    ]


def _inventory_linked_suggestion_map(
    session: Session,
    *,
    inventory_copy_ids: Iterable[int],
) -> dict[int, list[CanonicalIssueLinkSuggestion]]:
    ids = sorted({int(inventory_copy_id) for inventory_copy_id in inventory_copy_ids})
    if not ids:
        return {}
    rows = session.exec(
        select(CanonicalIssueLinkSuggestion)
        .where(CanonicalIssueLinkSuggestion.inventory_copy_id.in_(ids))
        .order_by(CanonicalIssueLinkSuggestion.deterministic_score.desc(), CanonicalIssueLinkSuggestion.id.asc())
    ).all()
    bucket: defaultdict[int, list[CanonicalIssueLinkSuggestion]] = defaultdict(list)
    for row in rows:
        if row.inventory_copy_id is None:
            continue
        bucket[int(row.inventory_copy_id)].append(row)
    return dict(bucket)


def _normalization_penalty(record: MarketSaleRecord, issue_rows: list[MarketSaleNormalizationIssue]) -> float:
    issue_types = {str(row.issue_type) for row in issue_rows}
    penalty = 0.0
    if record.normalization_status == "normalization_failed":
        penalty += 0.18
    elif record.normalization_status == "partially_normalized":
        penalty += 0.08
    if "missing_issue_number" in issue_types:
        penalty += 0.12
    if "malformed_title" in issue_types:
        penalty += 0.08
    if "ambiguous_variant" in issue_types:
        penalty += 0.05
    if "missing_sale_price" in issue_types:
        penalty += 0.03
    if "unsupported_currency" in issue_types:
        penalty += 0.06
    return round(min(penalty, 0.4), 4)


def _score(
    *,
    suggestion_type: MarketSaleMatchSuggestionType,
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
    support_count: int = 0,
    linked_reviewed_count: int = 0,
    barcode_count: int = 0,
) -> float:
    score = _TYPE_BASE_SCORE[suggestion_type]
    score += min(0.05, 0.01 * max(0, support_count - 1))
    score += min(0.04, 0.02 * max(0, linked_reviewed_count))
    if barcode_count > 0 and suggestion_type != "unresolved_ambiguous":
        score += 0.03
    score -= _normalization_penalty(record, issue_rows)
    if suggestion_type == "barcode_supported" and barcode_count == 0:
        score -= 0.08
    if suggestion_type == "unresolved_ambiguous":
        score = min(score, 0.35)
    return round(max(0.0, min(0.99, score)), 4)


def _issue_rows_have_unresolved_signal(issue_rows: list[MarketSaleNormalizationIssue]) -> bool:
    issue_types = {str(row.issue_type) for row in issue_rows}
    return bool(issue_types.intersection({"missing_issue_number", "malformed_title", "ambiguous_variant", "missing_sale_price", "unsupported_currency"}))


def _spec_from_candidate(
    *,
    record: MarketSaleRecord,
    suggestion_type: MarketSaleMatchSuggestionType,
    canonical_issue_id: int | None,
    canonical_series_id: int | None,
    canonical_publisher_id: int | None,
    suggested_identity_key: str | None,
    issue_rows: list[MarketSaleNormalizationIssue],
    support_count: int = 0,
    linked_reviewed_count: int = 0,
    barcode_values: list[str] | None = None,
    evidence_json: dict[str, object] | None = None,
) -> _SuggestionSpec:
    score = _score(
        suggestion_type=suggestion_type,
        record=record,
        issue_rows=issue_rows,
        support_count=support_count,
        linked_reviewed_count=linked_reviewed_count,
        barcode_count=len(barcode_values or []),
    )
    return _SuggestionSpec(
        market_sale_record_id=int(record.id or 0),
        canonical_issue_id=canonical_issue_id,
        canonical_series_id=canonical_series_id,
        canonical_publisher_id=canonical_publisher_id,
        suggested_identity_key=suggested_identity_key,
        suggestion_type=suggestion_type,
        confidence_bucket=_bucket_for_score(score),
        deterministic_score=score,
        evidence_json=dict(evidence_json or {}),
    )


def _group_inventory_candidates(
    rows: list[_InventoryContextRow],
    *,
    suggestion_type: MarketSaleMatchSuggestionType,
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
    barcode_values: list[str],
    linked_suggestion_map: dict[int, list[CanonicalIssueLinkSuggestion]],
) -> list[_SuggestionSpec]:
    grouped: dict[int, list[_InventoryContextRow]] = defaultdict(list)
    for row in rows:
        grouped[row.canonical_issue_id].append(row)
    specs: list[_SuggestionSpec] = []
    for canonical_issue_id, candidates in sorted(grouped.items()):
        first = candidates[0]
        linked_rows = [
            linked
            for candidate in candidates
            for linked in linked_suggestion_map.get(candidate.inventory_copy_id, [])
        ]
        reviewed_rows = [row for row in linked_rows if row.review_state == "approved"]
        evidence: dict[str, object] = {
            "support_count": len(candidates),
            "inventory_copy_ids": [row.inventory_copy_id for row in candidates],
            "metadata_identity_keys": sorted({row.metadata_identity_key for row in candidates if row.metadata_identity_key}),
            "title": first.title,
            "publisher": first.publisher,
            "issue_number": first.issue_number,
            "linked_canonical_issue_suggestion_ids": [int(row.id or 0) for row in linked_rows],
            "linked_canonical_issue_suggestion_states": [row.review_state for row in linked_rows],
        }
        if barcode_values:
            evidence["barcode_values"] = barcode_values
        specs.append(
            _spec_from_candidate(
                record=record,
                suggestion_type=suggestion_type,
                canonical_issue_id=canonical_issue_id,
                canonical_series_id=first.canonical_series_id,
                canonical_publisher_id=first.canonical_publisher_id,
                suggested_identity_key=first.metadata_identity_key,
                issue_rows=issue_rows,
                support_count=len(candidates),
                linked_reviewed_count=len(reviewed_rows),
                barcode_values=barcode_values,
                evidence_json=evidence,
            )
        )
    return specs


def _group_registry_candidates(
    rows: list[_IssueRegistryRow],
    *,
    record: MarketSaleRecord,
    issue_rows: list[MarketSaleNormalizationIssue],
    barcode_values: list[str],
    suggestion_type: MarketSaleMatchSuggestionType,
    linked_reviewed_count: int = 0,
    evidence_extra: dict[str, object] | None = None,
) -> list[_SuggestionSpec]:
    grouped: dict[int, list[_IssueRegistryRow]] = defaultdict(list)
    for row in rows:
        grouped[row.canonical_issue_id].append(row)
    specs: list[_SuggestionSpec] = []
    for canonical_issue_id, candidates in sorted(grouped.items()):
        first = candidates[0]
        evidence: dict[str, object] = {
            "support_count": len(candidates),
            "title": first.title,
            "publisher": first.publisher,
            "issue_number": first.issue_number,
            "registry_titles": sorted({row.title for row in candidates}),
            "registry_publishers": sorted({row.publisher for row in candidates}),
        }
        if evidence_extra:
            evidence.update(evidence_extra)
        if barcode_values:
            evidence["barcode_values"] = barcode_values
        specs.append(
            _spec_from_candidate(
                record=record,
                suggestion_type=suggestion_type,
                canonical_issue_id=canonical_issue_id,
                canonical_series_id=first.canonical_series_id,
                canonical_publisher_id=first.canonical_publisher_id,
                suggested_identity_key=evidence_extra.get("suggested_identity_key") if evidence_extra else None,
                issue_rows=issue_rows,
                support_count=len(candidates),
                linked_reviewed_count=linked_reviewed_count,
                barcode_values=barcode_values,
                evidence_json=evidence,
            )
        )
    return specs


def _best_specs_by_score(specs: list[_SuggestionSpec]) -> list[_SuggestionSpec]:
    best: dict[tuple[int | None, int | None, str | None, MarketSaleMatchSuggestionType], _SuggestionSpec] = {}
    for spec in specs:
        key = (
            spec.canonical_issue_id,
            spec.canonical_series_id,
            spec.suggested_identity_key,
            spec.suggestion_type,
        )
        incumbent = best.get(key)
        if incumbent is None or spec.deterministic_score > incumbent.deterministic_score:
            best[key] = spec
    return sorted(best.values(), key=lambda item: (-item.deterministic_score, item.suggestion_type, item.canonical_issue_id or -1))


def _build_suggestion_specs(
    session: Session,
    *,
    record: MarketSaleRecord,
) -> list[_SuggestionSpec]:
    issue_rows = _issue_rows_by_record(session, int(record.id or 0))
    barcode_values = _barcode_values(record)

    canonical_title = _canonical_title(record.normalized_title or record.raw_title, session=session)
    canonical_issue = _canonical_issue(record.normalized_issue or record.raw_issue)
    canonical_publisher = _canonical_publisher(record.normalized_publisher or record.raw_publisher, session=session)
    canonical_variant = _trim(record.normalized_variant)

    exact_identity_key = _sale_identity_components(
        publisher=canonical_publisher,
        title=canonical_title,
        issue=canonical_issue,
        variant=canonical_variant,
    )
    identity_prefix = _sale_identity_prefix(
        publisher=canonical_publisher,
        title=canonical_title,
        issue=canonical_issue,
    )

    registry_exact_rows: list[_IssueRegistryRow] = []
    registry_title_issue_rows: list[_IssueRegistryRow] = []
    if canonical_title and canonical_issue and canonical_publisher:
        registry_exact_rows = _load_canonical_issue_rows(
            session,
            title=canonical_title,
            issue_number=canonical_issue,
            publisher=canonical_publisher,
        )
    if canonical_title and canonical_issue:
        registry_title_issue_rows = _load_canonical_issue_rows(
            session,
            title=canonical_title,
            issue_number=canonical_issue,
            publisher=None,
        )

    exact_inventory_rows = _load_inventory_rows(session, identity_key=exact_identity_key, prefix_only=False)
    prefix_inventory_rows = _load_inventory_rows(session, identity_key=identity_prefix, prefix_only=True)
    linked_suggestion_map = _inventory_linked_suggestion_map(
        session,
        inventory_copy_ids=[row.inventory_copy_id for row in exact_inventory_rows] + [row.inventory_copy_id for row in prefix_inventory_rows],
    )

    specs: list[_SuggestionSpec] = []
    if exact_inventory_rows:
        specs.extend(
            _group_inventory_candidates(
                exact_inventory_rows,
                suggestion_type="exact_identity_key",
                record=record,
                issue_rows=issue_rows,
                barcode_values=barcode_values,
                linked_suggestion_map=linked_suggestion_map,
            )
        )

    if registry_exact_rows:
        evidence_extra = {"suggested_identity_key": exact_identity_key}
        specs.extend(
            _group_registry_candidates(
                registry_exact_rows,
                record=record,
                issue_rows=issue_rows,
                barcode_values=barcode_values,
                suggestion_type="normalized_title_issue_publisher",
                evidence_extra=evidence_extra,
            )
        )
        if prefix_inventory_rows and exact_identity_key is not None:
            # Same canonical row, but the inventory context adds a separate review-only hint.
            specs.extend(
                _group_registry_candidates(
                    registry_exact_rows,
                    record=record,
                    issue_rows=issue_rows,
                    barcode_values=barcode_values,
                    suggestion_type="publisher_series_issue",
                    linked_reviewed_count=0,
                    evidence_extra={
                        "suggested_identity_key": exact_identity_key,
                        "inventory_context_supported": True,
                        "inventory_support_count": len(prefix_inventory_rows),
                    },
                )
            )
    elif registry_title_issue_rows:
        specs.extend(
            _group_registry_candidates(
                registry_title_issue_rows,
                record=record,
                issue_rows=issue_rows,
                barcode_values=barcode_values,
                suggestion_type="normalized_title_issue",
                evidence_extra={
                    "suggested_identity_key": exact_identity_key,
                    "publisher_missing_or_weaker": True,
                },
            )
        )

    if prefix_inventory_rows and not exact_inventory_rows:
        specs.extend(
            _group_inventory_candidates(
                prefix_inventory_rows,
                suggestion_type="inventory_context_supported",
                record=record,
                issue_rows=issue_rows,
                barcode_values=barcode_values,
                linked_suggestion_map=linked_suggestion_map,
            )
        )

    if barcode_values and any(spec.suggestion_type != "unresolved_ambiguous" for spec in specs):
        best = specs[0]
        specs.append(
            _SuggestionSpec(
                market_sale_record_id=int(record.id or 0),
                canonical_issue_id=best.canonical_issue_id,
                canonical_series_id=best.canonical_series_id,
                canonical_publisher_id=best.canonical_publisher_id,
                suggested_identity_key=best.suggested_identity_key,
                suggestion_type="barcode_supported",
                confidence_bucket=_bucket_for_score(
                    _score(
                        suggestion_type="barcode_supported",
                        record=record,
                        issue_rows=issue_rows,
                        support_count=1,
                        linked_reviewed_count=0,
                        barcode_count=len(barcode_values),
                    )
                ),
                deterministic_score=_score(
                    suggestion_type="barcode_supported",
                    record=record,
                    issue_rows=issue_rows,
                    support_count=1,
                    linked_reviewed_count=0,
                    barcode_count=len(barcode_values),
                ),
                evidence_json={
                    "barcode_values": barcode_values,
                    "barcode_can_support_but_not_sole_identity": True,
                    "best_candidate_suggestion_type": best.suggestion_type,
                },
            )
        )

    if not specs or _issue_rows_have_unresolved_signal(issue_rows):
        specs.append(
            _SuggestionSpec(
                market_sale_record_id=int(record.id or 0),
                canonical_issue_id=None,
                canonical_series_id=None,
                canonical_publisher_id=None,
                suggested_identity_key=exact_identity_key or identity_prefix,
                suggestion_type="unresolved_ambiguous",
                confidence_bucket=_bucket_for_score(
                    _score(
                        suggestion_type="unresolved_ambiguous",
                        record=record,
                        issue_rows=issue_rows,
                        support_count=0,
                        linked_reviewed_count=0,
                        barcode_count=len(barcode_values),
                    )
                ),
                deterministic_score=_score(
                    suggestion_type="unresolved_ambiguous",
                    record=record,
                    issue_rows=issue_rows,
                    support_count=0,
                    linked_reviewed_count=0,
                    barcode_count=len(barcode_values),
                ),
                evidence_json={
                    "unresolved_issue_types": sorted({str(row.issue_type) for row in issue_rows}),
                    "normalization_status": record.normalization_status,
                    "barcode_values": barcode_values,
                    "identity_key": exact_identity_key or identity_prefix,
                },
            )
        )

    return _best_specs_by_score(specs)


def _existing_rows_for_sale(session: Session, *, market_sale_record_id: int) -> list[MarketSaleMatchSuggestion]:
    return session.exec(
        select(MarketSaleMatchSuggestion)
        .where(MarketSaleMatchSuggestion.market_sale_record_id == market_sale_record_id)
        .order_by(MarketSaleMatchSuggestion.deterministic_score.desc(), MarketSaleMatchSuggestion.id.asc())
    ).all()


def _signature_for_row(row: MarketSaleMatchSuggestion) -> tuple[int, int | None, int | None, str | None, MarketSaleMatchSuggestionType, str]:
    return (
        int(row.market_sale_record_id),
        row.canonical_issue_id,
        row.canonical_series_id,
        row.suggested_identity_key,
        row.suggestion_type,  # type: ignore[return-value]
        row.confidence_version,
    )


def _signature_for_spec(spec: _SuggestionSpec) -> tuple[int, int | None, int | None, str | None, MarketSaleMatchSuggestionType, str]:
    return (
        spec.market_sale_record_id,
        spec.canonical_issue_id,
        spec.canonical_series_id,
        spec.suggested_identity_key,
        spec.suggestion_type,
        CONFIDENCE_VERSION,
    )


def _upsert_generated_suggestions(
    session: Session,
    *,
    record: MarketSaleRecord,
    specs: list[_SuggestionSpec],
    actor_user_id: int | None,
) -> list[MarketSaleMatchSuggestion]:
    existing = _existing_rows_for_sale(session, market_sale_record_id=int(record.id or 0))
    existing_by_sig = {_signature_for_row(row): row for row in existing}
    now = utc_now()
    out_rows: list[MarketSaleMatchSuggestion] = []

    for spec in specs:
        sig = _signature_for_spec(spec)
        row = existing_by_sig.get(sig)
        if row is None:
            row = MarketSaleMatchSuggestion(
                market_sale_record_id=int(record.id or 0),
                canonical_issue_id=spec.canonical_issue_id,
                canonical_series_id=spec.canonical_series_id,
                canonical_publisher_id=spec.canonical_publisher_id,
                suggested_identity_key=spec.suggested_identity_key,
                suggestion_type=spec.suggestion_type,
                confidence_bucket=spec.confidence_bucket,
                deterministic_score=spec.deterministic_score,
                confidence_version=CONFIDENCE_VERSION,
                evidence_json=spec.evidence_json,
                review_state="pending",
                reviewed_by_user_id=None,
                reviewed_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.canonical_issue_id = spec.canonical_issue_id
            row.canonical_series_id = spec.canonical_series_id
            row.canonical_publisher_id = spec.canonical_publisher_id
            row.suggested_identity_key = spec.suggested_identity_key
            row.suggestion_type = spec.suggestion_type
            row.confidence_bucket = spec.confidence_bucket
            row.deterministic_score = spec.deterministic_score
            row.evidence_json = spec.evidence_json
            row.updated_at = now
            session.add(row)
        out_rows.append(row)

    session.flush()
    session.commit()
    for row in out_rows:
        session.refresh(row)
    return sorted(out_rows, key=lambda row: (-row.deterministic_score, row.id or -1))


def _set_review_state(
    session: Session,
    *,
    row: MarketSaleMatchSuggestion,
    review_state: MarketSaleMatchSuggestionReviewState,
    actor_user_id: int | None,
) -> MarketSaleMatchSuggestion:
    now = utc_now()
    row.review_state = review_state
    row.reviewed_by_user_id = actor_user_id
    row.reviewed_at = now
    row.updated_at = now
    session.add(row)
    session.flush()
    session.commit()
    session.refresh(row)
    return row


def _require_row_access(session: Session, *, row: MarketSaleMatchSuggestion, ops_mode: bool, owner_user_id: int | None) -> None:
    del owner_user_id
    if not ops_mode:
        # Owner endpoints are authenticated but not ownership-scoped in the market-sales domain.
        return
    if session.get(MarketSaleRecord, int(row.market_sale_record_id)) is None:
        raise HTTPException(status_code=404, detail="Market sale match suggestion not found")


def generate_market_sale_match_suggestions(
    session: Session,
    *,
    market_sale_record_id: int,
    actor_user_id: int | None,
) -> MarketSaleMatchSuggestionGenerateResponse:
    ensure_system_market_sources(session)
    record = _market_sale_row_or_404(session, market_sale_record_id)
    specs = _build_suggestion_specs(session, record=record)
    rows = _upsert_generated_suggestions(session, record=record, specs=specs, actor_user_id=actor_user_id)
    issue_count = len(_issue_rows_by_record(session, int(record.id or 0)))
    return MarketSaleMatchSuggestionGenerateResponse(
        sale_id=int(record.id or 0),
        suggestion_count=len(rows),
        suggestions=[_match_read(session, row=row, issue_count=issue_count) for row in rows],
    )


def list_market_sale_match_suggestions(
    session: Session,
    *,
    ops_mode: bool,
    owner_user_id: int | None,
    source: str | None = None,
    confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | None = None,
    review_state: MarketSaleMatchSuggestionReviewState | None = None,
    suggestion_type: MarketSaleMatchSuggestionType | None = None,
) -> MarketSaleMatchSuggestionOpsListResponse:
    del owner_user_id
    ensure_system_market_sources(session)
    stmt = (
        select(MarketSaleMatchSuggestion, MarketSaleRecord, MarketSource)
        .join(MarketSaleRecord, MarketSaleMatchSuggestion.market_sale_record_id == MarketSaleRecord.id)
        .join(MarketSource, MarketSaleRecord.market_source_id == MarketSource.id)
        .order_by(
            MarketSaleMatchSuggestion.deterministic_score.desc(),
            MarketSaleMatchSuggestion.updated_at.desc(),
            MarketSaleMatchSuggestion.id.asc(),
        )
    )
    if source is not None:
        source_term = source.strip().lower()
        if source_term:
            stmt = stmt.where(
                or_(
                    MarketSource.source_name.ilike(f"%{source_term}%"),
                    MarketSource.source_type.ilike(f"%{source_term}%"),
                )
            )
    if confidence_bucket is not None:
        stmt = stmt.where(MarketSaleMatchSuggestion.confidence_bucket == confidence_bucket)
    if review_state is not None:
        stmt = stmt.where(MarketSaleMatchSuggestion.review_state == review_state)
    if suggestion_type is not None:
        stmt = stmt.where(MarketSaleMatchSuggestion.suggestion_type == suggestion_type)
    rows = session.exec(stmt).all()
    suggestions = [
        _match_read(session, row=suggestion_row, issue_count=len(_issue_rows_by_record(session, int(sale_row.id or 0))))
        for suggestion_row, sale_row, _source_row in rows
    ]
    return MarketSaleMatchSuggestionOpsListResponse(
        suggestions=suggestions,
        review_state=review_state or "all",
        confidence_bucket=confidence_bucket or "all",
        suggestion_type=suggestion_type or "all",
        total_count=len(suggestions),
    )


def list_market_sale_match_suggestions_for_sale(
    session: Session,
    *,
    market_sale_record_id: int,
    ops_mode: bool,
    owner_user_id: int | None,
) -> list[MarketSaleMatchSuggestionRead]:
    del owner_user_id
    ensure_system_market_sources(session)
    record = _market_sale_row_or_404(session, market_sale_record_id)
    rows = _existing_rows_for_sale(session, market_sale_record_id=int(record.id or 0))
    issue_count = len(_issue_rows_by_record(session, int(record.id or 0)))
    return [_match_read(session, row=row, issue_count=issue_count) for row in rows]


def get_market_sale_match_suggestion_for_owner(
    session: Session,
    *,
    market_sale_record_id: int,
    owner_user_id: int | None,
) -> list[MarketSaleMatchSuggestionRead]:
    return list_market_sale_match_suggestions_for_sale(
        session,
        market_sale_record_id=market_sale_record_id,
        ops_mode=False,
        owner_user_id=owner_user_id,
    )


def get_market_sale_match_suggestion_for_ops(
    session: Session,
    *,
    market_sale_record_id: int,
) -> list[MarketSaleMatchSuggestionRead]:
    return list_market_sale_match_suggestions_for_sale(
        session,
        market_sale_record_id=market_sale_record_id,
        ops_mode=True,
        owner_user_id=None,
    )


def approve_market_sale_match_suggestion_for_ops(
    session: Session,
    *,
    suggestion_id: int,
    actor_user_id: int | None,
) -> MarketSaleMatchSuggestionReviewActionResponse:
    row = session.get(MarketSaleMatchSuggestion, suggestion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market sale match suggestion not found")
    updated = _set_review_state(session, row=row, review_state="approved", actor_user_id=actor_user_id)
    return MarketSaleMatchSuggestionReviewActionResponse(suggestion=_match_read(session, row=updated))


def reject_market_sale_match_suggestion_for_ops(
    session: Session,
    *,
    suggestion_id: int,
    actor_user_id: int | None,
) -> MarketSaleMatchSuggestionReviewActionResponse:
    row = session.get(MarketSaleMatchSuggestion, suggestion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market sale match suggestion not found")
    updated = _set_review_state(session, row=row, review_state="rejected", actor_user_id=actor_user_id)
    return MarketSaleMatchSuggestionReviewActionResponse(suggestion=_match_read(session, row=updated))


def ignore_market_sale_match_suggestion_for_ops(
    session: Session,
    *,
    suggestion_id: int,
    actor_user_id: int | None,
) -> MarketSaleMatchSuggestionReviewActionResponse:
    row = session.get(MarketSaleMatchSuggestion, suggestion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market sale match suggestion not found")
    updated = _set_review_state(session, row=row, review_state="ignored", actor_user_id=actor_user_id)
    return MarketSaleMatchSuggestionReviewActionResponse(suggestion=_match_read(session, row=updated))

