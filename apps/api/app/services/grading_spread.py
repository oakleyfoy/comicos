"""P37-02 deterministic raw-vs-graded spread intelligence."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    GradingSpreadBand,
    GradingSpreadEvidence,
    GradingSpreadHistory,
    GradingSpreadSnapshot,
    InventoryCopy,
    InventoryFmvSnapshot,
    InventoryLiquiditySnapshot,
    Listing,
    ListingIntelligenceSnapshot,
    MarketFmvSnapshot,
    MarketSaleRecord,
    SaleRecord,
    Variant,
)
from app.schemas.grading_spread import (
    GradingSpreadDashboardSummary,
    GradingSpreadDetailRead,
    GradingSpreadEvidenceListResponse,
    GradingSpreadEvidenceRead,
    GradingSpreadGeneratePayload,
    GradingSpreadHistoryListResponse,
    GradingSpreadHistoryRead,
    GradingSpreadListResponse,
    GradingSpreadRead,
    InventoryGradingSpreadBadge,
)

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
ZERO = Decimal("0.00")

LIQUIDITY_WEIGHTS: dict[str, Decimal] = {
    "HIGH": Decimal("1.00"),
    "MEDIUM": Decimal("0.85"),
    "LOW": Decimal("0.65"),
}

DEFAULT_GRADING_COSTS: dict[str, Decimal] = {
    "PSA": Decimal("25.00"),
    "CGC": Decimal("30.00"),
    "CBCS": Decimal("28.00"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_grading_spread_pagination(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal | None:
    dec = _decimal(value)
    if dec is None:
        return None
    return dec.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _pct(value: Any | None) -> Decimal | None:
    dec = _decimal(value)
    if dec is None:
        return None
    return dec.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        quant = value.quantize(PCT_QUANT if value.copy_abs() < Decimal("1000") else MONEY_QUANT)
        return format(quant, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def deterministic_checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _inventory_row(
    session: Session,
    *,
    owner_user_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> tuple[InventoryCopy, int]:
    stmt = select(InventoryCopy).join(Variant, InventoryCopy.variant_id == Variant.id).join(
        ComicIssue, Variant.comic_issue_id == ComicIssue.id
    )
    if owner_user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == owner_user_id)
    if inventory_item_id is not None:
        stmt = stmt.where(InventoryCopy.id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        stmt = stmt.where(ComicIssue.id == canonical_comic_issue_id)
    row = session.exec(stmt.order_by(InventoryCopy.id.asc())).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")
    issue_id = int(session.exec(select(Variant.comic_issue_id).where(Variant.id == row.variant_id)).one())
    return row, issue_id


def _latest_inventory_fmv(session: Session, inventory_item_id: int) -> Decimal | None:
    row = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == inventory_item_id)
        .order_by(col(InventoryFmvSnapshot.changed_at).desc())
        .order_by(col(InventoryFmvSnapshot.id).desc())
    ).first()
    if row is not None:
        return _money(row.new_fmv)
    inv = session.get(InventoryCopy, inventory_item_id)
    return _money(inv.current_fmv) if inv is not None else None


def _latest_graded_fmv(
    session: Session,
    *,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
) -> tuple[Decimal | None, MarketFmvSnapshot | None]:
    stmt = select(MarketFmvSnapshot).where(
        MarketFmvSnapshot.canonical_issue_id == canonical_comic_issue_id,
        MarketFmvSnapshot.snapshot_scope.in_(["graded", "graded_by_company", "graded_by_grade"]),
        MarketFmvSnapshot.grading_company == target_grader,
    )
    if target_grade is not None:
        stmt = stmt.where(MarketFmvSnapshot.normalized_grade == target_grade)
    row = session.exec(
        stmt.order_by(col(MarketFmvSnapshot.snapshot_date).desc()).order_by(col(MarketFmvSnapshot.id).desc())
    ).first()
    if row is None:
        return None, None
    return _money(row.estimated_fmv), row


def _latest_liquidity_snapshot(
    session: Session,
    *,
    owner_user_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> InventoryLiquiditySnapshot | None:
    stmt = select(InventoryLiquiditySnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(InventoryLiquiditySnapshot.owner_user_id == owner_user_id)
    if inventory_item_id is not None:
        stmt = stmt.where(InventoryLiquiditySnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        stmt = stmt.where(InventoryLiquiditySnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    return session.exec(
        stmt.order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc()).order_by(
            col(InventoryLiquiditySnapshot.id).desc()
        )
    ).first()


def _latest_listing_intelligence_snapshot(
    session: Session,
    *,
    owner_user_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> ListingIntelligenceSnapshot | None:
    stmt = select(ListingIntelligenceSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(ListingIntelligenceSnapshot.owner_user_id == owner_user_id)
    if inventory_item_id is not None:
        stmt = stmt.where(ListingIntelligenceSnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        stmt = stmt.where(ListingIntelligenceSnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    return session.exec(
        stmt.order_by(col(ListingIntelligenceSnapshot.snapshot_date).desc()).order_by(
            col(ListingIntelligenceSnapshot.id).desc()
        )
    ).first()


def _latest_sales_ledger_sale(session: Session, inventory_item_id: int) -> SaleRecord | None:
    return session.exec(
        select(SaleRecord)
        .join(Listing, SaleRecord.listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(SaleRecord.sale_date).desc())
        .order_by(col(SaleRecord.id).desc())
    ).first()


def _latest_market_sale_record(session: Session, inventory_item_id: int) -> MarketSaleRecord | None:
    return session.exec(
        select(MarketSaleRecord)
        .join(Listing, MarketSaleRecord.source_listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(MarketSaleRecord.sale_date).desc().nullslast())
        .order_by(col(MarketSaleRecord.id).desc())
    ).first()


def _liquidity_modifier(status_value: str | None) -> tuple[str, Decimal]:
    normalized = (status_value or "LOW").upper()
    if normalized == "HIGH":
        return "HIGH", LIQUIDITY_WEIGHTS["HIGH"]
    if normalized == "MODERATE":
        return "MEDIUM", LIQUIDITY_WEIGHTS["MEDIUM"]
    return "LOW", LIQUIDITY_WEIGHTS["LOW"]


def _confidence_level(*, evidence_count: int, has_raw: bool, has_graded: bool, has_liquidity: bool) -> str:
    if not has_raw or not has_graded or not has_liquidity:
        return "LOW"
    if evidence_count >= 5:
        return "HIGH"
    if evidence_count >= 2:
        return "MEDIUM"
    return "LOW"


def _spread_status(
    *,
    estimated_spread_amount: Decimal | None,
    estimated_net_upside: Decimal | None,
    estimated_spread_pct: Decimal | None,
    liquidity_modifier: str,
    confidence_level: str,
    has_raw: bool,
    has_graded: bool,
    has_liquidity: bool,
) -> str:
    if not has_raw or not has_graded or not has_liquidity:
        return "INSUFFICIENT_DATA"
    if estimated_net_upside is None or estimated_spread_amount is None:
        return "INSUFFICIENT_DATA"
    if estimated_net_upside < ZERO:
        return "NEGATIVE"
    if estimated_net_upside < Decimal("25.00") or (estimated_spread_pct is not None and estimated_spread_pct < Decimal("15.00")):
        return "WEAK"
    if (
        estimated_net_upside >= Decimal("120.00")
        and estimated_spread_pct is not None
        and estimated_spread_pct >= Decimal("50.00")
        and liquidity_modifier == "HIGH"
        and confidence_level == "HIGH"
    ):
        return "ELITE"
    if (
        estimated_net_upside >= Decimal("60.00")
        and liquidity_modifier in {"HIGH", "MEDIUM"}
        and confidence_level in {"HIGH", "MEDIUM"}
    ):
        return "STRONG"
    return "MODERATE"


def _band_override_status(
    session: Session,
    *,
    target_grader: str,
    target_grade: str | None,
    estimated_spread_pct: Decimal | None,
    default_status: str,
) -> str:
    if estimated_spread_pct is None:
        return default_status
    bands = session.exec(
        select(GradingSpreadBand)
        .where(GradingSpreadBand.target_grader == target_grader)
        .where(GradingSpreadBand.target_grade == target_grade)
        .order_by(col(GradingSpreadBand.lower_bound_pct).asc(), col(GradingSpreadBand.id).asc())
    ).all()
    for band in bands:
        if band.lower_bound_pct <= estimated_spread_pct < band.upper_bound_pct:
            return band.status_label
    bands = session.exec(
        select(GradingSpreadBand)
        .where(GradingSpreadBand.target_grader == target_grader)
        .where(GradingSpreadBand.target_grade.is_(None))
        .order_by(col(GradingSpreadBand.lower_bound_pct).asc(), col(GradingSpreadBand.id).asc())
    ).all()
    for band in bands:
        if band.lower_bound_pct <= estimated_spread_pct < band.upper_bound_pct:
            return band.status_label
    return default_status


def _evidence_payload_rows(
    *,
    raw_fmv_amount: Decimal | None,
    graded_fmv_amount: Decimal | None,
    grading_cost_amount: Decimal | None,
    liquidity_snapshot: InventoryLiquiditySnapshot | None,
    sales_ledger_sale: SaleRecord | None,
    market_sale_record: MarketSaleRecord | None,
    listing_intelligence_snapshot: ListingIntelligenceSnapshot | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if raw_fmv_amount is not None:
        rows.append(
            {
                "evidence_type": "RAW_FMV",
                "source_id": None,
                "source_table": "inventory_fmv_snapshot",
                "evidence_value_json": {"raw_fmv_amount": raw_fmv_amount},
            }
        )
    if graded_fmv_amount is not None:
        rows.append(
            {
                "evidence_type": "GRADED_FMV",
                "source_id": None,
                "source_table": "market_fmv_snapshot",
                "evidence_value_json": {"graded_fmv_amount": graded_fmv_amount},
            }
        )
    if liquidity_snapshot is not None:
        rows.append(
            {
                "evidence_type": "LIQUIDITY",
                "source_id": int(liquidity_snapshot.id or 0),
                "source_table": "inventory_liquidity_snapshot",
                "evidence_value_json": {
                    "liquidity_status": liquidity_snapshot.liquidity_status,
                    "liquidity_confidence": liquidity_snapshot.liquidity_confidence,
                    "sell_through_rate_pct": liquidity_snapshot.sell_through_rate_pct,
                    "stale_listing_rate_pct": liquidity_snapshot.stale_listing_rate_pct,
                },
            }
        )
    if sales_ledger_sale is not None:
        rows.append(
            {
                "evidence_type": "SALES_LEDGER",
                "source_id": int(sales_ledger_sale.id or 0),
                "source_table": "sale_record",
                "evidence_value_json": {
                    "sale_date": sales_ledger_sale.sale_date,
                    "net_proceeds_amount": sales_ledger_sale.net_proceeds_amount,
                    "realized_profit_amount": sales_ledger_sale.realized_profit_amount,
                },
            }
        )
    if market_sale_record is not None:
        rows.append(
            {
                "evidence_type": "MARKET_SALE",
                "source_id": int(market_sale_record.id or 0),
                "source_table": "market_sale_record",
                "evidence_value_json": {
                    "sale_price": market_sale_record.sale_price,
                    "sale_date": market_sale_record.sale_date,
                    "normalized_grade": market_sale_record.normalized_grade,
                },
            }
        )
    if listing_intelligence_snapshot is not None:
        rows.append(
            {
                "evidence_type": "LISTING_INTELLIGENCE",
                "source_id": int(listing_intelligence_snapshot.id or 0),
                "source_table": "listing_intelligence_snapshot",
                "evidence_value_json": {
                    "intelligence_status": listing_intelligence_snapshot.intelligence_status,
                    "completeness_score": listing_intelligence_snapshot.completeness_score,
                    "export_readiness_score": listing_intelligence_snapshot.export_readiness_score,
                },
            }
        )
    return rows


def _snapshot_signature_payload(
    *,
    owner_user_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
    raw_fmv_amount: Decimal | None,
    graded_fmv_amount: Decimal | None,
    grading_cost_amount: Decimal | None,
    estimated_spread_amount: Decimal | None,
    estimated_spread_pct: Decimal | None,
    estimated_net_upside: Decimal | None,
    liquidity_adjusted_upside: Decimal | None,
    spread_status: str,
    liquidity_modifier: str,
    confidence_level: str,
    snapshot_date: date,
) -> dict[str, Any]:
    return {
        "owner_user_id": owner_user_id,
        "inventory_item_id": inventory_item_id,
        "canonical_comic_issue_id": canonical_comic_issue_id,
        "target_grader": target_grader,
        "target_grade": target_grade,
        "raw_fmv_amount": raw_fmv_amount,
        "graded_fmv_amount": graded_fmv_amount,
        "grading_cost_amount": grading_cost_amount,
        "estimated_spread_amount": estimated_spread_amount,
        "estimated_spread_pct": estimated_spread_pct,
        "estimated_net_upside": estimated_net_upside,
        "liquidity_adjusted_upside": liquidity_adjusted_upside,
        "spread_status": spread_status,
        "liquidity_modifier": liquidity_modifier,
        "confidence_level": confidence_level,
        "snapshot_date": snapshot_date,
    }


def _history_checksum(
    *,
    owner_user_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
    spread_amount: Decimal | None,
    spread_pct: Decimal | None,
    snapshot_date: date,
) -> str:
    payload = {
        "owner_user_id": owner_user_id,
        "inventory_item_id": inventory_item_id,
        "canonical_comic_issue_id": canonical_comic_issue_id,
        "target_grader": target_grader,
        "target_grade": target_grade,
        "spread_amount": spread_amount,
        "spread_pct": spread_pct,
        "snapshot_date": snapshot_date,
    }
    return deterministic_checksum(payload)


def _snapshot_read(row: GradingSpreadSnapshot) -> GradingSpreadRead:
    return GradingSpreadRead.model_validate(row, from_attributes=True)


def _evidence_read(row: GradingSpreadEvidence) -> GradingSpreadEvidenceRead:
    return GradingSpreadEvidenceRead.model_validate(row, from_attributes=True)


def _history_read(row: GradingSpreadHistory) -> GradingSpreadHistoryRead:
    return GradingSpreadHistoryRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, snapshot: GradingSpreadSnapshot) -> GradingSpreadDetailRead:
    sid = int(snapshot.id or 0)
    evidence_rows = session.exec(
        select(GradingSpreadEvidence)
        .where(GradingSpreadEvidence.grading_spread_snapshot_id == sid)
        .order_by(col(GradingSpreadEvidence.created_at).asc(), col(GradingSpreadEvidence.id).asc())
    ).all()
    history_rows = session.exec(
        select(GradingSpreadHistory)
        .where(GradingSpreadHistory.canonical_comic_issue_id == snapshot.canonical_comic_issue_id)
        .where(GradingSpreadHistory.target_grader == snapshot.target_grader)
        .where(GradingSpreadHistory.target_grade == snapshot.target_grade)
        .order_by(col(GradingSpreadHistory.snapshot_date).desc(), col(GradingSpreadHistory.id).desc())
    ).all()
    return GradingSpreadDetailRead(
        snapshot=_snapshot_read(snapshot),
        evidence=[_evidence_read(row) for row in evidence_rows],
        history=[_history_read(row) for row in history_rows],
    )


def _candidate_snapshot_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    spread_status: str | None = None,
    confidence_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
) -> Any:
    q = select(GradingSpreadSnapshot)
    if owner_user_id is not None:
        q = q.where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
    if inventory_item_id is not None:
        q = q.where(GradingSpreadSnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        q = q.where(GradingSpreadSnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    if target_grader is not None:
        q = q.where(GradingSpreadSnapshot.target_grader == target_grader)
    if target_grade is not None:
        q = q.where(GradingSpreadSnapshot.target_grade == target_grade)
    if spread_status is not None:
        q = q.where(GradingSpreadSnapshot.spread_status == spread_status)
    if confidence_level is not None:
        q = q.where(GradingSpreadSnapshot.confidence_level == confidence_level)
    if snapshot_date_from is not None:
        q = q.where(GradingSpreadSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(GradingSpreadSnapshot.snapshot_date <= snapshot_date_to)
    return q


def _build_row(
    session: Session,
    *,
    owner_user_id: int | None,
    inventory_row: InventoryCopy,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
    snapshot_date: date,
    replay_key: str | None,
    generation_params_json: dict[str, Any],
) -> tuple[GradingSpreadSnapshot, bool]:
    raw_fmv = _latest_inventory_fmv(session, int(inventory_row.id or 0))
    graded_fmv, graded_snapshot = _latest_graded_fmv(
        session,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
    )
    liquidity_snapshot = _latest_liquidity_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory_row.id or 0),
        canonical_comic_issue_id=canonical_comic_issue_id,
    )
    sales_ledger_sale = _latest_sales_ledger_sale(session, int(inventory_row.id or 0))
    market_sale_record = _latest_market_sale_record(session, int(inventory_row.id or 0))
    listing_intel = _latest_listing_intelligence_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory_row.id or 0),
        canonical_comic_issue_id=canonical_comic_issue_id,
    )

    has_raw = raw_fmv is not None
    has_graded = graded_fmv is not None
    has_liquidity = liquidity_snapshot is not None

    spread_amount = _money(graded_fmv - raw_fmv) if has_raw and has_graded else None
    spread_pct = _pct((spread_amount / raw_fmv) * Decimal("100")) if spread_amount is not None and raw_fmv not in (None, ZERO) else None
    grading_cost_amount = _money(
        sales_ledger_sale.other_cost_amount if sales_ledger_sale is not None else None
    ) or _money(DEFAULT_GRADING_COSTS.get(target_grader)) or ZERO
    net_upside = _money((spread_amount - grading_cost_amount) if spread_amount is not None else None)
    liq_label, liq_weight = _liquidity_modifier(liquidity_snapshot.liquidity_status if liquidity_snapshot else None)
    liquidity_adjusted = _money(net_upside * liq_weight) if net_upside is not None else None

    evidence_payload_rows = _evidence_payload_rows(
        raw_fmv_amount=raw_fmv,
        graded_fmv_amount=graded_fmv,
        grading_cost_amount=grading_cost_amount,
        liquidity_snapshot=liquidity_snapshot,
        sales_ledger_sale=sales_ledger_sale,
        market_sale_record=market_sale_record,
        listing_intelligence_snapshot=listing_intel,
    )
    evidence_count = len(evidence_payload_rows)
    confidence_level = _confidence_level(
        evidence_count=evidence_count,
        has_raw=has_raw,
        has_graded=has_graded,
        has_liquidity=has_liquidity,
    )
    spread_status = _spread_status(
        estimated_spread_amount=spread_amount,
        estimated_net_upside=net_upside,
        estimated_spread_pct=spread_pct,
        liquidity_modifier=liq_label,
        confidence_level=confidence_level,
        has_raw=has_raw,
        has_graded=has_graded,
        has_liquidity=has_liquidity,
    )
    spread_status = _band_override_status(
        session,
        target_grader=target_grader,
        target_grade=target_grade,
        estimated_spread_pct=spread_pct,
        default_status=spread_status,
    )
    checksum = deterministic_checksum(
        _snapshot_signature_payload(
            owner_user_id=owner_user_id,
            inventory_item_id=int(inventory_row.id or 0),
            canonical_comic_issue_id=canonical_comic_issue_id,
            target_grader=target_grader,
            target_grade=target_grade,
            raw_fmv_amount=raw_fmv,
            graded_fmv_amount=graded_fmv,
            grading_cost_amount=grading_cost_amount,
            estimated_spread_amount=spread_amount,
            estimated_spread_pct=spread_pct,
            estimated_net_upside=net_upside,
            liquidity_adjusted_upside=liquidity_adjusted,
            spread_status=spread_status,
            liquidity_modifier=liq_label,
            confidence_level=confidence_level,
            snapshot_date=snapshot_date,
        )
    )

    if replay_key is not None:
        existing = session.exec(
            select(GradingSpreadSnapshot).where(
                GradingSpreadSnapshot.owner_user_id == owner_user_id,
                GradingSpreadSnapshot.replay_key == replay_key,
            )
        ).first()
        if existing is not None:
            return existing, True

    existing = session.exec(
        select(GradingSpreadSnapshot).where(
            GradingSpreadSnapshot.checksum == checksum,
            GradingSpreadSnapshot.inventory_item_id == int(inventory_row.id or 0),
            GradingSpreadSnapshot.target_grader == target_grader,
            GradingSpreadSnapshot.target_grade == target_grade,
            GradingSpreadSnapshot.snapshot_date == snapshot_date,
        )
    ).first()
    if existing is not None:
        return existing, True

    snapshot = GradingSpreadSnapshot(
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory_row.id or 0),
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        raw_fmv_amount=raw_fmv,
        graded_fmv_amount=graded_fmv,
        grading_cost_amount=grading_cost_amount,
        estimated_spread_amount=spread_amount,
        estimated_spread_pct=spread_pct,
        estimated_net_upside=net_upside,
        liquidity_adjusted_upside=liquidity_adjusted,
        spread_status=spread_status,
        liquidity_modifier=liq_label,
        confidence_level=confidence_level,
        evidence_count=evidence_count,
        checksum=checksum,
        snapshot_date=snapshot_date,
        replay_key=replay_key,
        generation_params_json=generation_params_json,
        created_at=utc_now(),
    )
    session.add(snapshot)
    session.flush()
    for payload in evidence_payload_rows:
        session.add(
            GradingSpreadEvidence(
                grading_spread_snapshot_id=int(snapshot.id or 0),
                evidence_type=payload["evidence_type"],
                source_id=payload["source_id"],
                source_table=payload["source_table"],
                evidence_value_json=_json_safe(payload["evidence_value_json"]),
                created_at=utc_now(),
            )
        )
    history_checksum = _history_checksum(
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory_row.id or 0),
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        spread_amount=spread_amount,
        spread_pct=spread_pct,
        snapshot_date=snapshot_date,
    )
    session.add(
        GradingSpreadHistory(
            owner_user_id=owner_user_id,
            inventory_item_id=int(inventory_row.id or 0),
            canonical_comic_issue_id=canonical_comic_issue_id,
            target_grader=target_grader,
            target_grade=target_grade,
            spread_amount=spread_amount,
            spread_pct=spread_pct,
            snapshot_date=snapshot_date,
            checksum=history_checksum,
            created_at=utc_now(),
        )
    )
    session.commit()
    session.refresh(snapshot)
    return snapshot, False


def generate_grading_spread(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingSpreadGeneratePayload,
) -> tuple[GradingSpreadDetailRead, bool]:
    target_grader = payload.target_grader.upper()
    target_grade = payload.target_grade.strip() if payload.target_grade else None
    snapshot_date = payload.snapshot_date or utc_now().date()
    replay_key = payload.replay_key.strip() if payload.replay_key else None

    if payload.inventory_item_id is None and payload.canonical_comic_issue_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="inventory_item_id or canonical_comic_issue_id is required",
        )

    inventory_row, canonical_comic_issue_id = _inventory_row(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=payload.inventory_item_id,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
    )
    if payload.canonical_comic_issue_id is not None and canonical_comic_issue_id != payload.canonical_comic_issue_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="inventory item does not match issue")

    snapshot, replayed = _build_row(
        session,
        owner_user_id=owner_user_id,
        inventory_row=inventory_row,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        snapshot_date=snapshot_date,
        replay_key=replay_key,
        generation_params_json=payload.model_dump(mode="json"),
    )
    return _detail_read(session, snapshot), replayed


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> GradingSpreadDashboardSummary:
    rows = session.exec(
        select(GradingSpreadSnapshot).where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
    ).all()
    strong = sum(1 for row in rows if row.spread_status == "STRONG")
    elite = sum(1 for row in rows if row.spread_status == "ELITE")
    negative = sum(1 for row in rows if row.spread_status == "NEGATIVE")
    upside_values = [row.estimated_net_upside for row in rows if row.estimated_net_upside is not None]
    liq_values = [row.liquidity_adjusted_upside for row in rows if row.liquidity_adjusted_upside is not None]
    avg_upside = _money(sum(upside_values, ZERO) / Decimal(len(upside_values))) if upside_values else None
    liq_total = _money(sum(liq_values, ZERO)) if liq_values else None
    return GradingSpreadDashboardSummary(
        strong_spread_count=strong,
        elite_spread_count=elite,
        negative_spread_count=negative,
        average_estimated_upside=avg_upside,
        liquidity_adjusted_upside_total=liq_total,
    )


def dashboard_summary_ops(session: Session, *, owner_user_id: int | None = None) -> GradingSpreadDashboardSummary:
    rows = session.exec(select(GradingSpreadSnapshot)).all()
    if owner_user_id is not None:
        rows = [row for row in rows if row.owner_user_id == owner_user_id]
    strong = sum(1 for row in rows if row.spread_status == "STRONG")
    elite = sum(1 for row in rows if row.spread_status == "ELITE")
    negative = sum(1 for row in rows if row.spread_status == "NEGATIVE")
    upside_values = [row.estimated_net_upside for row in rows if row.estimated_net_upside is not None]
    liq_values = [row.liquidity_adjusted_upside for row in rows if row.liquidity_adjusted_upside is not None]
    avg_upside = _money(sum(upside_values, ZERO) / Decimal(len(upside_values))) if upside_values else None
    liq_total = _money(sum(liq_values, ZERO)) if liq_values else None
    return GradingSpreadDashboardSummary(
        strong_spread_count=strong,
        elite_spread_count=elite,
        negative_spread_count=negative,
        average_estimated_upside=avg_upside,
        liquidity_adjusted_upside_total=liq_total,
    )


def list_spreads_owner(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    spread_status: str | None = None,
    confidence_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSpreadSnapshot], int]:
    q = _candidate_snapshot_query(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        spread_status=spread_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSpreadSnapshot.snapshot_date).desc())
        .order_by(col(GradingSpreadSnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_spreads_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    spread_status: str | None = None,
    confidence_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSpreadSnapshot], int]:
    q = _candidate_snapshot_query(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        spread_status=spread_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSpreadSnapshot.snapshot_date).desc())
        .order_by(col(GradingSpreadSnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def get_spread_owner(session: Session, *, owner_user_id: int, spread_id: int) -> GradingSpreadSnapshot:
    row = session.get(GradingSpreadSnapshot, spread_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading spread not found")
    return row


def get_spread_ops(session: Session, *, spread_id: int) -> GradingSpreadSnapshot:
    row = session.get(GradingSpreadSnapshot, spread_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading spread not found")
    return row


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    spread_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSpreadEvidence], int]:
    q = select(GradingSpreadEvidence).join(
        GradingSpreadSnapshot,
        GradingSpreadEvidence.grading_spread_snapshot_id == GradingSpreadSnapshot.id,
    )
    q = q.where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
    if spread_id is not None:
        q = q.where(GradingSpreadEvidence.grading_spread_snapshot_id == spread_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSpreadEvidence.created_at).asc()).order_by(col(GradingSpreadEvidence.id).asc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    spread_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSpreadEvidence], int]:
    q = select(GradingSpreadEvidence).join(
        GradingSpreadSnapshot,
        GradingSpreadEvidence.grading_spread_snapshot_id == GradingSpreadSnapshot.id,
    )
    if owner_user_id is not None:
        q = q.where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
    if spread_id is not None:
        q = q.where(GradingSpreadEvidence.grading_spread_snapshot_id == spread_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSpreadEvidence.created_at).asc()).order_by(col(GradingSpreadEvidence.id).asc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSpreadHistory], int]:
    q = select(GradingSpreadHistory).where(GradingSpreadHistory.owner_user_id == owner_user_id)
    if canonical_comic_issue_id is not None:
        q = q.where(GradingSpreadHistory.canonical_comic_issue_id == canonical_comic_issue_id)
    if target_grader is not None:
        q = q.where(GradingSpreadHistory.target_grader == target_grader)
    if target_grade is not None:
        q = q.where(GradingSpreadHistory.target_grade == target_grade)
    if snapshot_date_from is not None:
        q = q.where(GradingSpreadHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(GradingSpreadHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSpreadHistory.snapshot_date).desc()).order_by(col(GradingSpreadHistory.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSpreadHistory], int]:
    q = select(GradingSpreadHistory)
    if owner_user_id is not None:
        q = q.where(GradingSpreadHistory.owner_user_id == owner_user_id)
    if canonical_comic_issue_id is not None:
        q = q.where(GradingSpreadHistory.canonical_comic_issue_id == canonical_comic_issue_id)
    if target_grader is not None:
        q = q.where(GradingSpreadHistory.target_grader == target_grader)
    if target_grade is not None:
        q = q.where(GradingSpreadHistory.target_grade == target_grade)
    if snapshot_date_from is not None:
        q = q.where(GradingSpreadHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(GradingSpreadHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSpreadHistory.snapshot_date).desc()).order_by(col(GradingSpreadHistory.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def get_history_owner(session: Session, *, history_id: int) -> GradingSpreadHistory:
    row = session.get(GradingSpreadHistory, history_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading spread history not found")
    return row


def get_history_ops(session: Session, *, history_id: int) -> GradingSpreadHistory:
    row = session.get(GradingSpreadHistory, history_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading spread history not found")
    return row


def list_response_from_rows(
    *,
    rows: list[GradingSpreadSnapshot],
    total: int,
    limit: int,
    offset: int,
) -> GradingSpreadListResponse:
    return GradingSpreadListResponse(items=[_snapshot_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def evidence_response_from_rows(
    *,
    rows: list[GradingSpreadEvidence],
    total: int,
    limit: int,
    offset: int,
) -> GradingSpreadEvidenceListResponse:
    return GradingSpreadEvidenceListResponse(items=[_evidence_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def history_response_from_rows(
    *,
    rows: list[GradingSpreadHistory],
    total: int,
    limit: int,
    offset: int,
) -> GradingSpreadHistoryListResponse:
    return GradingSpreadHistoryListResponse(items=[_history_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def inventory_grading_spread_badge(session: Session, *, owner_user_id: int, inventory_item_id: int) -> InventoryGradingSpreadBadge | None:
    row = session.exec(
        select(GradingSpreadSnapshot)
        .where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
        .where(GradingSpreadSnapshot.inventory_item_id == inventory_item_id)
        .order_by(col(GradingSpreadSnapshot.snapshot_date).desc())
        .order_by(col(GradingSpreadSnapshot.id).desc())
    ).first()
    if row is None:
        return None
    return InventoryGradingSpreadBadge(
        grading_spread_snapshot_id=int(row.id or 0),
        spread_status=row.spread_status,
        target_grader=row.target_grader,
        target_grade=row.target_grade,
        estimated_net_upside=row.estimated_net_upside,
        liquidity_adjusted_upside=row.liquidity_adjusted_upside,
        checksum=row.checksum,
    )
