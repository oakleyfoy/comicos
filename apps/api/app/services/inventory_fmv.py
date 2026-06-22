from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    ComicIssue,
    InventoryCopy,
    MarketFmvCompReference,
    MarketFmvSnapshot,
    MarketTrendSnapshot,
    User,
)
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.inventory_fmv import (
    InventoryFmvAttachmentRead,
    InventoryValuationScope,
    PortfolioValueCurrencySummaryRead,
    PortfolioValueSummaryResponse,
)
from app.schemas.inventory import InventoryListResponse, InventoryRow
from app.schemas.market_fmv import MarketFmvSnapshotRead, MarketFmvSnapshotSummaryRead
from app.schemas.market_fmv import MarketFmvCompReferenceRead
from app.schemas.market_trends import MarketTrendSnapshotSummaryRead
from app.services.authoritative_fmv_service import authoritative_fmv_to_evidence, get_authoritative_fmv
from app.services.duplicate_ownership_intelligence import (
    duplicate_ownership_inventory_context_for_owner,
    duplicate_ownership_inventory_attach_map,
    list_duplicate_ownership_ops,
)
from app.services.inventory_intelligence import normalize_ownership_state

ZERO = Decimal("0.00")
_METHOD_RANK = {"weighted_recent_sales": 0, "median_recent_sales": 1}
_SCOPE_RANK = {"raw": 0, "graded_by_grade": 1, "graded_by_company": 2, "graded": 3}
_CONFIDENCE_RANK = {"very_high": 0, "high": 1, "medium": 2, "low": 3, "very_low": 4}
_LIQUIDITY_RANK = {"very_high": 0, "high": 1, "medium": 2, "low": 3, "very_low": 4}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _attachment_volatility_bucket(value: str | None) -> str | None:
    normalized = _trim(value)
    if normalized is None:
        return None
    if normalized in {"stable", "moderate", "volatile"}:
        return normalized
    if normalized in {"low", "very_low"}:
        return "volatile"
    if normalized == "medium":
        return "moderate"
    if normalized == "high":
        return "moderate"
    if normalized == "very_high":
        return "stable"
    return "volatile"


@dataclass(frozen=True)
class _ProjectionRow:
    inventory_copy_id: int
    metadata_identity_key: str | None
    canonical_issue_id: int | None
    title: str
    publisher: str
    issue_number: str
    grade_status: str
    order_status: str
    release_status: str
    received_at: datetime | None
    acquisition_cost: Decimal


def _projection_rows(
    session: Session,
    *,
    owner_user_id: int | None = None,
    inventory_copy_id: int | None = None,
) -> list[_ProjectionRow]:
    stmt = apply_inventory_spine_joins(
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
            InventoryCopy.canonical_series_id.label("canonical_series_id"),
            ComicIssue.id.label("canonical_issue_id"),
            title_expr().label("title"),
            publisher_expr().label("publisher"),
            issue_number_expr().label("issue_number"),
            InventoryCopy.grade_status.label("grade_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.received_at.label("received_at"),
            InventoryCopy.acquisition_cost.label("acquisition_cost"),
            InventoryCopy.current_fmv.label("current_fmv"),
        ).select_from(InventoryCopy)
    )
    if owner_user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == owner_user_id)
    if inventory_copy_id is not None:
        stmt = stmt.where(InventoryCopy.id == inventory_copy_id)
    rows = session.exec(stmt.order_by(InventoryCopy.id.asc())).all()
    out: list[_ProjectionRow] = []
    for row in rows:
        out.append(
            _ProjectionRow(
                inventory_copy_id=int(row.inventory_copy_id),
                metadata_identity_key=_trim(row.metadata_identity_key),
                canonical_issue_id=int(row.canonical_issue_id) if row.canonical_issue_id is not None else None,
                title=str(row.title),
                publisher=str(row.publisher),
                issue_number=str(row.issue_number),
                grade_status=str(row.grade_status),
                order_status=str(row.order_status),
                release_status=str(row.release_status),
                received_at=row.received_at,
                acquisition_cost=Decimal(str(row.acquisition_cost)),
            )
        )
    return out


