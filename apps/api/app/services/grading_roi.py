"""P37-03 deterministic grading ROI intelligence."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.models import (
    GradingCandidate,
    GradingRoiEvidence,
    GradingRoiHistory,
    GradingRoiScenario,
    GradingRoiSnapshot,
    GradingSpreadSnapshot,
    InventoryCopy,
    InventoryFmvSnapshot,
    InventoryLiquiditySnapshot,
    Listing,
    MarketFmvSnapshot,
    MarketSaleRecord,
    SaleRecord,
    Variant,
)
from app.services.catalog_unification_issue_id import (
    effective_catalog_issue_id,
    resolve_legacy_comic_issue_id,
)
from app.schemas.grading_roi import (
    GradingRoiDashboardSummary,
    GradingRoiDetailRead,
    GradingRoiEvidenceListResponse,
    GradingRoiEvidenceRead,
    GradingRoiGeneratePayload,
    GradingRoiHistoryListResponse,
    GradingRoiHistoryRead,
    GradingRoiListResponse,
    GradingRoiRead,
    GradingRoiScenarioRead,
    InventoryGradingRoiBadge,
)

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
ZERO = Decimal("0.00")
ONE_HUNDRED = Decimal("100.00")
GRADED_FMV_MULTIPLIER_PESSIMISTIC = Decimal("0.90")
GRADED_FMV_MULTIPLIER_OPTIMISTIC = Decimal("1.10")
ROI_WEAK_THRESHOLD = Decimal("0.25")
ROI_MODERATE_THRESHOLD = Decimal("0.75")
ROI_STRONG_THRESHOLD = Decimal("0.75")
ROI_ELITE_THRESHOLD = Decimal("1.50")
LIQUIDITY_STRONG_THRESHOLD = Decimal("0.85")
LIQUIDITY_ELITE_THRESHOLD = Decimal("1.00")
GRADE_STEP_INCREMENT = Decimal("0.2")

LIQUIDITY_WEIGHTS: dict[str, Decimal] = {
    "HIGH": Decimal("1.00"),
    "MEDIUM": Decimal("0.85"),
    "LOW": Decimal("0.65"),
}

FEE_SCHEDULE: dict[str, dict[str, Decimal | int]] = {
    "PSA": {
        "grading_fee_amount": Decimal("25.00"),
        "shipping_cost_amount": Decimal("18.00"),
        "insurance_rate": Decimal("0.0125"),
        "insurance_floor": Decimal("5.00"),
        "estimated_turnaround_days": 75,
    },
    "CGC": {
        "grading_fee_amount": Decimal("30.00"),
        "shipping_cost_amount": Decimal("20.00"),
        "insurance_rate": Decimal("0.0150"),
        "insurance_floor": Decimal("5.00"),
        "estimated_turnaround_days": 90,
    },
    "CBCS": {
        "grading_fee_amount": Decimal("28.00"),
        "shipping_cost_amount": Decimal("19.00"),
        "insurance_rate": Decimal("0.0140"),
        "insurance_floor": Decimal("5.00"),
        "estimated_turnaround_days": 85,
    },
}

GRADE_VALUE_STEP_PCT: dict[str, Decimal] = {
    "PSA": Decimal("0.06"),
    "CGC": Decimal("0.05"),
    "CBCS": Decimal("0.05"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_grading_roi_pagination(limit: int, offset: int) -> tuple[int, int]:
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
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> tuple[InventoryCopy, int | None, int | None, GradingCandidate | None]:
    candidate: GradingCandidate | None = None
    if grading_candidate_id is not None:
        candidate = session.get(GradingCandidate, grading_candidate_id)
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading candidate not found")
        if owner_user_id is not None and candidate.owner_user_id != owner_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading candidate not found")
        if inventory_item_id is not None and candidate.inventory_item_id != inventory_item_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="grading candidate does not match inventory")
        inventory_item_id = candidate.inventory_item_id
        if canonical_comic_issue_id is None:
            canonical_comic_issue_id = candidate.canonical_comic_issue_id

    if inventory_item_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="grading_candidate_id or inventory_item_id is required",
        )

    stmt = select(InventoryCopy).where(InventoryCopy.id == inventory_item_id)
    if owner_user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == owner_user_id)
    if canonical_comic_issue_id is not None:
        linked_catalog = effective_catalog_issue_id(
            session,
            catalog_issue_id=None,
            canonical_comic_issue_id=canonical_comic_issue_id,
            inventory_copy_id=inventory_item_id,
        )
        scope_filters = []
        if linked_catalog is not None:
            scope_filters.append(InventoryCopy.catalog_issue_id == linked_catalog)
        scope_filters.append(
            InventoryCopy.variant_id.in_(
                select(Variant.id).where(Variant.comic_issue_id == canonical_comic_issue_id)
            )
        )
        stmt = stmt.where(or_(*scope_filters))
    inventory_row = session.exec(stmt.order_by(InventoryCopy.id.asc())).first()
    if inventory_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")
    catalog_issue_id = effective_catalog_issue_id(
        session,
        catalog_issue_id=inventory_row.catalog_issue_id,
        canonical_comic_issue_id=canonical_comic_issue_id or (candidate.canonical_comic_issue_id if candidate else None),
        inventory_copy_id=int(inventory_row.id or 0),
    )
    issue_id = resolve_legacy_comic_issue_id(
        session,
        inventory_row,
        fallback_canonical_comic_issue_id=canonical_comic_issue_id
        or (candidate.canonical_comic_issue_id if candidate else None),
    )
    return inventory_row, issue_id, catalog_issue_id, candidate


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


def _latest_candidate_estimates(
    session: Session,
    *,
    grading_candidate_id: int | None,
    target_grader: str,
    target_grade: str | None,
) -> tuple[Decimal | None, Decimal | None]:
    if grading_candidate_id is None:
        return None, None
    row = session.get(GradingCandidate, grading_candidate_id)
    if row is None or row.target_grader != target_grader:
        return None, None
    if target_grade is not None and row.target_grade is not None and row.target_grade != target_grade:
        return None, None
    return _money(row.estimated_raw_value), _money(row.estimated_graded_value)


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


def _latest_spread_snapshot(
    session: Session,
    *,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
) -> GradingSpreadSnapshot | None:
    stmt = select(GradingSpreadSnapshot).where(GradingSpreadSnapshot.target_grader == target_grader)
    if inventory_item_id is not None:
        stmt = stmt.where(GradingSpreadSnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        stmt = stmt.where(GradingSpreadSnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    if target_grade is not None:
        stmt = stmt.where(GradingSpreadSnapshot.target_grade == target_grade)
    return session.exec(
        stmt.order_by(col(GradingSpreadSnapshot.snapshot_date).desc()).order_by(col(GradingSpreadSnapshot.id).desc())
    ).first()


def _liquidity_modifier(status_value: str | None) -> tuple[str, Decimal]:
    normalized = (status_value or "LOW").upper()
    if normalized == "HIGH":
        return "HIGH", LIQUIDITY_WEIGHTS["HIGH"]
    if normalized == "MODERATE":
        return "MEDIUM", LIQUIDITY_WEIGHTS["MEDIUM"]
    return "LOW", LIQUIDITY_WEIGHTS["LOW"]


def _fee_schedule(target_grader: str, graded_fmv_amount: Decimal | None) -> tuple[Decimal | None, Decimal | None, Decimal | None, int | None]:
    schedule = FEE_SCHEDULE.get(target_grader.upper())
    if schedule is None:
        schedule = FEE_SCHEDULE["PSA"]
    grading_fee = _money(schedule["grading_fee_amount"])
    shipping_cost = _money(schedule["shipping_cost_amount"])
    turnaround_days = int(schedule["estimated_turnaround_days"])
    insurance_cost = None
    if graded_fmv_amount is not None:
        insurance_rate = _decimal(schedule["insurance_rate"]) or ZERO
        insurance_raw = max(
            _money(schedule["insurance_floor"]) or ZERO,
            _money(graded_fmv_amount * insurance_rate) or ZERO,
        )
        insurance_cost = _money(insurance_raw)
    return grading_fee, shipping_cost, insurance_cost, turnaround_days


def _confidence_level(*, evidence_count: int, has_raw: bool, has_graded: bool, has_liquidity: bool, has_fee: bool, has_realized: bool) -> str:
    if not has_raw or not has_graded or not has_liquidity or not has_fee:
        return "LOW"
    if evidence_count >= 5 and has_realized:
        return "HIGH"
    if evidence_count >= 3:
        return "MEDIUM"
    return "LOW"


def _roi_status(
    *,
    estimated_net_profit: Decimal | None,
    estimated_roi_pct: Decimal | None,
    liquidity_adjusted_roi: Decimal | None,
    liquidity_weight: Decimal,
    confidence_level: str,
    evidence_count: int,
    has_raw: bool,
    has_graded: bool,
    has_liquidity: bool,
) -> str:
    if not has_raw or not has_graded or not has_liquidity or evidence_count < 2:
        return "INSUFFICIENT_DATA"
    if estimated_net_profit is None or estimated_roi_pct is None or liquidity_adjusted_roi is None:
        return "INSUFFICIENT_DATA"
    if estimated_net_profit < ZERO:
        return "NEGATIVE"
    if estimated_roi_pct < ROI_WEAK_THRESHOLD or liquidity_adjusted_roi < Decimal("0.20"):
        return "WEAK"
    if estimated_roi_pct < ROI_MODERATE_THRESHOLD or liquidity_adjusted_roi < Decimal("0.55"):
        return "MODERATE"
    if (
        estimated_roi_pct >= ROI_ELITE_THRESHOLD
        and liquidity_weight >= LIQUIDITY_ELITE_THRESHOLD
        and confidence_level == "HIGH"
        and evidence_count >= 5
    ):
        return "ELITE"
    if (
        estimated_roi_pct >= ROI_STRONG_THRESHOLD
        and liquidity_weight >= LIQUIDITY_STRONG_THRESHOLD
        and confidence_level in {"HIGH", "MEDIUM"}
    ):
        return "STRONG"
    return "MODERATE"


def _normalized_grade_value(target_grade: str | None) -> Decimal | None:
    if target_grade is None:
        return None
    try:
        return Decimal(str(target_grade))
    except Exception:
        return None


def _format_grade(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _break_even_grade(
    *,
    target_grader: str,
    target_grade: str | None,
    raw_fmv_amount: Decimal | None,
    graded_fmv_amount: Decimal | None,
    total_cost_amount: Decimal | None,
) -> str | None:
    if raw_fmv_amount is None or graded_fmv_amount is None or total_cost_amount is None:
        return None
    grade = _normalized_grade_value(target_grade)
    if grade is None:
        return None
    net = _money(graded_fmv_amount - raw_fmv_amount - total_cost_amount)
    if net is not None and net >= ZERO:
        return _format_grade(grade)
    step_pct = GRADE_VALUE_STEP_PCT.get(target_grader.upper(), Decimal("0.05"))
    if graded_fmv_amount <= ZERO or step_pct <= ZERO:
        return None
    required_uplift = (raw_fmv_amount + total_cost_amount) - graded_fmv_amount
    if required_uplift <= ZERO:
        return _format_grade(grade)
    required_pct = required_uplift / graded_fmv_amount
    steps_needed = (required_pct / step_pct).to_integral_value(rounding=ROUND_CEILING)
    if steps_needed <= 0:
        return _format_grade(grade)
    break_even = grade + (GRADE_STEP_INCREMENT * Decimal(steps_needed))
    if break_even > Decimal("10.0"):
        return None
    return _format_grade(break_even)


def _scenario_grade(target_grade: str | None, scenario_name: str) -> str | None:
    grade = _normalized_grade_value(target_grade)
    if grade is None:
        return target_grade
    if scenario_name == "pessimistic":
        adjusted = grade - GRADE_STEP_INCREMENT
    elif scenario_name == "optimistic":
        adjusted = grade + GRADE_STEP_INCREMENT
    else:
        adjusted = grade
    if adjusted < Decimal("0.0"):
        adjusted = Decimal("0.0")
    if adjusted > Decimal("10.0"):
        adjusted = Decimal("10.0")
    return _format_grade(adjusted)


def _scenario_multiplier(scenario_name: str) -> Decimal:
    if scenario_name == "pessimistic":
        return GRADED_FMV_MULTIPLIER_PESSIMISTIC
    if scenario_name == "optimistic":
        return GRADED_FMV_MULTIPLIER_OPTIMISTIC
    return Decimal("1.00")


def _scenario_rows(
    *,
    snapshot_id: int,
    raw_fmv_amount: Decimal | None,
    target_grade: str | None,
    graded_fmv_amount: Decimal | None,
    total_cost_amount: Decimal | None,
    liquidity_weight: Decimal,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if graded_fmv_amount is None or total_cost_amount is None:
        return rows
    for scenario_name in ("pessimistic", "baseline", "optimistic"):
        multiplier = _scenario_multiplier(scenario_name)
        value = _money(graded_fmv_amount * multiplier)
        roi_pct = None
        liquidity_adjusted = None
        if value is not None and total_cost_amount > ZERO and raw_fmv_amount is not None:
            roi_pct = _pct((value - raw_fmv_amount - total_cost_amount) / total_cost_amount)
            liquidity_adjusted = _pct(roi_pct * liquidity_weight) if roi_pct is not None else None
        rows.append(
            {
                "grading_roi_snapshot_id": snapshot_id,
                "scenario_name": scenario_name,
                "target_grade": _scenario_grade(target_grade, scenario_name),
                "estimated_value": value,
                "estimated_roi_pct": roi_pct,
                "liquidity_adjusted_roi": liquidity_adjusted,
            }
        )
    return rows


def _evidence_payload_rows(
    *,
    raw_fmv_amount: Decimal | None,
    graded_fmv_amount: Decimal | None,
    fee_schedule_row: dict[str, Any] | None,
    liquidity_snapshot: InventoryLiquiditySnapshot | None,
    sales_ledger_sale: SaleRecord | None,
    market_sale_record: MarketSaleRecord | None,
    spread_snapshot: GradingSpreadSnapshot | None,
    candidate: GradingCandidate | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if raw_fmv_amount is not None:
        rows.append(
            {
                "evidence_type": "FMV",
                "source_id": None,
                "source_table": "inventory_fmv_snapshot",
                "evidence_value_json": {"raw_fmv_amount": raw_fmv_amount},
            }
        )
    if graded_fmv_amount is not None:
        rows.append(
            {
                "evidence_type": "FMV",
                "source_id": None,
                "source_table": "market_fmv_snapshot",
                "evidence_value_json": {"graded_fmv_amount": graded_fmv_amount},
            }
        )
    if fee_schedule_row is not None:
        rows.append(
            {
                "evidence_type": "FEE_SCHEDULE",
                "source_id": None,
                "source_table": "deterministic_fee_schedule",
                "evidence_value_json": fee_schedule_row,
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
    if spread_snapshot is not None:
        rows.append(
            {
                "evidence_type": "SPREAD_ENGINE",
                "source_id": int(spread_snapshot.id or 0),
                "source_table": "grading_spread_snapshot",
                "evidence_value_json": {
                    "spread_status": spread_snapshot.spread_status,
                    "estimated_spread_amount": spread_snapshot.estimated_spread_amount,
                    "estimated_net_upside": spread_snapshot.estimated_net_upside,
                    "liquidity_adjusted_upside": spread_snapshot.liquidity_adjusted_upside,
                },
            }
        )
    if candidate is not None and (
        candidate.estimated_raw_value is not None
        or candidate.estimated_graded_value is not None
        or candidate.estimated_grading_cost is not None
        or candidate.estimated_roi is not None
        or candidate.rationale is not None
    ):
        rows.append(
            {
                "evidence_type": "MANUAL_OVERRIDE",
                "source_id": int(candidate.id or 0),
                "source_table": "grading_candidate",
                "evidence_value_json": {
                    "estimated_raw_value": candidate.estimated_raw_value,
                    "estimated_graded_value": candidate.estimated_graded_value,
                    "estimated_grading_cost": candidate.estimated_grading_cost,
                    "estimated_roi": candidate.estimated_roi,
                    "rationale": candidate.rationale,
                },
            }
        )
    return rows


def _snapshot_signature_payload(
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
    raw_fmv_amount: Decimal | None,
    graded_fmv_amount: Decimal | None,
    grading_fee_amount: Decimal | None,
    shipping_cost_amount: Decimal | None,
    insurance_cost_amount: Decimal | None,
    estimated_turnaround_days: int | None,
    estimated_total_cost: Decimal | None,
    estimated_spread_amount: Decimal | None,
    estimated_net_profit: Decimal | None,
    estimated_roi_pct: Decimal | None,
    liquidity_adjusted_roi: Decimal | None,
    break_even_grade: str | None,
    roi_status: str,
    confidence_level: str,
    snapshot_date: date,
) -> dict[str, Any]:
    return {
        "owner_user_id": owner_user_id,
        "grading_candidate_id": grading_candidate_id,
        "inventory_item_id": inventory_item_id,
        "canonical_comic_issue_id": canonical_comic_issue_id,
        "target_grader": target_grader,
        "target_grade": target_grade,
        "raw_fmv_amount": raw_fmv_amount,
        "graded_fmv_amount": graded_fmv_amount,
        "grading_fee_amount": grading_fee_amount,
        "shipping_cost_amount": shipping_cost_amount,
        "insurance_cost_amount": insurance_cost_amount,
        "estimated_turnaround_days": estimated_turnaround_days,
        "estimated_total_cost": estimated_total_cost,
        "estimated_spread_amount": estimated_spread_amount,
        "estimated_net_profit": estimated_net_profit,
        "estimated_roi_pct": estimated_roi_pct,
        "liquidity_adjusted_roi": liquidity_adjusted_roi,
        "break_even_grade": break_even_grade,
        "roi_status": roi_status,
        "confidence_level": confidence_level,
        "snapshot_date": snapshot_date,
    }


def _history_checksum(
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    target_grader: str,
    target_grade: str | None,
    roi_pct: Decimal | None,
    liquidity_adjusted_roi: Decimal | None,
    snapshot_date: date,
) -> str:
    payload = {
        "owner_user_id": owner_user_id,
        "grading_candidate_id": grading_candidate_id,
        "inventory_item_id": inventory_item_id,
        "canonical_comic_issue_id": canonical_comic_issue_id,
        "target_grader": target_grader,
        "target_grade": target_grade,
        "roi_pct": roi_pct,
        "liquidity_adjusted_roi": liquidity_adjusted_roi,
        "snapshot_date": snapshot_date,
    }
    return deterministic_checksum(payload)


def _snapshot_read(row: GradingRoiSnapshot) -> GradingRoiRead:
    return GradingRoiRead.model_validate(row, from_attributes=True)


def _evidence_read(row: GradingRoiEvidence) -> GradingRoiEvidenceRead:
    return GradingRoiEvidenceRead.model_validate(row, from_attributes=True)


def _scenario_read(row: GradingRoiScenario) -> GradingRoiScenarioRead:
    return GradingRoiScenarioRead.model_validate(row, from_attributes=True)


def _history_read(row: GradingRoiHistory) -> GradingRoiHistoryRead:
    return GradingRoiHistoryRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, snapshot: GradingRoiSnapshot) -> GradingRoiDetailRead:
    sid = int(snapshot.id or 0)
    evidence_rows = session.exec(
        select(GradingRoiEvidence)
        .where(GradingRoiEvidence.grading_roi_snapshot_id == sid)
        .order_by(col(GradingRoiEvidence.created_at).asc(), col(GradingRoiEvidence.id).asc())
    ).all()
    scenario_rows = session.exec(
        select(GradingRoiScenario)
        .where(GradingRoiScenario.grading_roi_snapshot_id == sid)
        .order_by(col(GradingRoiScenario.id).asc())
    ).all()
    history_rows = session.exec(
        select(GradingRoiHistory)
        .where(GradingRoiHistory.canonical_comic_issue_id == snapshot.canonical_comic_issue_id)
        .where(GradingRoiHistory.target_grader == snapshot.target_grader)
        .where(GradingRoiHistory.target_grade == snapshot.target_grade)
        .order_by(col(GradingRoiHistory.snapshot_date).desc(), col(GradingRoiHistory.id).desc())
    ).all()
    return GradingRoiDetailRead(
        snapshot=_snapshot_read(snapshot),
        evidence=[_evidence_read(row) for row in evidence_rows],
        scenarios=[_scenario_read(row) for row in scenario_rows],
        history=[_history_read(row) for row in history_rows],
    )


def _candidate_snapshot_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    roi_status: str | None = None,
    confidence_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
) -> Any:
    q = select(GradingRoiSnapshot)
    if owner_user_id is not None:
        q = q.where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        q = q.where(GradingRoiSnapshot.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        q = q.where(GradingRoiSnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        linked_catalog = effective_catalog_issue_id(
            session,
            catalog_issue_id=None,
            canonical_comic_issue_id=canonical_comic_issue_id,
            inventory_copy_id=None,
        )
        scope = [GradingRoiSnapshot.canonical_comic_issue_id == canonical_comic_issue_id]
        if linked_catalog is not None:
            scope.append(GradingRoiSnapshot.catalog_issue_id == linked_catalog)
        q = q.where(or_(*scope))
    if target_grader is not None:
        q = q.where(GradingRoiSnapshot.target_grader == target_grader)
    if target_grade is not None:
        q = q.where(GradingRoiSnapshot.target_grade == target_grade)
    if roi_status is not None:
        q = q.where(GradingRoiSnapshot.roi_status == roi_status)
    if confidence_level is not None:
        q = q.where(GradingRoiSnapshot.confidence_level == confidence_level)
    if snapshot_date_from is not None:
        q = q.where(GradingRoiSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(GradingRoiSnapshot.snapshot_date <= snapshot_date_to)
    return q


def _build_row(
    session: Session,
    *,
    owner_user_id: int | None,
    inventory_row: InventoryCopy,
    canonical_comic_issue_id: int | None,
    catalog_issue_id: int | None,
    grading_candidate: GradingCandidate | None,
    target_grader: str,
    target_grade: str | None,
    snapshot_date: date,
    replay_key: str | None,
    generation_params_json: dict[str, Any],
) -> tuple[GradingRoiSnapshot, bool]:
    inventory_id = int(inventory_row.id or 0)
    raw_candidate, graded_candidate = _latest_candidate_estimates(
        session,
        grading_candidate_id=int(grading_candidate.id or 0) if grading_candidate is not None else None,
        target_grader=target_grader,
        target_grade=target_grade,
    )
    raw_fmv = raw_candidate if raw_candidate is not None else _latest_inventory_fmv(session, inventory_id)
    graded_fmv, _graded_snapshot = _latest_graded_fmv(
        session,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
    )
    if graded_candidate is not None:
        graded_fmv = graded_candidate
    liquidity_snapshot = _latest_liquidity_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=inventory_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
    )
    sales_ledger_sale = _latest_sales_ledger_sale(session, inventory_id)
    market_sale_record = _latest_market_sale_record(session, inventory_id)
    spread_snapshot = _latest_spread_snapshot(
        session,
        inventory_item_id=inventory_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
    )

    has_raw = raw_fmv is not None
    has_graded = graded_fmv is not None
    has_liquidity = liquidity_snapshot is not None

    fee_grading, fee_shipping, fee_insurance, turnaround_days = _fee_schedule(target_grader, graded_fmv)
    estimated_total_cost = None
    if fee_grading is not None and fee_shipping is not None and fee_insurance is not None:
        estimated_total_cost = _money(fee_grading + fee_shipping + fee_insurance)
    estimated_spread = _money(graded_fmv - raw_fmv) if has_raw and has_graded else None
    estimated_net_profit = _money(graded_fmv - raw_fmv - estimated_total_cost) if has_raw and has_graded and estimated_total_cost is not None else None
    estimated_roi_pct = _pct(estimated_net_profit / estimated_total_cost) if estimated_net_profit is not None and estimated_total_cost not in (None, ZERO) else None
    liq_label, liq_weight = _liquidity_modifier(liquidity_snapshot.liquidity_status if liquidity_snapshot else None)
    liquidity_adjusted_roi = _pct(estimated_roi_pct * liq_weight) if estimated_roi_pct is not None else None
    break_even_grade = _break_even_grade(
        target_grader=target_grader,
        target_grade=target_grade,
        raw_fmv_amount=raw_fmv,
        graded_fmv_amount=graded_fmv,
        total_cost_amount=estimated_total_cost,
    )

    evidence_payload_rows = _evidence_payload_rows(
        raw_fmv_amount=raw_fmv,
        graded_fmv_amount=graded_fmv,
        fee_schedule_row={
            "target_grader": target_grader,
            "grading_fee_amount": fee_grading,
            "shipping_cost_amount": fee_shipping,
            "insurance_cost_amount": fee_insurance,
            "estimated_turnaround_days": turnaround_days,
        }
        if fee_grading is not None and fee_shipping is not None
        else None,
        liquidity_snapshot=liquidity_snapshot,
        sales_ledger_sale=sales_ledger_sale,
        market_sale_record=market_sale_record,
        spread_snapshot=spread_snapshot,
        candidate=grading_candidate,
    )
    evidence_count = len(evidence_payload_rows)
    realized_sale_present = sales_ledger_sale is not None or market_sale_record is not None
    confidence_level = _confidence_level(
        evidence_count=evidence_count,
        has_raw=has_raw,
        has_graded=has_graded,
        has_liquidity=has_liquidity,
        has_fee=estimated_total_cost is not None,
        has_realized=realized_sale_present,
    )
    roi_status = _roi_status(
        estimated_net_profit=estimated_net_profit,
        estimated_roi_pct=estimated_roi_pct,
        liquidity_adjusted_roi=liquidity_adjusted_roi,
        liquidity_weight=liq_weight,
        confidence_level=confidence_level,
        evidence_count=evidence_count,
        has_raw=has_raw,
        has_graded=has_graded,
        has_liquidity=has_liquidity,
    )
    checksum = deterministic_checksum(
        _snapshot_signature_payload(
            owner_user_id=owner_user_id,
            grading_candidate_id=int(grading_candidate.id or 0) if grading_candidate is not None else None,
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=canonical_comic_issue_id,
            target_grader=target_grader,
            target_grade=target_grade,
            raw_fmv_amount=raw_fmv,
            graded_fmv_amount=graded_fmv,
            grading_fee_amount=fee_grading,
            shipping_cost_amount=fee_shipping,
            insurance_cost_amount=fee_insurance,
            estimated_turnaround_days=turnaround_days,
            estimated_total_cost=estimated_total_cost,
            estimated_spread_amount=estimated_spread,
            estimated_net_profit=estimated_net_profit,
            estimated_roi_pct=estimated_roi_pct,
            liquidity_adjusted_roi=liquidity_adjusted_roi,
            break_even_grade=break_even_grade,
            roi_status=roi_status,
            confidence_level=confidence_level,
            snapshot_date=snapshot_date,
        )
    )

    if replay_key is not None:
        existing = session.exec(
            select(GradingRoiSnapshot).where(
                GradingRoiSnapshot.owner_user_id == owner_user_id,
                GradingRoiSnapshot.replay_key == replay_key,
            )
        ).first()
        if existing is not None:
            return existing, True

    existing = session.exec(
        select(GradingRoiSnapshot).where(
            GradingRoiSnapshot.checksum == checksum,
            GradingRoiSnapshot.grading_candidate_id == (int(grading_candidate.id or 0) if grading_candidate is not None else None),
            GradingRoiSnapshot.inventory_item_id == inventory_id,
            GradingRoiSnapshot.target_grader == target_grader,
            GradingRoiSnapshot.target_grade == target_grade,
            GradingRoiSnapshot.snapshot_date == snapshot_date,
        )
    ).first()
    if existing is not None:
        return existing, True

    snapshot = GradingRoiSnapshot(
        owner_user_id=owner_user_id,
        grading_candidate_id=int(grading_candidate.id or 0) if grading_candidate is not None else None,
        inventory_item_id=inventory_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        catalog_issue_id=catalog_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        raw_fmv_amount=raw_fmv,
        graded_fmv_amount=graded_fmv,
        grading_fee_amount=fee_grading,
        shipping_cost_amount=fee_shipping,
        insurance_cost_amount=fee_insurance,
        estimated_turnaround_days=turnaround_days,
        estimated_total_cost=estimated_total_cost,
        estimated_spread_amount=estimated_spread,
        estimated_net_profit=estimated_net_profit,
        estimated_roi_pct=estimated_roi_pct,
        liquidity_adjusted_roi=liquidity_adjusted_roi,
        break_even_grade=break_even_grade,
        roi_status=roi_status,
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
            GradingRoiEvidence(
                grading_roi_snapshot_id=int(snapshot.id or 0),
                evidence_type=payload["evidence_type"],
                source_id=payload["source_id"],
                source_table=payload["source_table"],
                evidence_value_json=_json_safe(payload["evidence_value_json"]),
                created_at=utc_now(),
            )
        )
    scenario_rows = _scenario_rows(
        snapshot_id=int(snapshot.id or 0),
        raw_fmv_amount=raw_fmv,
        target_grade=target_grade,
        graded_fmv_amount=graded_fmv,
        total_cost_amount=estimated_total_cost,
        liquidity_weight=liq_weight,
    )
    for payload in scenario_rows:
        session.add(
            GradingRoiScenario(
                grading_roi_snapshot_id=payload["grading_roi_snapshot_id"],
                scenario_name=payload["scenario_name"],
                target_grade=payload["target_grade"],
                estimated_value=payload["estimated_value"],
                estimated_roi_pct=payload["estimated_roi_pct"],
                liquidity_adjusted_roi=payload["liquidity_adjusted_roi"],
                created_at=utc_now(),
            )
        )
    history_checksum = _history_checksum(
        owner_user_id=owner_user_id,
        grading_candidate_id=int(grading_candidate.id or 0) if grading_candidate is not None else None,
        inventory_item_id=inventory_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        roi_pct=estimated_roi_pct,
        liquidity_adjusted_roi=liquidity_adjusted_roi,
        snapshot_date=snapshot_date,
    )
    session.add(
        GradingRoiHistory(
            owner_user_id=owner_user_id,
            grading_candidate_id=int(grading_candidate.id or 0) if grading_candidate is not None else None,
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=canonical_comic_issue_id,
            target_grader=target_grader,
            target_grade=target_grade,
            roi_pct=estimated_roi_pct,
            liquidity_adjusted_roi=liquidity_adjusted_roi,
            snapshot_date=snapshot_date,
            checksum=history_checksum,
            created_at=utc_now(),
        )
    )
    session.commit()
    session.refresh(snapshot)
    return snapshot, False


def generate_grading_roi(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingRoiGeneratePayload,
) -> tuple[GradingRoiDetailRead, bool]:
    target_grader = payload.target_grader.upper()
    target_grade = payload.target_grade.strip() if payload.target_grade else None
    snapshot_date = payload.snapshot_date or utc_now().date()
    replay_key = payload.replay_key.strip() if payload.replay_key else None

    if payload.grading_candidate_id is None and payload.inventory_item_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="grading_candidate_id or inventory_item_id is required",
        )

    inventory_row, canonical_comic_issue_id, catalog_issue_id, candidate = _inventory_row(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=payload.grading_candidate_id,
        inventory_item_id=payload.inventory_item_id,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
    )
    if payload.canonical_comic_issue_id is not None and canonical_comic_issue_id != payload.canonical_comic_issue_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="inventory item does not match issue")
    if payload.grading_candidate_id is not None and candidate is not None and candidate.owner_user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading candidate not found")

    snapshot, replayed = _build_row(
        session,
        owner_user_id=owner_user_id,
        inventory_row=inventory_row,
        canonical_comic_issue_id=canonical_comic_issue_id,
        catalog_issue_id=catalog_issue_id,
        grading_candidate=candidate,
        target_grader=target_grader,
        target_grade=target_grade,
        snapshot_date=snapshot_date,
        replay_key=replay_key,
        generation_params_json=payload.model_dump(mode="json"),
    )
    return _detail_read(session, snapshot), replayed


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> GradingRoiDashboardSummary:
    rows = session.exec(
        select(GradingRoiSnapshot).where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    ).all()
    strong = sum(1 for row in rows if row.roi_status == "STRONG")
    elite = sum(1 for row in rows if row.roi_status == "ELITE")
    negative = sum(1 for row in rows if row.roi_status == "NEGATIVE")
    roi_values = [row.estimated_roi_pct for row in rows if row.estimated_roi_pct is not None]
    liquidity_values = [row.liquidity_adjusted_roi for row in rows if row.liquidity_adjusted_roi is not None]
    avg_roi = _pct(sum(roi_values, ZERO) / Decimal(len(roi_values))) if roi_values else None
    liquidity_total = _pct(sum(liquidity_values, ZERO)) if liquidity_values else None
    return GradingRoiDashboardSummary(
        strong_roi_count=strong,
        elite_roi_count=elite,
        negative_roi_count=negative,
        average_estimated_roi=avg_roi,
        liquidity_adjusted_roi_total=liquidity_total,
    )


def dashboard_summary_ops(session: Session, *, owner_user_id: int | None = None) -> GradingRoiDashboardSummary:
    rows = session.exec(select(GradingRoiSnapshot)).all()
    if owner_user_id is not None:
        rows = [row for row in rows if row.owner_user_id == owner_user_id]
    strong = sum(1 for row in rows if row.roi_status == "STRONG")
    elite = sum(1 for row in rows if row.roi_status == "ELITE")
    negative = sum(1 for row in rows if row.roi_status == "NEGATIVE")
    roi_values = [row.estimated_roi_pct for row in rows if row.estimated_roi_pct is not None]
    liquidity_values = [row.liquidity_adjusted_roi for row in rows if row.liquidity_adjusted_roi is not None]
    avg_roi = _pct(sum(roi_values, ZERO) / Decimal(len(roi_values))) if roi_values else None
    liquidity_total = _pct(sum(liquidity_values, ZERO)) if liquidity_values else None
    return GradingRoiDashboardSummary(
        strong_roi_count=strong,
        elite_roi_count=elite,
        negative_roi_count=negative,
        average_estimated_roi=avg_roi,
        liquidity_adjusted_roi_total=liquidity_total,
    )


def list_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    roi_status: str | None = None,
    confidence_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRoiSnapshot], int]:
    q = _candidate_snapshot_query(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        roi_status=roi_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingRoiSnapshot.snapshot_date).desc()).order_by(col(GradingRoiSnapshot.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    roi_status: str | None = None,
    confidence_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRoiSnapshot], int]:
    q = _candidate_snapshot_query(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        roi_status=roi_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingRoiSnapshot.snapshot_date).desc()).order_by(col(GradingRoiSnapshot.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def get_snapshot_owner(session: Session, *, owner_user_id: int, roi_id: int) -> GradingRoiSnapshot:
    row = session.get(GradingRoiSnapshot, roi_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading roi not found")
    return row


def get_snapshot_ops(session: Session, *, roi_id: int) -> GradingRoiSnapshot:
    row = session.get(GradingRoiSnapshot, roi_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading roi not found")
    return row


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    roi_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRoiEvidence], int]:
    q = select(GradingRoiEvidence).join(
        GradingRoiSnapshot,
        GradingRoiEvidence.grading_roi_snapshot_id == GradingRoiSnapshot.id,
    )
    q = q.where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    if roi_id is not None:
        q = q.where(GradingRoiEvidence.grading_roi_snapshot_id == roi_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingRoiEvidence.created_at).asc()).order_by(col(GradingRoiEvidence.id).asc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    roi_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRoiEvidence], int]:
    q = select(GradingRoiEvidence).join(
        GradingRoiSnapshot,
        GradingRoiEvidence.grading_roi_snapshot_id == GradingRoiSnapshot.id,
    )
    if owner_user_id is not None:
        q = q.where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    if roi_id is not None:
        q = q.where(GradingRoiEvidence.grading_roi_snapshot_id == roi_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingRoiEvidence.created_at).asc()).order_by(col(GradingRoiEvidence.id).asc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRoiHistory], int]:
    q = select(GradingRoiHistory).where(GradingRoiHistory.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        q = q.where(GradingRoiHistory.grading_candidate_id == grading_candidate_id)
    if canonical_comic_issue_id is not None:
        q = q.where(GradingRoiHistory.canonical_comic_issue_id == canonical_comic_issue_id)
    if target_grader is not None:
        q = q.where(GradingRoiHistory.target_grader == target_grader)
    if target_grade is not None:
        q = q.where(GradingRoiHistory.target_grade == target_grade)
    if snapshot_date_from is not None:
        q = q.where(GradingRoiHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(GradingRoiHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingRoiHistory.snapshot_date).desc()).order_by(col(GradingRoiHistory.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    target_grader: str | None = None,
    target_grade: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRoiHistory], int]:
    q = select(GradingRoiHistory)
    if owner_user_id is not None:
        q = q.where(GradingRoiHistory.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        q = q.where(GradingRoiHistory.grading_candidate_id == grading_candidate_id)
    if canonical_comic_issue_id is not None:
        q = q.where(GradingRoiHistory.canonical_comic_issue_id == canonical_comic_issue_id)
    if target_grader is not None:
        q = q.where(GradingRoiHistory.target_grader == target_grader)
    if target_grade is not None:
        q = q.where(GradingRoiHistory.target_grade == target_grade)
    if snapshot_date_from is not None:
        q = q.where(GradingRoiHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(GradingRoiHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingRoiHistory.snapshot_date).desc()).order_by(col(GradingRoiHistory.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def get_history_owner(session: Session, *, owner_user_id: int, history_id: int) -> GradingRoiHistory:
    row = session.get(GradingRoiHistory, history_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading roi history not found")
    return row


def get_history_ops(session: Session, *, history_id: int) -> GradingRoiHistory:
    row = session.get(GradingRoiHistory, history_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading roi history not found")
    return row


def list_response_from_rows(
    *,
    rows: list[GradingRoiSnapshot],
    total: int,
    limit: int,
    offset: int,
) -> GradingRoiListResponse:
    return GradingRoiListResponse(items=[_snapshot_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def evidence_response_from_rows(
    *,
    rows: list[GradingRoiEvidence],
    total: int,
    limit: int,
    offset: int,
) -> GradingRoiEvidenceListResponse:
    return GradingRoiEvidenceListResponse(items=[_evidence_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def history_response_from_rows(
    *,
    rows: list[GradingRoiHistory],
    total: int,
    limit: int,
    offset: int,
) -> GradingRoiHistoryListResponse:
    return GradingRoiHistoryListResponse(items=[_history_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def inventory_grading_roi_badge(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryGradingRoiBadge | None:
    row = session.exec(
        select(GradingRoiSnapshot)
        .where(GradingRoiSnapshot.owner_user_id == owner_user_id)
        .where(GradingRoiSnapshot.inventory_item_id == inventory_item_id)
        .order_by(col(GradingRoiSnapshot.snapshot_date).desc())
        .order_by(col(GradingRoiSnapshot.id).desc())
    ).first()
    if row is None:
        return None
    return InventoryGradingRoiBadge(
        grading_roi_snapshot_id=int(row.id or 0),
        roi_status=row.roi_status,
        target_grader=row.target_grader,
        target_grade=row.target_grade,
        estimated_total_cost=row.estimated_total_cost,
        estimated_net_profit=row.estimated_net_profit,
        liquidity_adjusted_roi=row.liquidity_adjusted_roi,
        break_even_grade=row.break_even_grade,
        checksum=row.checksum,
    )
