"""P38-03 deterministic portfolio liquidity allocation intelligence (read-only inputs)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, literal
from sqlmodel import Session, col, select

from app.models import (
    ConventionEvent,
    ConventionInventoryAssignment,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    Portfolio,
    PortfolioAllocationSnapshot,
    PortfolioItem,
    PortfolioLiquidityBucket,
    PortfolioLiquidityEvidence,
    PortfolioLiquidityHistory,
    PortfolioLiquiditySnapshot,
    SaleRecord,
    SaleRecordLineItem,
)
from app.schemas.portfolio_liquidity import (
    InventoryPortfolioLiquidityTeaser,
    PortfolioLiquidityBucketRead,
    PortfolioLiquidityEvidenceListResponse,
    PortfolioLiquidityEvidenceRead,
    PortfolioLiquidityGeneratePayload,
    PortfolioLiquidityGenerateResponse,
    PortfolioLiquidityHistoryListResponse,
    PortfolioLiquidityHistoryRead,
    PortfolioLiquiditySnapshotListResponse,
    PortfolioLiquiditySnapshotRead,
)

SCOPE_ALL_INVENTORY = "ALL_INVENTORY"

BUCKET_ORDER = ("HIGH", "MEDIUM", "LOW", "ILLIQUID")

ENGINE_TO_BUCKET_WEIGHT: dict[str, tuple[str, Decimal]] = {
    "HIGH": ("HIGH", Decimal("1.00")),
    "MODERATE": ("MEDIUM", Decimal("0.70")),
    "LOW": ("LOW", Decimal("0.40")),
    "ILLIQUID": ("ILLIQUID", Decimal("0.10")),
}

ENGINE_MISSING_BUCKET = ("MEDIUM", Decimal("0.55"))

BUCKET_WEIGHTS: dict[str, Decimal] = {
    "HIGH": Decimal("1.00"),
    "MEDIUM": Decimal("0.70"),
    "LOW": Decimal("0.40"),
    "ILLIQUID": Decimal("0.10"),
}


def _engine_label_map_evidence_json() -> dict[str, dict[str, str]]:
    core = {status: {"bucket": bkt, "liquidity_weight": str(w)} for status, (bkt, w) in ENGINE_TO_BUCKET_WEIGHT.items()}
    mb, mw = ENGINE_MISSING_BUCKET
    core["_MISSING_OR_UNKNOWN_ENGINE_SNAPSHOT"] = {"bucket": mb, "liquidity_weight": str(mw)}
    return core


COV_INSUFFICIENT = Decimal("0.25")
RULE_CRITICAL_ILLIQ = Decimal("0.42")
RULE_CRITICAL_DEAD_SHARE = Decimal("0.38")
RULE_IMBALANCED_COMBO = Decimal("0.52")
RULE_WATCH_COMBO = Decimal("0.28")

MONEY_QUANT = Decimal("0.01")
SCORE_QUANT = Decimal("0.01")
ZERO = Decimal("0")
DEC_100 = Decimal("100")


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def scope_key(portfolio_id: int | None) -> str:
    return SCOPE_ALL_INVENTORY if portfolio_id is None else f"PORTFOLIO_{int(portfolio_id)}"


def _norm_rk(value: str | None) -> str:
    return (value or "").strip()


def _money(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _score_q(value: Decimal) -> Decimal:
    return min(DEC_100, max(ZERO, value)).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _portfolio_bucket_for_engine(engine_status: str | None) -> tuple[str, Decimal]:
    if engine_status and engine_status in ENGINE_TO_BUCKET_WEIGHT:
        return ENGINE_TO_BUCKET_WEIGHT[engine_status]
    return ENGINE_MISSING_BUCKET


@dataclass(frozen=True)
class _ItemLiquidityRow:
    inventory_item_id: int
    current_fmv: Decimal | None
    liquidity_snapshot_id: int | None
    engine_status: str | None
    sell_through_pct: Decimal
    stale_listing_rate_pct: Decimal


def _hydrate_facts(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, _ItemLiquidityRow]:
    if not inv_ids:
        return {}
    fmv_map = {
        int(pid): fm
        for pid, fm in session.exec(
            select(InventoryCopy.id, InventoryCopy.current_fmv).where(
                InventoryCopy.user_id == owner_user_id,
                col(InventoryCopy.id).in_(inv_ids),
            )
        ).all()
    }

    liquidity_rows = session.exec(
        select(InventoryLiquiditySnapshot)
        .where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            col(InventoryLiquiditySnapshot.inventory_item_id).is_not(None),
            col(InventoryLiquiditySnapshot.inventory_item_id).in_(inv_ids),
        )
        .order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc(), col(InventoryLiquiditySnapshot.id).desc())
    ).all()

    latest_by_item: dict[int, InventoryLiquiditySnapshot] = {}
    for lr in liquidity_rows:
        iid = int(lr.inventory_item_id or 0)
        if iid and iid not in latest_by_item:
            latest_by_item[iid] = lr

    facts: dict[int, _ItemLiquidityRow] = {}
    for iid in sorted(inv_ids):
        lr = latest_by_item.get(iid)
        fm = fmv_map.get(iid)
        if lr:
            facts[iid] = _ItemLiquidityRow(
                inventory_item_id=iid,
                current_fmv=fm,
                liquidity_snapshot_id=int(lr.id or 0) or None,
                engine_status=str(lr.liquidity_status),
                sell_through_pct=_money(lr.sell_through_rate_pct),
                stale_listing_rate_pct=_money(lr.stale_listing_rate_pct),
            )
        else:
            facts[iid] = _ItemLiquidityRow(
                inventory_item_id=iid,
                current_fmv=fm,
                liquidity_snapshot_id=None,
                engine_status=None,
                sell_through_pct=ZERO,
                stale_listing_rate_pct=ZERO,
            )
    return facts


def _load_scope_inventory_ids(session: Session, *, owner_user_id: int, portfolio_id: int | None) -> list[int]:
    stmt = select(InventoryCopy.id).where(InventoryCopy.user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.join(
            PortfolioItem,
            and_(
                PortfolioItem.inventory_item_id == InventoryCopy.id,
                PortfolioItem.portfolio_id == portfolio_id,
                PortfolioItem.removed_at.is_(None),
            ),
        )
    stmt = stmt.order_by(col(InventoryCopy.id).asc())
    rows = session.exec(stmt).all()
    return [int(r) for r in rows if r is not None]


def _latest_allocation_checksum(session: Session, *, owner_user_id: int, generation_scope_key: str) -> str | None:
    row = session.exec(
        select(PortfolioAllocationSnapshot)
        .where(
            PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
            PortfolioAllocationSnapshot.generation_scope_key == generation_scope_key,
        )
        .order_by(col(PortfolioAllocationSnapshot.snapshot_date).desc(), col(PortfolioAllocationSnapshot.id).desc())
    ).first()
    return str(row.checksum) if row and row.checksum else None


def _activity_signals(
    session: Session, *, owner_user_id: int, inv_ids: list[int]
) -> tuple[Decimal, set[int], int, int]:
    gross = ZERO
    sale_items: set[int] = set()
    listings_ct = 0
    conv_ct = 0
    if not inv_ids:
        return gross, sale_items, listings_ct, conv_ct
    lines = session.exec(
        select(SaleRecordLineItem.inventory_item_id, SaleRecordLineItem.line_subtotal_amount)
        .join(SaleRecord, SaleRecordLineItem.sale_record_id == SaleRecord.id)
        .where(
            SaleRecord.owner_user_id == owner_user_id,
            SaleRecord.status == "RECORDED",
            col(SaleRecordLineItem.inventory_item_id).in_(inv_ids),
        )
    ).all()
    for iid, amt in lines:
        ii = int(iid or 0)
        if ii:
            sale_items.add(ii)
        gross += _money(amt)

    lst = session.exec(
        select(Listing.id).where(
            Listing.owner_user_id == owner_user_id,
            col(Listing.inventory_copy_id).in_(inv_ids),
            Listing.archived_at.is_(None),
        )
    ).all()
    listings_ct = len(lst)

    ca = session.exec(
        select(ConventionInventoryAssignment.id)
        .join(ConventionEvent, ConventionInventoryAssignment.convention_event_id == ConventionEvent.id)
        .where(
            ConventionEvent.owner_user_id == owner_user_id,
            ConventionEvent.status == "ACTIVE",
            ConventionInventoryAssignment.removed_at.is_(None),
            col(ConventionInventoryAssignment.inventory_item_id).in_(inv_ids),
        )
    ).all()
    conv_ct = len(ca)
    return gross, sale_items, listings_ct, conv_ct


def _classify_balance(
    *,
    n_items: int,
    liquidity_coverage_pct: Decimal,
    total_denominator_money: Decimal,
    illiquid_fmv: Decimal,
    low_fmv: Decimal,
    illiquid_cnt: int,
    low_cnt: int,
    dead_capital_estimate: Decimal,
) -> str:
    if n_items <= 0:
        return "INSUFFICIENT_DATA"
    if liquidity_coverage_pct < COV_INSUFFICIENT * DEC_100:
        return "INSUFFICIENT_DATA"
    dead_share = dead_capital_estimate / total_denominator_money if total_denominator_money > ZERO else ZERO
    if total_denominator_money > ZERO:
        illiq_share = illiquid_fmv / total_denominator_money
        low_share = low_fmv / total_denominator_money
        combo = illiq_share + low_share
    else:
        illiq_share = Decimal(illiquid_cnt) / Decimal(n_items)
        low_share = Decimal(low_cnt) / Decimal(n_items)
        combo = illiq_share + low_share

    crit_dead = dead_share >= RULE_CRITICAL_DEAD_SHARE if total_denominator_money > ZERO else False
    if illiq_share >= RULE_CRITICAL_ILLIQ or crit_dead:
        return "CRITICAL"
    if combo >= RULE_IMBALANCED_COMBO:
        return "IMBALANCED"
    if combo >= RULE_WATCH_COMBO:
        return "WATCH"
    return "HEALTHY"


def _snapshot_read(row: PortfolioLiquiditySnapshot) -> PortfolioLiquiditySnapshotRead:
    return PortfolioLiquiditySnapshotRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        portfolio_id=row.portfolio_id,
        generation_scope_key=str(row.generation_scope_key),
        replay_key=str(row.replay_key or ""),
        total_portfolio_fmv=row.total_portfolio_fmv,
        liquid_portfolio_value=row.liquid_portfolio_value,
        illiquid_portfolio_value=row.illiquid_portfolio_value,
        liquidity_weighted_value=row.liquidity_weighted_value,
        liquidity_efficiency_score=row.liquidity_efficiency_score,
        liquidity_drag_score=row.liquidity_drag_score,
        concentration_risk_score=row.concentration_risk_score,
        dead_capital_estimate=row.dead_capital_estimate,
        liquidity_balance_status=str(row.liquidity_balance_status),  # type: ignore[arg-type]
        high_liquidity_count=int(row.high_liquidity_count),
        medium_liquidity_count=int(row.medium_liquidity_count),
        low_liquidity_count=int(row.low_liquidity_count),
        illiquid_count=int(row.illiquid_count),
        checksum=str(row.checksum),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _bucket_read(row: PortfolioLiquidityBucket) -> PortfolioLiquidityBucketRead:
    return PortfolioLiquidityBucketRead(
        id=int(row.id or 0),
        portfolio_liquidity_snapshot_id=int(row.portfolio_liquidity_snapshot_id),
        liquidity_bucket=str(row.liquidity_bucket),  # type: ignore[arg-type]
        item_count=int(row.item_count),
        total_fmv=row.total_fmv,
        weighted_liquidity_value=row.weighted_liquidity_value,
        percentage_of_portfolio=row.percentage_of_portfolio,
        created_at=row.created_at,
    )


def _evidence_read(row: PortfolioLiquidityEvidence) -> PortfolioLiquidityEvidenceRead:
    return PortfolioLiquidityEvidenceRead(
        id=int(row.id or 0),
        portfolio_liquidity_snapshot_id=int(row.portfolio_liquidity_snapshot_id),
        evidence_type=str(row.evidence_type),  # type: ignore[arg-type]
        source_id=row.source_id,
        source_table=row.source_table,
        evidence_value_json=dict(row.evidence_value_json or {}),
        created_at=row.created_at,
    )


def _history_read(row: PortfolioLiquidityHistory) -> PortfolioLiquidityHistoryRead:
    return PortfolioLiquidityHistoryRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        portfolio_id=row.portfolio_id,
        generation_scope_key=str(row.generation_scope_key),
        replay_key=str(row.replay_key or ""),
        liquidity_efficiency_score=row.liquidity_efficiency_score,
        liquidity_drag_score=row.liquidity_drag_score,
        concentration_risk_score=row.concentration_risk_score,
        dead_capital_estimate=row.dead_capital_estimate,
        liquidity_balance_status=str(row.liquidity_balance_status),  # type: ignore[arg-type]
        checksum=str(row.checksum),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _validate_portfolio(session: Session, *, owner_user_id: int, portfolio_id: int | None) -> None:
    if portfolio_id is None:
        return
    row = session.get(Portfolio, portfolio_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found for owner")


def generate_portfolio_liquidity(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioLiquidityGeneratePayload,
) -> PortfolioLiquidityGenerateResponse:
    snap_date = payload.snapshot_date or utc_today()
    rk = _norm_rk(payload.replay_key)
    portfolio_id = payload.portfolio_id
    _validate_portfolio(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)

    scope = scope_key(portfolio_id)
    inv_ids = _load_scope_inventory_ids(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    facts_ordered = _hydrate_facts(session, owner_user_id=owner_user_id, inv_ids=list(inv_ids))
    gross_sales, sales_items_set, listings_ct, convention_ct = _activity_signals(session, owner_user_id=owner_user_id, inv_ids=list(inv_ids))
    alloc_ck = _latest_allocation_checksum(session, owner_user_id=owner_user_id, generation_scope_key=scope)

    n_items = len(inv_ids)
    n_with_snap = sum(1 for f in facts_ordered.values() if f.liquidity_snapshot_id is not None)
    cov_pct = (Decimal(n_with_snap) / Decimal(max(n_items, 1))) * DEC_100

    per_item_fingerprints: list[dict[str, Any]] = []
    bucket_counts = {k: 0 for k in BUCKET_ORDER}
    bucket_fmv = {k: ZERO for k in BUCKET_ORDER}
    lw_row_total = ZERO
    high_fm = ZERO
    illiq_fm = ZERO
    low_fm = ZERO
    staleness_sum = ZERO
    sell_sum = ZERO
    staleness_snap_n = ZERO
    snap_ids_used: list[int] = []

    for iid in sorted(facts_ordered.keys()):
        row = facts_ordered[iid]
        bucket, wt = _portfolio_bucket_for_engine(row.engine_status)
        bucket_counts[bucket] += 1
        fv = _money(row.current_fmv) if row.current_fmv is not None else ZERO
        bucket_fmv[bucket] += fv
        lw_row_total += fv * wt
        if bucket == "HIGH":
            high_fm += fv
        elif bucket == "ILLIQUID":
            illiq_fm += fv
        elif bucket == "LOW":
            low_fm += fv
        per_item_fingerprints.append(
            {
                "inventory_item_id": iid,
                "fmv": _json_safe(fv),
                "liquidity_snapshot_id": row.liquidity_snapshot_id,
                "engine_status": row.engine_status,
                "portfolio_liquidity_bucket": bucket,
                "liquidity_weight": _json_safe(wt),
                "sell_through_pct": _json_safe(row.sell_through_pct),
                "stale_listing_rate_pct": _json_safe(row.stale_listing_rate_pct),
            }
        )
        if row.liquidity_snapshot_id:
            staleness_snap_n += 1
            staleness_sum += row.stale_listing_rate_pct
            sell_sum += row.sell_through_pct
            snap_ids_used.append(int(row.liquidity_snapshot_id))

    total_fmv = sum(bucket_fmv[k] for k in BUCKET_ORDER)
    denom_money = total_fmv if total_fmv > ZERO else ZERO

    avg_stale = staleness_sum / Decimal(max(staleness_snap_n, 1))
    avg_sell = sell_sum / Decimal(max(staleness_snap_n, 1))

    dead_base = low_fm * Decimal("0.45") + illiq_fm * Decimal("0.90")
    stale_floor = ZERO
    if avg_stale >= Decimal("70") and denom_money > ZERO:
        stale_floor = denom_money * Decimal("0.04")
    weak_sales = ZERO
    if avg_sell < Decimal("18") and staleness_snap_n >= 3 and denom_money > ZERO:
        weak_sales = denom_money * Decimal("0.025")
    dead_cap_raw = dead_base + stale_floor + weak_sales
    dead_capital = dead_cap_raw.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if dead_cap_raw > ZERO else ZERO

    efficiency = liquidity_drag = concentration = None
    if denom_money > ZERO:
        efficiency = _score_q(DEC_100 * (lw_row_total / denom_money))
        stale_component = avg_stale * Decimal("0.027")
        liquidity_drag = _score_q(
            (illiq_fm / denom_money * DEC_100 * Decimal("1.85"))
            + (low_fm / denom_money * DEC_100 * Decimal("0.72"))
            + stale_component
        )
        pct_map: dict[str, Decimal] = {k: (bucket_fmv[k] / denom_money) for k in BUCKET_ORDER}
        hhi = sum(p * p for p in pct_map.values())
        illiq_share = illiq_fm / denom_money
        concentration = _score_q(
            ((hhi - Decimal("0.25")) / Decimal("0.75")) * Decimal("60") + illiq_share * Decimal("40")
        )

    balance = _classify_balance(
        n_items=n_items,
        liquidity_coverage_pct=cov_pct,
        total_denominator_money=denom_money,
        illiquid_fmv=illiq_fm,
        low_fmv=low_fm,
        illiquid_cnt=bucket_counts["ILLIQUID"],
        low_cnt=bucket_counts["LOW"],
        dead_capital_estimate=dead_capital,
    )

    fp_payload: dict[str, Any] = {
        "algorithm": "portfolio_liquidity_p38_03_v1",
        "generation_scope_key": scope,
        "replay_key_normalized": rk,
        "snapshot_date": snap_date.isoformat(),
        "allocation_snapshot_checksum_latest": alloc_ck,
        "activity": {
            "gross_sales": _json_safe(gross_sales),
            "items_with_sale_lines": sorted(sales_items_set),
            "active_listings": listings_ct,
            "convention_active_assignments": convention_ct,
            "distinct_liquidity_engine_snapshot_ids_ordered": sorted(snap_ids_used),
        },
        "ordered_inventory": per_item_fingerprints,
        "coverage_pct": _json_safe(cov_pct),
        "totals_by_bucket": {k: _json_safe(bucket_fmv[k]) for k in BUCKET_ORDER},
        "liquidity_drag_components": {
            "illiquid_fmv_pct_weight": str(Decimal("1.85")),
            "low_liquidity_fmv_pct_weight": str(Decimal("0.72")),
            "average_stale_listing_pct_from_engine": _json_safe(avg_stale),
            "average_stale_additive_drag_scale": str(Decimal("0.027")),
            "formula": (
                "(illiquid_share * 100 * 1.85) + (low_share * 100 * 0.72) + (avg_engine_stale_rate_pct * 0.027), "
                "clamped into 0-100 snapshot score"
            ),
        },
        "dead_capital_inputs": {
            "low_inventory_weight": str(Decimal("0.45")),
            "illiquid_inventory_weight": str(Decimal("0.90")),
            "stale_floor_threshold_pct": str(Decimal("70")),
            "stale_floor_share_of_fmv_when_triggered": str(Decimal("0.04")),
            "weak_sales_sell_through_threshold_pct": str(Decimal("18")),
            "minimum_engine_rows_for_sales_weak_floor": "3",
            "weak_sales_fmv_addon": str(Decimal("0.025")),
            "coverage_insufficient_below_pct_of_items": _json_safe(COV_INSUFFICIENT * DEC_100),
        },
        "distribution_thresholds_pct": {
            "critical_min_illiquid_share": _json_safe(RULE_CRITICAL_ILLIQ * DEC_100),
            "critical_min_dead_share_of_fmv": _json_safe(RULE_CRITICAL_DEAD_SHARE * DEC_100),
            "imbalanced_combo_min": _json_safe(RULE_IMBALANCED_COMBO * DEC_100),
            "watch_combo_min": _json_safe(RULE_WATCH_COMBO * DEC_100),
        },
        "classified_balance_status": balance,
    }
    checksum = _hash_payload(fp_payload)

    existing = session.exec(
        select(PortfolioLiquiditySnapshot).where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == scope,
            PortfolioLiquiditySnapshot.snapshot_date == snap_date,
            PortfolioLiquiditySnapshot.replay_key == rk,
        )
    ).first()

    if existing is not None and str(existing.checksum) == checksum:
        bk_rows = session.exec(
            select(PortfolioLiquidityBucket)
            .where(PortfolioLiquidityBucket.portfolio_liquidity_snapshot_id == int(existing.id))
            .order_by(col(PortfolioLiquidityBucket.liquidity_bucket).asc())
        ).all()
        return PortfolioLiquidityGenerateResponse(
            replayed=True,
            snapshot=_snapshot_read(existing),
            buckets=[_bucket_read(b) for b in bk_rows],
            history_appended=False,
        )

    if existing is not None:
        sid = int(existing.id)
        session.exec(delete(PortfolioLiquidityEvidence).where(PortfolioLiquidityEvidence.portfolio_liquidity_snapshot_id == sid))
        session.exec(delete(PortfolioLiquidityBucket).where(PortfolioLiquidityBucket.portfolio_liquidity_snapshot_id == sid))
        session.delete(existing)
        session.flush()

    snap_row = PortfolioLiquiditySnapshot(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        generation_scope_key=scope,
        replay_key=rk,
        total_portfolio_fmv=total_fmv if total_fmv > ZERO else None,
        liquid_portfolio_value=high_fm if high_fm > ZERO else None,
        illiquid_portfolio_value=illiq_fm if illiq_fm > ZERO else None,
        liquidity_weighted_value=lw_row_total if lw_row_total > ZERO else None,
        liquidity_efficiency_score=efficiency,
        liquidity_drag_score=liquidity_drag,
        concentration_risk_score=concentration,
        dead_capital_estimate=dead_capital if dead_capital > ZERO else None,
        liquidity_balance_status=str(balance),
        high_liquidity_count=bucket_counts["HIGH"],
        medium_liquidity_count=bucket_counts["MEDIUM"],
        low_liquidity_count=bucket_counts["LOW"],
        illiquid_count=bucket_counts["ILLIQUID"],
        checksum=checksum,
        snapshot_date=snap_date,
    )
    session.add(snap_row)
    session.flush()
    sid = int(snap_row.id or 0)

    pct_denom = total_fmv if total_fmv > ZERO else ZERO
    for bname in BUCKET_ORDER:
        bfm = bucket_fmv[bname]
        wt = BUCKET_WEIGHTS[bname]
        if pct_denom > ZERO:
            pct = (bfm / pct_denom * DEC_100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        else:
            pct = None
        wsum = bfm * wt

        bk = PortfolioLiquidityBucket(
            portfolio_liquidity_snapshot_id=sid,
            liquidity_bucket=bname,
            item_count=int(bucket_counts[bname]),
            total_fmv=bfm if bfm > ZERO else None,
            weighted_liquidity_value=wsum if wsum > ZERO else None,
            percentage_of_portfolio=pct,
        )
        session.add(bk)

    evidence_payloads = [
        (
            "FMV",
            None,
            "inventory_copy",
            {
                "computed_total_scope_fmv": _json_safe(total_fmv),
                "items_in_scope_count": n_items,
                "null_fmv_inventory_ids": sorted(
                    [fid for fid, fx in facts_ordered.items() if fx.current_fmv is None]
                ),
                "formula": "sum(current_fmv) over scope rows; null fmvs treated as 0 contribution",
            },
        ),
        (
            "LIQUIDITY_ENGINE",
            None,
            "inventory_liquidity_snapshot",
            {
                "items_with_snapshots": int(n_with_snap),
                "coverage_pct": _json_safe(cov_pct),
                "ordered_snapshot_reference_ids": sorted(snap_ids_used),
                "engine_mappings": _json_safe(_engine_label_map_evidence_json()),
                "formula": (
                    "map latest engine liquidity_status HIGH/MODERATE/LOW/ILLIQUID to portfolio buckets; "
                    "missing engine → MEDIUM bucket weight 0.55"
                ),
            },
        ),
        (
            "SALES_LEDGER",
            None,
            "sale_record_line_item",
            {
                "gross_sale_line_subtotal": _json_safe(gross_sales),
                "distinct_inventory_with_sales_lines": len(sales_items_set),
                "sample_inventory_ids": sorted(sales_items_set)[:64],
                "formula": "sum RECORDED sale line amounts for inventories in generation scope only",
            },
        ),
        (
            "LISTING_INTELLIGENCE",
            None,
            "listing_registry",
            {
                "non_archived_listing_rows": listings_ct,
                "formula": "count active Listing rows anchored to inventories in generation scope only",
            },
        ),
        (
            "CONVENTION_ACTIVITY",
            None,
            "convention_inventory_assignment",
            {
                "active_assignments": convention_ct,
                "formula": "count assignments removed_at=null joined to ACTIVE convention events scoped to owner",
            },
        ),
        (
            "PORTFOLIO_REGISTRY",
            sid,
            "portfolio_allocation_snapshot",
            {
                "generation_scope_key": scope,
                "latest_allocation_checksum": alloc_ck,
                "formula": "latest PortfolioAllocationSnapshot row checksum for identical generation_scope_key anchor",
            },
        ),
    ]
    for ev_type, src_id, src_table, ej in evidence_payloads:
        session.add(
            PortfolioLiquidityEvidence(
                portfolio_liquidity_snapshot_id=sid,
                evidence_type=str(ev_type),
                source_id=src_id,
                source_table=str(src_table),
                evidence_value_json=ej,
            )
        )

    hist = PortfolioLiquidityHistory(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        generation_scope_key=scope,
        replay_key=rk,
        liquidity_efficiency_score=snap_row.liquidity_efficiency_score,
        liquidity_drag_score=snap_row.liquidity_drag_score,
        concentration_risk_score=snap_row.concentration_risk_score,
        dead_capital_estimate=snap_row.dead_capital_estimate,
        liquidity_balance_status=str(balance),
        checksum=checksum,
        snapshot_date=snap_date,
    )
    session.add(hist)

    session.commit()

    refreshed = session.get(PortfolioLiquiditySnapshot, sid)
    assert refreshed is not None
    bk_final = session.exec(
        select(PortfolioLiquidityBucket)
        .where(PortfolioLiquidityBucket.portfolio_liquidity_snapshot_id == sid)
        .order_by(col(PortfolioLiquidityBucket.liquidity_bucket).asc())
    ).all()
    history_appended = session.exec(
        select(PortfolioLiquidityHistory).where(
            PortfolioLiquidityHistory.owner_user_id == owner_user_id,
            PortfolioLiquidityHistory.generation_scope_key == scope,
            PortfolioLiquidityHistory.snapshot_date == snap_date,
            PortfolioLiquidityHistory.replay_key == rk,
            PortfolioLiquidityHistory.checksum == checksum,
        )
    ).first() is not None

    return PortfolioLiquidityGenerateResponse(
        replayed=False,
        snapshot=_snapshot_read(refreshed),
        buckets=[_bucket_read(b) for b in bk_final],
        history_appended=bool(history_appended),
    )


def list_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None = None,
    liquidity_balance_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
    latest_only: bool = False,
) -> PortfolioLiquiditySnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    conds: list[Any] = [PortfolioLiquiditySnapshot.owner_user_id == owner_user_id]
    if portfolio_id is not None:
        conds.append(PortfolioLiquiditySnapshot.portfolio_id == portfolio_id)
    if latest_only and portfolio_id is None:
        conds.append(PortfolioLiquiditySnapshot.generation_scope_key == SCOPE_ALL_INVENTORY)
    if liquidity_balance_status:
        conds.append(PortfolioLiquiditySnapshot.liquidity_balance_status == liquidity_balance_status)
    if snapshot_date_from:
        conds.append(col(PortfolioLiquiditySnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to:
        conds.append(col(PortfolioLiquiditySnapshot.snapshot_date) <= snapshot_date_to)

    where_clause = and_(*conds)
    total = int(
        session.exec(
            select(func.count()).select_from(PortfolioLiquiditySnapshot).where(where_clause),
        ).one()
    )

    stmt = (
        select(PortfolioLiquiditySnapshot)
        .where(where_clause)
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    )
    if latest_only:
        stmt = stmt.limit(1)
    else:
        stmt = stmt.offset(offset).limit(limit)

    rows = list(session.exec(stmt).all())
    return PortfolioLiquiditySnapshotListResponse(items=[_snapshot_read(r) for r in rows], total=total)


def get_snapshot_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> PortfolioLiquiditySnapshotRead:
    row = session.get(PortfolioLiquiditySnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio liquidity snapshot not found")
    return _snapshot_read(row)


def get_snapshot_detail_owner(
    session: Session, *, owner_user_id: int, snapshot_id: int
) -> tuple[PortfolioLiquiditySnapshotRead, list[PortfolioLiquidityBucketRead]]:
    snap = get_snapshot_owner(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    bk = session.exec(
        select(PortfolioLiquidityBucket)
        .where(PortfolioLiquidityBucket.portfolio_liquidity_snapshot_id == snapshot_id)
        .order_by(col(PortfolioLiquidityBucket.liquidity_bucket).asc())
    ).all()
    return snap, [_bucket_read(b) for b in bk]


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_liquidity_snapshot_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioLiquidityEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    join_on = PortfolioLiquidityEvidence.portfolio_liquidity_snapshot_id == PortfolioLiquiditySnapshot.id
    conds = [PortfolioLiquiditySnapshot.owner_user_id == owner_user_id]
    if portfolio_liquidity_snapshot_id is not None:
        conds.append(PortfolioLiquidityEvidence.portfolio_liquidity_snapshot_id == portfolio_liquidity_snapshot_id)
    if evidence_type:
        conds.append(PortfolioLiquidityEvidence.evidence_type == evidence_type)
    where_clause = and_(*conds)
    total = int(
        session.exec(
            select(func.count())
            .select_from(PortfolioLiquidityEvidence)
            .join(PortfolioLiquiditySnapshot, join_on)
            .where(where_clause),
        ).one(),
    )
    rows = session.exec(
        select(PortfolioLiquidityEvidence)
        .join(PortfolioLiquiditySnapshot, join_on)
        .where(where_clause)
        .order_by(col(PortfolioLiquidityEvidence.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioLiquidityEvidenceListResponse(items=[_evidence_read(r) for r in rows], total=total)


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None = None,
    liquidity_balance_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioLiquidityHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    conds = [PortfolioLiquidityHistory.owner_user_id == owner_user_id]
    if portfolio_id is not None:
        conds.append(PortfolioLiquidityHistory.portfolio_id == portfolio_id)
    if liquidity_balance_status:
        conds.append(PortfolioLiquidityHistory.liquidity_balance_status == liquidity_balance_status)
    if snapshot_date_from:
        conds.append(col(PortfolioLiquidityHistory.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to:
        conds.append(col(PortfolioLiquidityHistory.snapshot_date) <= snapshot_date_to)
    where_clause = and_(*conds)
    total = int(session.exec(select(func.count()).select_from(PortfolioLiquidityHistory).where(where_clause)).one())  # type: ignore[arg-type]
    rows = session.exec(
        select(PortfolioLiquidityHistory)
        .where(where_clause)
        .order_by(col(PortfolioLiquidityHistory.snapshot_date).desc(), col(PortfolioLiquidityHistory.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioLiquidityHistoryListResponse(items=[_history_read(r) for r in rows], total=total)


def list_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    liquidity_balance_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
    latest_only: bool = False,
) -> PortfolioLiquiditySnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    conds: list[Any] = []
    if owner_user_id is not None:
        conds.append(PortfolioLiquiditySnapshot.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        conds.append(PortfolioLiquiditySnapshot.portfolio_id == portfolio_id)
    if latest_only and portfolio_id is None and owner_user_id is not None:
        conds.append(PortfolioLiquiditySnapshot.generation_scope_key == SCOPE_ALL_INVENTORY)
    if liquidity_balance_status:
        conds.append(PortfolioLiquiditySnapshot.liquidity_balance_status == liquidity_balance_status)
    if snapshot_date_from:
        conds.append(col(PortfolioLiquiditySnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to:
        conds.append(col(PortfolioLiquiditySnapshot.snapshot_date) <= snapshot_date_to)
    where_clause = and_(*conds) if conds else literal(True)
    total = int(
        session.exec(
            select(func.count()).select_from(PortfolioLiquiditySnapshot).where(where_clause),
        ).one()
    )
    stmt = (
        select(PortfolioLiquiditySnapshot)
        .where(where_clause)
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    )
    if latest_only:
        stmt = stmt.limit(1)
    else:
        stmt = stmt.offset(offset).limit(limit)
    rows = list(session.exec(stmt).all())
    return PortfolioLiquiditySnapshotListResponse(items=[_snapshot_read(r) for r in rows], total=total)


def get_snapshot_ops(
    session: Session, *, owner_user_id: int | None, snapshot_id: int
) -> PortfolioLiquiditySnapshotRead:
    row = session.get(PortfolioLiquiditySnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio liquidity snapshot not found")
    if owner_user_id is not None and int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio liquidity snapshot not found")
    return _snapshot_read(row)


def get_snapshot_detail_ops(
    session: Session, *, owner_user_id: int | None, snapshot_id: int
) -> tuple[PortfolioLiquiditySnapshotRead, list[PortfolioLiquidityBucketRead]]:
    snap = get_snapshot_ops(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    bk = session.exec(
        select(PortfolioLiquidityBucket)
        .where(PortfolioLiquidityBucket.portfolio_liquidity_snapshot_id == snapshot_id)
        .order_by(col(PortfolioLiquidityBucket.liquidity_bucket).asc())
    ).all()
    return snap, [_bucket_read(b) for b in bk]


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_liquidity_snapshot_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioLiquidityEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    join_on = PortfolioLiquidityEvidence.portfolio_liquidity_snapshot_id == PortfolioLiquiditySnapshot.id
    conds: list[Any] = []
    if owner_user_id is not None:
        conds.append(PortfolioLiquiditySnapshot.owner_user_id == owner_user_id)
    if portfolio_liquidity_snapshot_id is not None:
        conds.append(PortfolioLiquidityEvidence.portfolio_liquidity_snapshot_id == portfolio_liquidity_snapshot_id)
    if evidence_type:
        conds.append(PortfolioLiquidityEvidence.evidence_type == evidence_type)
    where_clause = and_(*conds) if conds else literal(True)
    total = int(
        session.exec(
            select(func.count())
            .select_from(PortfolioLiquidityEvidence)
            .join(PortfolioLiquiditySnapshot, join_on)
            .where(where_clause),
        ).one(),
    )
    rows = session.exec(
        select(PortfolioLiquidityEvidence)
        .join(PortfolioLiquiditySnapshot, join_on)
        .where(where_clause)
        .order_by(col(PortfolioLiquidityEvidence.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioLiquidityEvidenceListResponse(items=[_evidence_read(r) for r in rows], total=total)


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    liquidity_balance_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioLiquidityHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    conds: list[Any] = []
    if owner_user_id is not None:
        conds.append(PortfolioLiquidityHistory.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        conds.append(PortfolioLiquidityHistory.portfolio_id == portfolio_id)
    if liquidity_balance_status:
        conds.append(PortfolioLiquidityHistory.liquidity_balance_status == liquidity_balance_status)
    if snapshot_date_from:
        conds.append(col(PortfolioLiquidityHistory.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to:
        conds.append(col(PortfolioLiquidityHistory.snapshot_date) <= snapshot_date_to)
    where_clause = and_(*conds) if conds else literal(True)
    total = int(session.exec(select(func.count()).select_from(PortfolioLiquidityHistory).where(where_clause)).one())  # type: ignore[arg-type]
    rows = session.exec(
        select(PortfolioLiquidityHistory)
        .where(where_clause)
        .order_by(col(PortfolioLiquidityHistory.snapshot_date).desc(), col(PortfolioLiquidityHistory.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioLiquidityHistoryListResponse(items=[_history_read(r) for r in rows], total=total)


def inventory_portfolio_liquidity_teaser(
    session: Session, *, owner_user_id: int, inventory_item_id: int
) -> InventoryPortfolioLiquidityTeaser | None:
    inv = session.get(InventoryCopy, inventory_item_id)
    if inv is None or int(inv.user_id) != owner_user_id:
        return None
    facts = _hydrate_facts(session, owner_user_id=owner_user_id, inv_ids=[inventory_item_id])
    fact = facts[int(inventory_item_id)]
    bucket, _w = _portfolio_bucket_for_engine(fact.engine_status)
    port = session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == SCOPE_ALL_INVENTORY,
        )
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    ).first()
    dead_teaser = None
    if bucket in ("LOW", "ILLIQUID"):
        dead_teaser = "This copy maps to a weak portfolio liquidity bucket (observational dead-capital drag signal)."
    return InventoryPortfolioLiquidityTeaser(
        portfolio_liquidity_bucket=bucket,  # type: ignore[arg-type]
        liquidity_engine_status=fact.engine_status,
        portfolio_liquidity_snapshot_id=int(port.id) if port else None,
        liquidity_efficiency_score=str(port.liquidity_efficiency_score) if port and port.liquidity_efficiency_score is not None else None,
        dead_capital_estimate=str(port.dead_capital_estimate) if port and port.dead_capital_estimate is not None else None,
        liquidity_balance_status=str(port.liquidity_balance_status) if port else None,
        dead_capital_teaser=dead_teaser,
    )