def _projection_from_mapping(row: Mapping[str, Any]) -> _ProjectionRow:
    return _ProjectionRow(
        inventory_copy_id=int(row["inventory_copy_id"]),
        metadata_identity_key=_trim(row.get("metadata_identity_key")),
        canonical_issue_id=int(row["canonical_issue_id"]) if row.get("canonical_issue_id") is not None else None,
        title=str(row["title"]),
        publisher=str(row["publisher"]),
        issue_number=str(row["issue_number"]),
        grade_status=str(row.get("grade_status") or "raw"),
        order_status=str(row.get("order_status") or "ordered"),
        release_status=str(row.get("release_status") or "unknown"),
        received_at=row.get("received_at"),
        acquisition_cost=Decimal(str(row.get("acquisition_cost") or "0")),
    )


def _approved_canonical_issue_id(session: Session, *, inventory_copy_id: int) -> int | None:
    row = session.exec(
        select(CanonicalIssueLinkSuggestion.canonical_issue_id)
        .where(
            CanonicalIssueLinkSuggestion.inventory_copy_id == inventory_copy_id,
            CanonicalIssueLinkSuggestion.review_state == "approved",
            CanonicalIssueLinkSuggestion.canonical_issue_id.is_not(None),
        )
        .order_by(
            CanonicalIssueLinkSuggestion.deterministic_score.desc(),
            CanonicalIssueLinkSuggestion.id.asc(),
        )
    ).first()
    return int(row) if row is not None else None


def _candidate_snapshots(
    session: Session,
    *,
    row: _ProjectionRow,
    approved_canonical_issue_id: int | None,
) -> list[MarketFmvSnapshot]:
    is_graded = row.grade_status != "raw"
    scopes = ["raw"] if not is_graded else ["graded_by_grade", "graded_by_company", "graded"]
    stmt = select(MarketFmvSnapshot).where(MarketFmvSnapshot.snapshot_scope.in_(scopes))

    filters = []
    identity_key = _trim(row.metadata_identity_key)
    if identity_key is not None:
        filters.append(MarketFmvSnapshot.metadata_identity_key == identity_key)
    canonical_issue_id = approved_canonical_issue_id if approved_canonical_issue_id is not None else row.canonical_issue_id
    if canonical_issue_id is not None:
        filters.append(MarketFmvSnapshot.canonical_issue_id == canonical_issue_id)
    if filters:
        stmt = stmt.where(or_(*filters))
    stmt = stmt.order_by(
        MarketFmvSnapshot.metadata_identity_key.asc().nullsfirst(),
        MarketFmvSnapshot.canonical_issue_id.asc().nullsfirst(),
        MarketFmvSnapshot.snapshot_scope.asc(),
        MarketFmvSnapshot.confidence_bucket.asc(),
        MarketFmvSnapshot.liquidity_bucket.asc(),
        MarketFmvSnapshot.stale_data.asc(),
        MarketFmvSnapshot.snapshot_date.desc(),
        MarketFmvSnapshot.valuation_method.asc(),
        MarketFmvSnapshot.id.desc(),
    )
    return session.exec(stmt).all()


def _snapshot_rank(snapshot: MarketFmvSnapshot, *, row: _ProjectionRow, exact_match: bool) -> tuple:
    if row.grade_status == "graded":
        scope_rank = {
            "graded_by_grade": 0,
            "graded_by_company": 1,
            "graded": 2,
            "raw": 3,
        }.get(snapshot.snapshot_scope, 99)
    else:
        scope_rank = {
            "raw": 0,
            "graded": 1,
            "graded_by_company": 2,
            "graded_by_grade": 3,
        }.get(snapshot.snapshot_scope, 99)
    confidence_rank = _CONFIDENCE_RANK.get(snapshot.confidence_bucket, 99)
    liquidity_rank = _LIQUIDITY_RANK.get(snapshot.liquidity_bucket, 99)
    method_rank = _METHOD_RANK.get(snapshot.valuation_method, 99)
    return (
        0 if exact_match else 1,
        scope_rank,
        confidence_rank,
        liquidity_rank,
        1 if snapshot.stale_data else 0,
        method_rank,
        -snapshot.snapshot_date.toordinal(),
        -int(snapshot.id or 0),
        _trim(snapshot.metadata_identity_key) or "",
        snapshot.canonical_issue_id or -1,
        row.inventory_copy_id,
    )


def _choose_snapshot(
    session: Session,
    *,
    row: _ProjectionRow,
    approved_canonical_issue_id: int | None,
) -> MarketFmvSnapshot | None:
    candidates = _candidate_snapshots(session, row=row, approved_canonical_issue_id=approved_canonical_issue_id)
    if not candidates:
        return None

    exact_identity = _trim(row.metadata_identity_key)
    canonical_issue_id = approved_canonical_issue_id if approved_canonical_issue_id is not None else row.canonical_issue_id
    exact_candidates = [
        snapshot
        for snapshot in candidates
        if (
            exact_identity is not None
            and _trim(snapshot.metadata_identity_key) == exact_identity
            and (canonical_issue_id is None or snapshot.canonical_issue_id == canonical_issue_id)
        )
    ]
    pool = exact_candidates if exact_candidates else candidates
    return sorted(pool, key=lambda snapshot: _snapshot_rank(snapshot, row=row, exact_match=snapshot in exact_candidates))[0]


def _trend_snapshot_for_value(
    session: Session,
    *,
    chosen_snapshot: MarketFmvSnapshot,
) -> MarketTrendSnapshotSummaryRead | None:
    stmt = select(MarketTrendSnapshot).where(
        MarketTrendSnapshot.currency_code == chosen_snapshot.currency_code,
        MarketTrendSnapshot.snapshot_scope == chosen_snapshot.snapshot_scope,
    )
    if chosen_snapshot.metadata_identity_key is not None:
        stmt = stmt.where(MarketTrendSnapshot.metadata_identity_key == chosen_snapshot.metadata_identity_key)
    elif chosen_snapshot.canonical_issue_id is not None:
        stmt = stmt.where(MarketTrendSnapshot.canonical_issue_id == chosen_snapshot.canonical_issue_id)
    stmt = stmt.order_by(
        MarketTrendSnapshot.updated_at.desc(),
        MarketTrendSnapshot.trend_window.asc(),
        MarketTrendSnapshot.id.desc(),
    )
    trend = session.exec(stmt).first()
    if trend is None:
        return None
    return MarketTrendSnapshotSummaryRead.model_validate(trend, from_attributes=True)


def _snapshot_read(
    session: Session,
    *,
    snapshot: MarketFmvSnapshot,
) -> MarketFmvSnapshotRead:
    refs = session.exec(
        select(MarketFmvCompReference)
        .where(MarketFmvCompReference.market_fmv_snapshot_id == int(snapshot.id or 0))
        .order_by(
            MarketFmvCompReference.excluded_reason.asc(),
            MarketFmvCompReference.weighting_factor.desc(),
            MarketFmvCompReference.market_sale_record_id.asc(),
            MarketFmvCompReference.id.asc(),
        )
    ).all()
    return MarketFmvSnapshotRead(
        **MarketFmvSnapshotSummaryRead.model_validate(snapshot, from_attributes=True).model_dump(),
        evidence_json=dict(snapshot.evidence_json or {}),
        comp_references=[
            MarketFmvCompReferenceRead(
                id=int(ref.id or 0),
                market_fmv_snapshot_id=ref.market_fmv_snapshot_id,
                market_sale_record_id=ref.market_sale_record_id,
                weighting_factor=ref.weighting_factor,
                included_reason=ref.included_reason,
                excluded_reason=ref.excluded_reason,
                created_at=ref.created_at,
                market_sale_record=None,
            )
            for ref in refs
        ],
    )


def build_inventory_fmv_attachment(
    session: Session,
    *,
    row: Mapping[str, Any],
    include_detail: bool = False,
) -> InventoryFmvAttachmentRead:
    projection = _projection_from_mapping(row)
    approved_canonical_issue_id = _approved_canonical_issue_id(session, inventory_copy_id=projection.inventory_copy_id)
    chosen_snapshot = _choose_snapshot(session, row=projection, approved_canonical_issue_id=approved_canonical_issue_id)

    ownership_state = str(row.get("ownership_state") or "unknown_state")
    order_status = projection.order_status
    release_status = projection.release_status
    is_cancelled = order_status == "cancelled"
    is_preorder = ownership_state == "preorder" or order_status == "preordered" or release_status == "not_released_yet"

    if chosen_snapshot is None:
        if is_cancelled:
            valuation_scope = "cancelled_excluded"
        elif is_preorder:
            valuation_scope = "preorder_pending"
        else:
            valuation_scope = "no_market_data"
        evidence = {
            "inventory_copy_id": projection.inventory_copy_id,
            "ownership_state": ownership_state,
            "order_status": order_status,
            "release_status": release_status,
            "approved_canonical_issue_id": approved_canonical_issue_id,
            "market_fmv_snapshot_id": None,
            "match_reason": "no_market_data" if not is_cancelled else "cancelled_excluded",
        }
        current_market_fmv = None
        conf_bucket = None
        liq_bucket = None
        copy_row = session.get(InventoryCopy, projection.inventory_copy_id)
        if copy_row is not None and copy_row.user_id is not None and valuation_scope not in {"preorder_pending", "cancelled_excluded"}:
            p68 = get_authoritative_fmv(session, owner_user_id=int(copy_row.user_id), inventory_copy_id=projection.inventory_copy_id)
            if p68 is not None:
                current_market_fmv = quantize_money(Decimal(str(p68.authoritative_fmv)))
                evidence.update(authoritative_fmv_to_evidence(p68))
                evidence["authoritative_source"] = "P68_MARKET_PRICING_ENGINE"
                conf_bucket = evidence.get("p68_confidence_bucket")
                liq_bucket = evidence.get("p68_liquidity_bucket")
                valuation_scope = "raw" if projection.grade_status == "raw" else "graded"
        return InventoryFmvAttachmentRead(
            inventory_copy_id=projection.inventory_copy_id,
            current_market_fmv=current_market_fmv,
            fmv_snapshot_id=None,
            fmv_method=None,
            fmv_confidence_bucket=conf_bucket,  # type: ignore[arg-type]
            fmv_liquidity_bucket=liq_bucket,  # type: ignore[arg-type]
            fmv_volatility_bucket=None,
            fmv_stale_data=None,
            fmv_currency_code="USD" if current_market_fmv is not None else None,
            valuation_scope=valuation_scope,
            valuation_evidence_json=evidence,
        )

    if is_cancelled:
        valuation_scope = "cancelled_excluded"
    elif is_preorder:
        valuation_scope = "preorder_pending"
    elif chosen_snapshot.confidence_bucket in {"low", "very_low"}:
        valuation_scope = "low_confidence"
    elif chosen_snapshot.snapshot_scope == "raw":
        valuation_scope = "raw"
    else:
        valuation_scope = "graded"

    current_market_fmv = None if valuation_scope in {"preorder_pending", "cancelled_excluded"} else quantize_money(
        Decimal(chosen_snapshot.estimated_fmv)
    )

    trend_snapshot = _trend_snapshot_for_value(session, chosen_snapshot=chosen_snapshot)
    snapshot_read: MarketFmvSnapshotRead | None = _snapshot_read(session, snapshot=chosen_snapshot) if include_detail else None
    evidence = {
            "inventory_copy_id": projection.inventory_copy_id,
            "title": projection.title,
            "publisher": projection.publisher,
            "issue_number": projection.issue_number,
            "ownership_state": ownership_state,
            "order_status": order_status,
            "release_status": release_status,
            "grade_status": projection.grade_status,
            "approved_canonical_issue_id": approved_canonical_issue_id,
            "market_fmv_snapshot_id": int(chosen_snapshot.id or 0),
            "market_fmv_snapshot_scope": chosen_snapshot.snapshot_scope,
            "market_fmv_confidence_bucket": chosen_snapshot.confidence_bucket,
            "market_fmv_liquidity_bucket": chosen_snapshot.liquidity_bucket,
            "market_fmv_volatility_bucket": chosen_snapshot.volatility_bucket,
            "market_fmv_stale_data": bool(chosen_snapshot.stale_data),
            "market_fmv_currency_code": chosen_snapshot.currency_code,
            "market_trend_snapshot_id": trend_snapshot.id if trend_snapshot is not None else None,
            "match_reason": "approved_canonical_issue" if approved_canonical_issue_id is not None else "exact_metadata_identity_key",
            "preorder_informational": is_preorder,
        }
    copy_row = session.get(InventoryCopy, projection.inventory_copy_id)
    conf_bucket = chosen_snapshot.confidence_bucket
    liq_bucket = chosen_snapshot.liquidity_bucket
    if copy_row is not None and copy_row.user_id is not None:
        p68 = get_authoritative_fmv(session, owner_user_id=int(copy_row.user_id), inventory_copy_id=projection.inventory_copy_id)
        if p68 is not None and valuation_scope not in {"preorder_pending", "cancelled_excluded"}:
            current_market_fmv = quantize_money(Decimal(str(p68.authoritative_fmv)))
            evidence.update(authoritative_fmv_to_evidence(p68))
            evidence["authoritative_source"] = "P68_MARKET_PRICING_ENGINE"
            conf_bucket = evidence.get("p68_confidence_bucket") or conf_bucket
            liq_bucket = evidence.get("p68_liquidity_bucket") or liq_bucket
    return InventoryFmvAttachmentRead(
        inventory_copy_id=projection.inventory_copy_id,
        current_market_fmv=current_market_fmv,
        fmv_snapshot_id=int(chosen_snapshot.id or 0),
        fmv_method=chosen_snapshot.valuation_method,
        fmv_confidence_bucket=conf_bucket,  # type: ignore[arg-type]
        fmv_liquidity_bucket=liq_bucket,  # type: ignore[arg-type]
            fmv_volatility_bucket=_attachment_volatility_bucket(chosen_snapshot.volatility_bucket),  # type: ignore[arg-type]
        fmv_stale_data=bool(chosen_snapshot.stale_data),
        fmv_currency_code=chosen_snapshot.currency_code,
        valuation_scope=valuation_scope,
        valuation_evidence_json=evidence,
        market_fmv_snapshot=snapshot_read,
        market_trend_snapshot=trend_snapshot,
    )


def inventory_fmv_context_for_scope(
    session: Session,
    *,
    owner_user_id: int | None,
    include_detail: bool = False,
) -> tuple[list[Mapping[str, Any]], dict[int, InventoryFmvAttachmentRead], dict[int, str | None]]:
    projections = _projection_rows(session, owner_user_id=owner_user_id)
    if owner_user_id is None:
        duplicate_groups = list_duplicate_ownership_ops(session, dup_scan_classification="all", classification=None).groups
        duplicate_map = duplicate_ownership_inventory_attach_map(duplicate_groups)
    else:
        _, duplicate_map = duplicate_ownership_inventory_context_for_owner(
            session,
            user=User(id=owner_user_id),
            dup_scan_classification="all",
        )
    duplicate_group_keys = {inv_id: attachment.group_key for inv_id, attachment in duplicate_map.items()}
    attachments: dict[int, InventoryFmvAttachmentRead] = {}
    row_maps: list[Mapping[str, Any]] = []
    for projection in projections:
        row_map = {
            "inventory_copy_id": projection.inventory_copy_id,
            "metadata_identity_key": projection.metadata_identity_key,
            "canonical_issue_id": projection.canonical_issue_id,
            "title": projection.title,
            "publisher": projection.publisher,
            "issue_number": projection.issue_number,
            "grade_status": projection.grade_status,
            "order_status": projection.order_status,
            "release_status": projection.release_status,
            "acquisition_cost": projection.acquisition_cost,
            "ownership_state": normalize_ownership_state(
                release_status=projection.release_status,
                order_status=projection.order_status,
                received_at=projection.received_at,
            ),
        }
        attachment = build_inventory_fmv_attachment(session, row=row_map, include_detail=include_detail)
        attachments[projection.inventory_copy_id] = attachment
        row_maps.append(row_map)
    return row_maps, attachments, duplicate_group_keys


def inventory_fmv_response_for_scope(
    session: Session,
    *,
    owner_user_id: int | None,
    page: int,
    page_size: int,
    publisher: str | None = None,
    ownership_state: str | None = None,
    valuation_scope: InventoryValuationScope | None = None,
    confidence_bucket: str | None = None,
    liquidity_bucket: str | None = None,
    stale_data: bool | None = None,
    currency_code: str | None = None,
) -> tuple[list[Mapping[str, Any]], dict[int, InventoryFmvAttachmentRead], PortfolioValueSummaryResponse, int]:
    row_maps, attachments, duplicate_group_keys = inventory_fmv_context_for_scope(
        session,
        owner_user_id=owner_user_id,
        include_detail=False,
    )
    filtered_rows: list[Mapping[str, Any]] = []
    for row in row_maps:
        attachment = attachments[int(row["inventory_copy_id"])]
        if publisher is not None and row["publisher"] != publisher:
            continue
        if ownership_state is not None and row["ownership_state"] != ownership_state:
            continue
        if valuation_scope is not None and attachment.valuation_scope != valuation_scope:
            continue
        if confidence_bucket is not None and attachment.fmv_confidence_bucket != confidence_bucket:
            continue
        if liquidity_bucket is not None and attachment.fmv_liquidity_bucket != liquidity_bucket:
            continue
        if stale_data is not None and bool(attachment.fmv_stale_data) != stale_data:
            continue
        if currency_code is not None and (attachment.fmv_currency_code or "").upper() != currency_code.strip().upper():
            continue
        filtered_rows.append(row)
    summary = summarize_inventory_fmv(
        filtered_rows,
        attachments,
        duplicate_group_keys=duplicate_group_keys,
        scope="owner" if owner_user_id is not None else "ops",
        scope_user_id=owner_user_id,
    )
    start = (page - 1) * page_size
    end = start + page_size
    return filtered_rows[start:end], attachments, summary, len(filtered_rows)


def inventory_fmv_inventory_response_for_scope(
    session: Session,
    *,
    owner_user_id: int | None,
    page: int,
    page_size: int,
    publisher: str | None = None,
    ownership_state: str | None = None,
    valuation_scope: InventoryValuationScope | None = None,
    confidence_bucket: str | None = None,
    liquidity_bucket: str | None = None,
    stale_data: bool | None = None,
    currency_code: str | None = None,
) -> InventoryListResponse:
    rows, attachments, _summary, total = inventory_fmv_response_for_scope(
        session,
        owner_user_id=owner_user_id,
        page=page,
        page_size=page_size,
        publisher=publisher,
        ownership_state=ownership_state,
        valuation_scope=valuation_scope,
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        stale_data=stale_data,
        currency_code=currency_code,
    )
    items: list[InventoryRow] = []
    for row in rows:
        inv_id = int(row["inventory_copy_id"])
        attachment = attachments[inv_id]
        row_map = dict(row)
        row_map["current_market_fmv"] = attachment.current_market_fmv
        row_map["fmv_snapshot_id"] = attachment.fmv_snapshot_id
        row_map["fmv_method"] = attachment.fmv_method
        row_map["fmv_confidence_bucket"] = attachment.fmv_confidence_bucket
        row_map["fmv_liquidity_bucket"] = attachment.fmv_liquidity_bucket
        row_map["fmv_volatility_bucket"] = attachment.fmv_volatility_bucket
        row_map["fmv_stale_data"] = attachment.fmv_stale_data
        row_map["fmv_currency_code"] = attachment.fmv_currency_code
        row_map["valuation_scope"] = attachment.valuation_scope
        row_map["valuation_evidence_json"] = attachment.valuation_evidence_json
        items.append(InventoryRow.model_validate(row_map))
    return InventoryListResponse(page=page, page_size=page_size, total=total, items=items)


def inventory_fmv_detail_for_scope(
    session: Session,
    *,
    owner_user_id: int | None,
    inventory_copy_id: int,
    include_detail: bool = True,
) -> InventoryFmvAttachmentRead:
    projections = _projection_rows(
        session,
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
    )
    if not projections:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    projection = projections[0]
    row_map = {
        "inventory_copy_id": projection.inventory_copy_id,
        "metadata_identity_key": projection.metadata_identity_key,
        "canonical_issue_id": projection.canonical_issue_id,
        "title": projection.title,
        "publisher": projection.publisher,
        "issue_number": projection.issue_number,
        "grade_status": projection.grade_status,
        "order_status": projection.order_status,
        "release_status": projection.release_status,
        "acquisition_cost": projection.acquisition_cost,
        "ownership_state": normalize_ownership_state(
            release_status=projection.release_status,
            order_status=projection.order_status,
            received_at=projection.received_at,
        ),
    }
    return build_inventory_fmv_attachment(session, row=row_map, include_detail=include_detail)


def portfolio_value_summary_for_scope(
    session: Session,
    *,
    owner_user_id: int | None,
    publisher: str | None = None,
    ownership_state: str | None = None,
    valuation_scope: InventoryValuationScope | None = None,
    confidence_bucket: str | None = None,
    liquidity_bucket: str | None = None,
    stale_data: bool | None = None,
    currency_code: str | None = None,
) -> PortfolioValueSummaryResponse:
    rows, attachments, duplicate_group_keys = inventory_fmv_context_for_scope(
        session,
        owner_user_id=owner_user_id,
        include_detail=False,
    )
    filtered_rows: list[Mapping[str, Any]] = []
    for row in rows:
        attachment = attachments[int(row["inventory_copy_id"])]
        if publisher is not None and row["publisher"] != publisher:
            continue
        if ownership_state is not None and row["ownership_state"] != ownership_state:
            continue
        if valuation_scope is not None and attachment.valuation_scope != valuation_scope:
            continue
        if confidence_bucket is not None and attachment.fmv_confidence_bucket != confidence_bucket:
            continue
        if liquidity_bucket is not None and attachment.fmv_liquidity_bucket != liquidity_bucket:
            continue
        if stale_data is not None and bool(attachment.fmv_stale_data) != stale_data:
            continue
        if currency_code is not None and (attachment.fmv_currency_code or "").upper() != currency_code.strip().upper():
            continue
        filtered_rows.append(row)
    return summarize_inventory_fmv(
        filtered_rows,
        attachments,
        duplicate_group_keys=duplicate_group_keys,
        scope="owner" if owner_user_id is not None else "ops",
        scope_user_id=owner_user_id,
    )


def summarize_inventory_fmv(
    rows: list[Mapping[str, Any]],
    attachments: dict[int, InventoryFmvAttachmentRead],
    *,
    duplicate_group_keys: dict[int, str | None] | None = None,
    scope: Literal["owner", "ops"],
    scope_user_id: int | None,
    generated_as_of_date: date | None = None,
) -> PortfolioValueSummaryResponse:
    generated_as_of_date = generated_as_of_date or date.today()
    duplicate_group_keys = duplicate_group_keys or {}

    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total_active_market_value": ZERO,
            "raw_market_value": ZERO,
            "graded_market_value": ZERO,
            "preorder_informational_value": ZERO,
            "low_confidence_value": ZERO,
            "stale_value": ZERO,
            "no_market_data_count": 0,
            "cancelled_excluded_count": 0,
            "duplicate_group_total_value": ZERO,
            "duplicate_extra_copy_value": ZERO,
            "duplicate_value_exposure": ZERO,
            "duplicate_raw_value": ZERO,
            "duplicate_graded_value": ZERO,
            "_duplicate_members": defaultdict(list),
        },
    )

    for row in rows:
        inv_id = int(row["inventory_copy_id"])
        attachment = attachments[inv_id]
        currency = attachment.fmv_currency_code or "UNKNOWN"
        bucket = buckets[currency]
        value = attachment.current_market_fmv
        if attachment.valuation_scope == "cancelled_excluded":
            bucket["cancelled_excluded_count"] += 1
            continue
        if attachment.valuation_scope == "no_market_data":
            bucket["no_market_data_count"] += 1
            continue
        if value is None:
            continue
        if attachment.valuation_scope == "preorder_pending":
            bucket["preorder_informational_value"] += value
        elif attachment.valuation_scope == "low_confidence":
            bucket["low_confidence_value"] += value
        else:
            bucket["total_active_market_value"] += value
            if attachment.valuation_scope == "raw":
                bucket["raw_market_value"] += value
            elif attachment.valuation_scope == "graded":
                bucket["graded_market_value"] += value
        if attachment.fmv_stale_data:
            bucket["stale_value"] += value
        if duplicate_group_keys.get(inv_id):
            bucket["_duplicate_members"][duplicate_group_keys[inv_id]].append((inv_id, attachment))

    summaries: list[PortfolioValueCurrencySummaryRead] = []
    for currency in sorted(buckets):
        bucket = buckets[currency]
        duplicate_group_total_value = ZERO
        duplicate_extra_copy_value = ZERO
        duplicate_value_exposure = ZERO
        duplicate_raw_value = ZERO
        duplicate_graded_value = ZERO
        for group_key, members in bucket["_duplicate_members"].items():
            del group_key
            ordered_members = sorted(members, key=lambda item: item[0])
            for position, (_inv_id, attachment) in enumerate(ordered_members):
                if attachment.current_market_fmv is None:
                    continue
                duplicate_group_total_value += attachment.current_market_fmv
                if position > 0:
                    duplicate_extra_copy_value += attachment.current_market_fmv
                    duplicate_value_exposure += attachment.current_market_fmv
                if attachment.valuation_scope == "raw":
                    duplicate_raw_value += attachment.current_market_fmv
                elif attachment.valuation_scope == "graded":
                    duplicate_graded_value += attachment.current_market_fmv

        summaries.append(
            PortfolioValueCurrencySummaryRead(
                currency_code=currency,
                total_active_market_value=quantize_money(bucket["total_active_market_value"]),
                raw_market_value=quantize_money(bucket["raw_market_value"]),
                graded_market_value=quantize_money(bucket["graded_market_value"]),
                preorder_informational_value=quantize_money(bucket["preorder_informational_value"]),
                low_confidence_value=quantize_money(bucket["low_confidence_value"]),
                stale_value=quantize_money(bucket["stale_value"]),
                no_market_data_count=int(bucket["no_market_data_count"]),
                cancelled_excluded_count=int(bucket["cancelled_excluded_count"]),
                duplicate_group_total_value=quantize_money(duplicate_group_total_value),
                duplicate_extra_copy_value=quantize_money(duplicate_extra_copy_value),
                duplicate_value_exposure=quantize_money(duplicate_value_exposure),
                duplicate_raw_value=quantize_money(duplicate_raw_value),
                duplicate_graded_value=quantize_money(duplicate_graded_value),
            )
        )

    return PortfolioValueSummaryResponse(
        scope=scope,
        scope_user_id=scope_user_id,
        generated_as_of_date=generated_as_of_date,
        items=summaries,
    )

