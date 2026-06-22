"""P38-02 deterministic duplicate detection & consolidation intelligence (no automation)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, update
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    DuplicateCluster,
    DuplicateClusterItem,
    DuplicateConsolidationRecommendation,
    DuplicateHistorySnapshot,
    GradingCandidate,
    GradingRecommendation,
    GradingRiskSnapshot,
    GradingRoiSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Portfolio,
    PortfolioItem,
)
from app.services.inventory_canonical_spine import apply_inventory_spine_joins
from app.schemas.duplicate_consolidation import (
    DuplicateClusterGeneratePayload,
    DuplicateClusterGenerateResponse,
    DuplicateClusterItemListResponse,
    DuplicateClusterItemRead,
    DuplicateClusterListResponse,
    DuplicateClusterRead,
    DuplicateConsolidationRecommendationListResponse,
    DuplicateConsolidationRecommendationRead,
    DuplicateHistoryListResponse,
    DuplicateHistorySnapshotRead,
    DuplicateIntelligenceSummary,
    DuplicateOpportunityBrief,
    InventoryDuplicateIntelligenceTeaser,
)

MONEY_QUANT = Decimal("0.01")
SCORE_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")

PIPELINE_STATUSES = frozenset({"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED"})

LIQ_MAP = {"HIGH": 85, "MODERATE": 70, "LOW": 42, "ILLIQUID": 18, "INSUFFICIENT_DATA": 55}


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _money(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _score(value: Any | None) -> Decimal:
    return _money(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm_rk(value: str | None) -> str:
    return (value or "").strip()


@dataclass(frozen=True)
class _InvSnap:
    inventory_item_id: int
    canonical_comic_issue_id: int
    variant_id: int
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    grade_normalized: str
    hold_normalized: str
    in_pipeline: bool
    portfolio_ids: tuple[int, ...]


def _classify_duplicate_grading(*, gs_norm: str, in_pipeline: bool) -> str:
    if in_pipeline:
        return "GRADING_PIPELINE"
    if gs_norm == "raw":
        return "RAW"
    return "GRADED"


def _liquidity_profile_for_scores(scores: list[int]) -> str:
    if not scores:
        return "LOW"
    avg = sum(scores) / len(scores)
    if avg >= 72:
        return "HIGH"
    if avg >= 50:
        return "MEDIUM"
    return "LOW"


def _duplication_status_rules(
    *,
    total_items: int,
    liquidity_profile: str,
    weak_fmv_ratio: Decimal | None,
) -> str:
    """Documented deterministic buckets (counts + optional weak-tail FMV share)."""
    if total_items < 2:
        return "HEALTHY"
    n = total_items
    tier = ""
    if n <= 2:
        tier = "HEALTHY"
    elif n == 3:
        tier = "WATCH"
    elif n <= 5:
        tier = "REDUNDANT"
    else:
        tier = "OVEREXPOSED"
    bumps = 0
    if liquidity_profile == "LOW" and n >= 3:
        bumps += 1
    if weak_fmv_ratio is not None and weak_fmv_ratio >= Decimal("35"):
        bumps += 1

    ordering = ["HEALTHY", "WATCH", "REDUNDANT", "OVEREXPOSED"]
    idx = ordering.index(tier)
    idx = min(len(ordering) - 1, idx + bumps)
    return ordering[idx]


def _latest_liquidity_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, str | None]:
    out: dict[int, str | None] = {}
    if not inv_ids:
        return out
    liq_rows = session.exec(
        select(InventoryLiquiditySnapshot)
        .where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            col(InventoryLiquiditySnapshot.inventory_item_id).in_(inv_ids),
            col(InventoryLiquiditySnapshot.inventory_item_id).is_not(None),
        )
        .order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc(), col(InventoryLiquiditySnapshot.id).desc())
    ).all()
    for row in liq_rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = str(row.liquidity_status or "")
    return out


def _latest_gr_reco_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, GradingRecommendation]:
    out: dict[int, GradingRecommendation] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(GradingRecommendation)
        .where(
            GradingRecommendation.owner_user_id == owner_user_id,
            col(GradingRecommendation.inventory_item_id).in_(inv_ids),
            col(GradingRecommendation.inventory_item_id).is_not(None),
        )
        .order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _latest_risk_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, GradingRiskSnapshot]:
    out: dict[int, GradingRiskSnapshot] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(GradingRiskSnapshot)
        .where(
            GradingRiskSnapshot.owner_user_id == owner_user_id,
            col(GradingRiskSnapshot.inventory_item_id).in_(inv_ids),
            col(GradingRiskSnapshot.inventory_item_id).is_not(None),
        )
        .order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _latest_roi_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, GradingRoiSnapshot]:
    out: dict[int, GradingRoiSnapshot] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(GradingRoiSnapshot)
        .where(
            GradingRoiSnapshot.owner_user_id == owner_user_id,
            col(GradingRoiSnapshot.inventory_item_id).in_(inv_ids),
            col(GradingRoiSnapshot.inventory_item_id).is_not(None),
        )
        .order_by(col(GradingRoiSnapshot.snapshot_date).desc(), col(GradingRoiSnapshot.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _load_owner_snapshots(session: Session, *, owner_user_id: int) -> list[_InvSnap]:
    gc_rows = session.exec(
        select(GradingCandidate)
        .where(GradingCandidate.owner_user_id == owner_user_id, GradingCandidate.archived_at.is_(None))
    ).all()
    pipeline_items: dict[int, str] = {}
    for gc in gc_rows:
        if gc.status.upper() in {s.upper() for s in PIPELINE_STATUSES}:
            pipeline_items[int(gc.inventory_item_id)] = gc.status.upper()

    pi_rows = session.exec(
        select(PortfolioItem, Portfolio)
        .join(Portfolio, PortfolioItem.portfolio_id == Portfolio.id)
        .where(Portfolio.owner_user_id == owner_user_id, PortfolioItem.removed_at.is_(None))
    ).all()

    pis_by_inventory: defaultdict[int, set[int]] = defaultdict(set)
    for pi, pf in pi_rows:
        pis_by_inventory[int(pi.inventory_item_id)].add(int(pi.portfolio_id))

    # Unify both spines: prefer the legacy comic_issue/variant identity, fall back
    # to the master-catalog ids on the copy. Copies with neither (unidentified) can
    # not be clustered, so they are skipped.
    stmt = (
        apply_inventory_spine_joins(
            select(
                InventoryCopy,
                func.coalesce(ComicIssue.id, InventoryCopy.catalog_issue_id).label("issue_id"),
            ).select_from(InventoryCopy)
        )
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(col(InventoryCopy.id).asc())
    )
    snaps: list[_InvSnap] = []
    for inv, issue_id in session.exec(stmt).all():
        iid = int(inv.id or 0)
        variant_key = inv.variant_id if inv.variant_id is not None else inv.catalog_variant_id
        if not iid or issue_id is None or variant_key is None:
            continue
        gs = str(inv.grade_status or "raw").lower()
        hold = str(inv.hold_status or "hold").lower()
        in_pipe = iid in pipeline_items
        snaps.append(
            _InvSnap(
                inventory_item_id=iid,
                canonical_comic_issue_id=int(issue_id),
                variant_id=int(variant_key),
                acquisition_cost=_money(inv.acquisition_cost),
                current_fmv=_money(inv.current_fmv) if inv.current_fmv is not None else None,
                grade_normalized=gs,
                hold_normalized=hold,
                in_pipeline=in_pipe,
                portfolio_ids=tuple(sorted(pis_by_inventory.get(iid, set()))),
            )
        )
    return snaps


def _build_cluster_specs(snaps: list[_InvSnap]) -> list[dict[str, Any]]:
    by_issue: dict[int, list[_InvSnap]] = defaultdict(list)
    by_variant: dict[int, list[_InvSnap]] = defaultdict(list)
    for s in snaps:
        by_issue[s.canonical_comic_issue_id].append(s)
        by_variant[s.variant_id].append(s)

    specs: list[dict[str, Any]] = []

    def register(*, cluster_type: str, cluster_key: str, issue_id: int | None, members: list[_InvSnap]) -> None:
        inv_ids = sorted({m.inventory_item_id for m in members})
        if len(inv_ids) < 2:
            return
        specs.append(
            {
                "cluster_type": cluster_type,
                "cluster_key": cluster_key,
                "canonical_comic_issue_id": issue_id,
                "inventory_item_ids": inv_ids,
            }
        )

    for issue_id, members in sorted(by_issue.items()):
        mids = sorted(members, key=lambda m: m.inventory_item_id)
        if len(mids) < 2:
            continue
        register(cluster_type="exact_issue", cluster_key=f"exact_issue::{issue_id}", issue_id=issue_id, members=mids)

        graded = [m for m in mids if _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline) == "GRADED"]


        if len(graded) >= 2:
            register(cluster_type="graded_overlap", cluster_key=f"graded_overlap::{issue_id}", issue_id=issue_id, members=graded)

        raw_flags = [
            _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline) == "RAW" for m in mids
        ]
        has_raw = any(raw_flags)
        has_pipeline = any(
            _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline) == "GRADING_PIPELINE"
            for m in mids
        )
        has_graded = len(graded) >= 1
        if len(mids) >= 2 and has_graded and (has_raw or has_pipeline):
            register(
                cluster_type="raw_graded_overlap",
                cluster_key=f"raw_graded_overlap::{issue_id}",
                issue_id=issue_id,
                members=mids,
            )

        port_union: set[int] = set()
        for m in mids:
            port_union.update(m.portfolio_ids)
        if len(mids) >= 2 and len(port_union) >= 2:
            register(
                cluster_type="portfolio_overlap",
                cluster_key=f"portfolio_overlap::{issue_id}",
                issue_id=issue_id,
                members=mids,
            )

    for variant_id, members in sorted(by_variant.items()):
        mids = sorted(members, key=lambda m: m.inventory_item_id)
        if len(mids) < 2:
            continue
        issue_anchor = mids[0].canonical_comic_issue_id
        register(cluster_type="variant_family", cluster_key=f"variant_family::{variant_id}", issue_id=issue_anchor, members=mids)

    dedupe: dict[tuple[str, str], dict[str, Any]] = {}
    for row in specs:
        dedupe[(row["cluster_type"], row["cluster_key"])] = row
    return sorted(dedupe.values(), key=lambda r: (r["cluster_type"], r["cluster_key"]))


def _fm_rank_points(*, sorted_members: list[_InvSnap]) -> dict[int, Decimal]:
    n = len(sorted_members)
    pts: dict[int, Decimal] = {}
    # Sort strength order: FMV desc (None last via key), acquisition desc, inventory id asc
    order = sorted(
        sorted_members,
        key=lambda m: (-(m.current_fmv or ZERO), -(m.acquisition_cost), m.inventory_item_id),
    )
    for idx, snap in enumerate(order):
        if n <= 1:
            pts[snap.inventory_item_id] = _score(Decimal("25"))
        else:
            span = Decimal("37") - Decimal("10")
            frac = Decimal(idx) / Decimal(n - 1)
            pts[snap.inventory_item_id] = _score(Decimal("37") - frac * span)
    return pts


def _risk_penalty(risk: GradingRiskSnapshot | None) -> Decimal:
    if risk is None:
        return ZERO
    lvl = (risk.overall_risk_level or "").upper()
    if lvl == "HIGH":
        return _score(Decimal("12"))
    if lvl == "MEDIUM":
        return _score(Decimal("7"))
    if lvl == "LOW":
        return _score(Decimal("2"))
    return _score(Decimal("5"))


def _reco_bonus(rec: GradingRecommendation | None) -> Decimal:
    if rec is None:
        return ZERO
    strength_map = {"ELITE": 14, "STRONG": 11, "MODERATE": 8, "WEAK": 4, "MARGINAL": 2}
    key = (rec.recommendation_strength or "").upper()
    pts = Decimal(str(strength_map.get(key, 4)))
    if rec.confidence_score is not None and rec.confidence_score >= Decimal("80"):
        pts += Decimal("5")
    return _score(min(pts, Decimal("22")))


def _roi_bonus(roi_row: GradingRoiSnapshot | None) -> Decimal:
    if roi_row is None or roi_row.liquidity_adjusted_roi is None:
        return ZERO
    v = roi_row.liquidity_adjusted_roi
    if v >= Decimal("25"):
        return _score(Decimal("11"))
    if v >= Decimal("15"):
        return _score(Decimal("8"))
    if v >= Decimal("8"):
        return _score(Decimal("4"))
    return ZERO


def _grade_points(gs: str) -> Decimal:
    if gs == "GRADED":
        return Decimal("39")
    if gs == "GRADING_PIPELINE":
        return Decimal("30")
    return Decimal("24")


def _compute_strengths(
    *,
    members: list[_InvSnap],
    liq_map: dict[int, str | None],
    reco_map: dict[int, GradingRecommendation],
    risk_map: dict[int, GradingRiskSnapshot],
    roi_map: dict[int, GradingRoiSnapshot],
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    strength: dict[int, Decimal] = {}
    liq_score: dict[int, Decimal] = {}
    fm_rank = _fm_rank_points(sorted_members=sorted(members, key=lambda m: m.inventory_item_id))

    for m in members:
        gs = _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline)
        liq_txt = (liq_map.get(m.inventory_item_id) or "").upper() or ""
        liquidity_points = Decimal(str(LIQ_MAP.get(liq_txt, 40)))

        contrib = liquidity_points * Decimal("0.30") + fm_rank[m.inventory_item_id] + _grade_points(gs)
        contrib += _reco_bonus(reco_map.get(m.inventory_item_id))
        contrib += _roi_bonus(roi_map.get(m.inventory_item_id))
        contrib -= _risk_penalty(risk_map.get(m.inventory_item_id))

        val = contrib.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
        if val < ZERO:
            val = ZERO
        if val > Decimal("100"):
            val = Decimal("100")

        strength[m.inventory_item_id] = val
        liq_score[m.inventory_item_id] = liquidity_points.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
    return strength, liq_score


def _priority_for_inventory(
    *,
    members_sorted: list[_InvSnap],
    strengths: dict[int, Decimal],
    duplication_status: str,
) -> dict[int, str]:
    ranking = sorted(
        members_sorted,
        key=lambda m: (-strengths[m.inventory_item_id], m.inventory_item_id),
    )
    n = len(ranking)
    keep_id = ranking[0].inventory_item_id
    out: dict[int, str] = {}
    for idx, snap in enumerate(ranking):
        iid = snap.inventory_item_id
        if duplication_status == "HEALTHY" and snap.hold_normalized == "sell":
            prio = "SELL_CANDIDATE"
        elif iid == keep_id:
            prio = "KEEP"
        elif idx >= max(1, int((2 * n) / 3)) or duplication_status == "OVEREXPOSED":
            prio = "CONSOLIDATE" if snap.hold_normalized != "sell" else "SELL_CANDIDATE"
        elif idx >= max(1, int(n / 3)):
            prio = "WATCH"
        elif snap.portfolio_ids and duplication_status in {"REDUNDANT", "OVEREXPOSED"}:
            prio = "WATCH"
        else:
            prio = "KEEP" if duplication_status == "HEALTHY" else "WATCH"
        # Portfolio duplicate tagging from portfolio_roles not persisted per item here; degrade weak tail
        out[iid] = prio
    return out


def _consolidate_action_and_rationale(
    *,
    cluster_type: str,
    duplication_status: str,
    members: list[_InvSnap],
    strengths: dict[int, Decimal],
    priorities: dict[int, str],
) -> tuple[str, str, str, Decimal | None, Decimal | None, Decimal | None]:
    ranking = sorted(members, key=lambda m: (-strengths[m.inventory_item_id], m.inventory_item_id))
    weak_tail = ranking[len(ranking) // 2 :]
    capital_tail = sum(m.acquisition_cost for m in weak_tail if priorities[m.inventory_item_id] != "KEEP")

    if duplication_status == "HEALTHY":
        return ("HOLD", "Duplicate posture is proportionate vs documented thresholds.", "HIGH", ZERO, ZERO, ZERO)

    over = duplication_status == "OVEREXPOSED"

    graded = [_classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline) for m in members]
    has_graded = any(g == "GRADED" for g in graded)
    has_raw = any(
        _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline) == "RAW" for m in members
    )

    if cluster_type == "raw_graded_overlap" and has_raw and has_graded:
        raw_members = [
            m
            for m in members
            if _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline) == "RAW"
        ]
        best_raw = max(raw_members, key=lambda m: (strengths[m.inventory_item_id], -m.inventory_item_id))
        return (
            "GRADE_STRONGEST_COPY",
            "Issue mixes raw and graded duplicates; observational note to favor grading the strongest raw duplicate "
            f"(inventory {best_raw.inventory_item_id}) while monitoring slab overlap.",
            "MEDIUM",
            _money(capital_tail) if capital_tail else None,
            _score(Decimal("35")) if over else _score(Decimal("15")),
            _score(Decimal("40")) if over else _score(Decimal("20")),
        )

    if over or duplication_status == "REDUNDANT":
        return (
            "REDUCE_EXPOSURE",
            "Duplicate depth exceeds watch thresholds; capital is observably concentrated on the same issue/variant.",
            "HIGH" if over else "MEDIUM",
            _money(capital_tail) if capital_tail else None,
            _score(Decimal("45")) if over else _score(Decimal("25")),
            _score(Decimal("55")) if over else _score(Decimal("30")),
        )

    weak_ids = {m.inventory_item_id for m in weak_tail if priorities[m.inventory_item_id] in {"CONSOLIDATE", "SELL_CANDIDATE"}}
    if len(weak_ids) >= 1 and cluster_type in {"variant_family", "exact_issue"}:
        return (
            "SELL_DUPLICATES",
            "Weaker tail copies are flagged for consolidation review (no automated listing).",
            "MEDIUM",
            _money(capital_tail) if capital_tail else None,
            _score(Decimal("30")),
            _score(Decimal("24")),
        )

    return (
        "KEEP_BEST_COPY",
        "Strongest duplicate copy remains the retention anchor; others stay on watch.",
        "MEDIUM",
        _money(capital_tail) if capital_tail else None,
        _score(Decimal("18")),
        _score(Decimal("22")),
    )


def _cluster_row_checksum(
    *,
    cluster_type: str,
    cluster_key: str,
    inventory_item_ids: list[int],
    duplication_status: str,
    liquidity_profile: str,
    item_fingerprints: list[dict[str, Any]],
) -> str:
    payload = {
        "cluster_type": cluster_type,
        "cluster_key": cluster_key,
        "inventory_item_ids": inventory_item_ids,
        "duplication_status": duplication_status,
        "liquidity_profile": liquidity_profile,
        "items": item_fingerprints,
    }
    return _hash_payload(payload)


def _batch_checksum(*, snapshot_date_value: date, replay_key_normalized: str, cluster_checksums: list[str]) -> str:
    return _hash_payload(
        {
            "snapshot_date": snapshot_date_value.isoformat(),
            "replay_key": replay_key_normalized,
            "cluster_checksums": sorted(cluster_checksums),
        }
    )


def _cluster_read_model(row: DuplicateCluster) -> DuplicateClusterRead:
    return DuplicateClusterRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        canonical_comic_issue_id=row.canonical_comic_issue_id,
        cluster_key=row.cluster_key,
        cluster_type=row.cluster_type,
        generation_batch_checksum=row.generation_batch_checksum,
        replay_key=row.replay_key,
        total_item_count=int(row.total_item_count),
        graded_item_count=int(row.graded_item_count),
        raw_item_count=int(row.raw_item_count),
        total_fmv_amount=row.total_fmv_amount,
        total_cost_basis_amount=row.total_cost_basis_amount,
        liquidity_profile=row.liquidity_profile,
        duplication_status=row.duplication_status,
        checksum=row.checksum,
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _reco_read_model(row: DuplicateConsolidationRecommendation) -> DuplicateConsolidationRecommendationRead:
    return DuplicateConsolidationRecommendationRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        duplicate_cluster_id=int(row.duplicate_cluster_id),
        generation_batch_checksum=row.generation_batch_checksum,
        recommendation_action=row.recommendation_action,
        rationale_summary=row.rationale_summary,
        expected_capital_reduction=row.expected_capital_reduction,
        estimated_liquidity_improvement=row.estimated_liquidity_improvement,
        estimated_portfolio_efficiency_gain=row.estimated_portfolio_efficiency_gain,
        confidence_level=row.confidence_level,
        recommendation_status=row.recommendation_status,
        checksum=row.checksum,
        snapshot_date=row.snapshot_date,
        replay_key=row.replay_key,
        created_at=row.created_at,
    )


def latest_batch_checksum(session: Session, *, owner_user_id: int) -> str | None:
    row = session.exec(
        select(DuplicateCluster.generation_batch_checksum)
        .where(DuplicateCluster.owner_user_id == owner_user_id)
        .order_by(col(DuplicateCluster.snapshot_date).desc(), col(DuplicateCluster.id).desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def generate_duplicate_clusters(
    session: Session, *, owner_user_id: int, payload: DuplicateClusterGeneratePayload
) -> DuplicateClusterGenerateResponse:
    snap_date = payload.snapshot_date or utc_today()
    rk = _norm_rk(payload.replay_key)

    snaps = _load_owner_snapshots(session, owner_user_id=owner_user_id)
    cluster_specs = _build_cluster_specs(snaps)
    inv_ids = sorted({s.inventory_item_id for s in snaps})
    liq_map = _latest_liquidity_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    reco_map = _latest_gr_reco_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    risk_map = _latest_risk_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    roi_map = _latest_roi_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    snap_by_id = {s.inventory_item_id: s for s in snaps}

    cluster_checksums: list[str] = []
    rows_to_insert: list[tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]] = []

    for spec in cluster_specs:
        members = [snap_by_id[i] for i in spec["inventory_item_ids"]]
        members = sorted(members, key=lambda m: m.inventory_item_id)
        strengths, liq_scores = _compute_strengths(
            members=members, liq_map=liq_map, reco_map=reco_map, risk_map=risk_map, roi_map=roi_map
        )

        inv_ids_row = [m.inventory_item_id for m in members]
        liq_vals = [int(liq_scores[i]) for i in inv_ids_row]
        profile = _liquidity_profile_for_scores(liq_vals)

        total_fmv = sum((m.current_fmv or ZERO) for m in members)
        total_cost = sum(m.acquisition_cost for m in members)
        ranked = sorted(members, key=lambda m: (-strengths[m.inventory_item_id], m.inventory_item_id))
        weak_half = ranked[len(ranked) // 2 :]
        weak_fmv = sum((m.current_fmv or ZERO) for m in weak_half)
        weak_ratio = None
        if total_fmv > ZERO:
            weak_ratio = (weak_fmv / total_fmv * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        dup_status = _duplication_status_rules(
            total_items=len(members), liquidity_profile=profile, weak_fmv_ratio=weak_ratio
        )

        g_ct = raw_ct = pipe_ct = 0
        for m in members:
            gs_label = _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline)
            if gs_label == "GRADED":
                g_ct += 1
            elif gs_label == "RAW":
                raw_ct += 1
            else:
                pipe_ct += 1

        priorities = _priority_for_inventory(
            members_sorted=members,
            strengths=strengths,
            duplication_status=dup_status,
        )

        fingerprints: list[dict[str, Any]] = []
        for m in sorted(members, key=lambda mm: mm.inventory_item_id):
            gs_label = _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline)
            fingerprints.append(
                {
                    "inventory_item_id": m.inventory_item_id,
                    "grading_status": gs_label,
                    "strength": str(strengths[m.inventory_item_id]),
                    "liquidity_score": str(liq_scores[m.inventory_item_id]),
                    "portfolio_ids": list(m.portfolio_ids),
                    "recommendation_priority": priorities[m.inventory_item_id],
                }
            )

        checksum = _cluster_row_checksum(
            cluster_type=str(spec["cluster_type"]),
            cluster_key=str(spec["cluster_key"]),
            inventory_item_ids=list(inv_ids_row),
            duplication_status=dup_status,
            liquidity_profile=profile,
            item_fingerprints=fingerprints,
        )
        cluster_checksums.append(checksum)

        row_payload = {
            "spec": spec,
            "profile": profile,
            "dup_status": dup_status,
            "checksum": checksum,
            "total_fmv": total_fmv,
            "total_cost": total_cost,
            "graded_ct": g_ct,
            # Non-slab grading footprint (includes pipeline rows for overlap intelligence).
            "raw_ct": int(raw_ct + pipe_ct),
        }
        rows_to_insert.append(
            (
                row_payload,
                [
                    {
                        "snap": m,
                        "gs": _classify_duplicate_grading(gs_norm=m.grade_normalized, in_pipeline=m.in_pipeline),
                        "prio": priorities[m.inventory_item_id],
                        "str": strengths[m.inventory_item_id],
                        "lq": liq_scores[m.inventory_item_id],
                    }
                    for m in sorted(members, key=lambda mm: mm.inventory_item_id)
                ],
                priorities,
            )
        )

    batch_checksum = _batch_checksum(
        snapshot_date_value=snap_date,
        replay_key_normalized=rk,
        cluster_checksums=sorted(cluster_checksums),
    )

    replay_probe = session.exec(
        select(DuplicateCluster)
        .where(
            DuplicateCluster.owner_user_id == owner_user_id,
            DuplicateCluster.snapshot_date == snap_date,
            DuplicateCluster.replay_key == rk,
            DuplicateCluster.generation_batch_checksum == batch_checksum,
        )
        .order_by(col(DuplicateCluster.id).asc())
    ).first()

    if replay_probe is not None:
        persisted = session.exec(
            select(DuplicateCluster)
            .where(
                DuplicateCluster.owner_user_id == owner_user_id,
                DuplicateCluster.snapshot_date == snap_date,
                DuplicateCluster.replay_key == rk,
                DuplicateCluster.generation_batch_checksum == batch_checksum,
            )
            .order_by(col(DuplicateCluster.cluster_type).asc(), col(DuplicateCluster.cluster_key).asc())
        ).all()

        reco_rows = []
        ids = [int(c.id or 0) for c in persisted]
        if ids:
            reco_rows = session.exec(
                select(DuplicateConsolidationRecommendation)
                .where(col(DuplicateConsolidationRecommendation.duplicate_cluster_id).in_(ids))
                .order_by(col(DuplicateConsolidationRecommendation.id).asc())
            ).all()

        return DuplicateClusterGenerateResponse(
            replayed=True,
            generation_batch_checksum=batch_checksum,
            snapshot_date=snap_date,
            snapshot_date_replay_source="explicit",
            clusters=[_cluster_read_model(c) for c in persisted],
            consolidation_recommendations=[_reco_read_model(r) for r in reco_rows],
            duplicate_history_snapshots_written=0,
        )

    session.execute(
        update(DuplicateConsolidationRecommendation)
        .where(
            DuplicateConsolidationRecommendation.owner_user_id == owner_user_id,
            DuplicateConsolidationRecommendation.recommendation_status == "ACTIVE",
        )
        .values(recommendation_status="SUPERSEDED")
    )
    session.flush()

    history_written = 0

    for row_payload, item_payloads, prio_map in rows_to_insert:
        spec = row_payload["spec"]
        dc = DuplicateCluster(
            owner_user_id=owner_user_id,
            canonical_comic_issue_id=spec["canonical_comic_issue_id"],
            cluster_key=str(spec["cluster_key"]),
            cluster_type=str(spec["cluster_type"]),
            generation_batch_checksum=batch_checksum,
            replay_key=rk,
            total_item_count=len(item_payloads),
            graded_item_count=int(row_payload["graded_ct"]),
            raw_item_count=int(row_payload["raw_ct"]),
            total_fmv_amount=row_payload["total_fmv"] if row_payload["total_fmv"] > ZERO else None,
            total_cost_basis_amount=row_payload["total_cost"] if row_payload["total_cost"] > ZERO else None,
            liquidity_profile=str(row_payload["profile"]),
            duplication_status=str(row_payload["dup_status"]),
            checksum=str(row_payload["checksum"]),
            snapshot_date=snap_date,
        )
        session.add(dc)
        session.flush()

        strengths_map = {
            payload["snap"].inventory_item_id: payload["str"] for payload in item_payloads
        }
        action, rationale, confidence, cap_red, liq_imp, gain = _consolidate_action_and_rationale(
            cluster_type=str(spec["cluster_type"]),
            duplication_status=str(row_payload["dup_status"]),
            members=[payload["snap"] for payload in item_payloads],
            strengths=strengths_map,
            priorities=prio_map,
        )

        reco_payload = {
            "owner_user_id": owner_user_id,
            "duplicate_cluster_id": int(dc.id or 0),
            "generation_batch_checksum": batch_checksum,
            "recommendation_action": action,
            "rationale_summary": rationale,
            "expected_capital_reduction": cap_red if cap_red and cap_red > ZERO else None,
            "estimated_liquidity_improvement": liq_imp,
            "estimated_portfolio_efficiency_gain": gain,
            "confidence_level": confidence,
            "recommendation_status": "ACTIVE",
            "snapshot_date": snap_date,
            "replay_key": rk,
            "checksum": _hash_payload(
                {
                    "cluster_checksum": dc.checksum,
                    "action": action,
                    "rationale": rationale,
                    "capital": _json_safe(cap_red),
                }
            ),
        }

        reco = DuplicateConsolidationRecommendation(**reco_payload)
        session.add(reco)

        hist = DuplicateHistorySnapshot(
            owner_user_id=owner_user_id,
            cluster_key=str(spec["cluster_key"]),
            cluster_type=str(spec["cluster_type"]),
            total_item_count=len(item_payloads),
            total_fmv_amount=dc.total_fmv_amount,
            duplication_status=str(row_payload["dup_status"]),
            checksum=str(row_payload["checksum"]),
            generation_batch_checksum=batch_checksum,
            snapshot_date=snap_date,
            replay_key=rk,
        )
        session.add(hist)
        history_written += 1

        for payload in sorted(item_payloads, key=lambda p: p["snap"].inventory_item_id):
            m = payload["snap"]
            best_pf = int(m.portfolio_ids[0]) if m.portfolio_ids else None
            dci = DuplicateClusterItem(
                duplicate_cluster_id=int(dc.id or 0),
                inventory_item_id=m.inventory_item_id,
                portfolio_id=best_pf,
                grading_status=str(payload["gs"]),
                estimated_strength_score=payload["str"],
                liquidity_score=payload["lq"],
                current_fmv=m.current_fmv,
                acquisition_cost=m.acquisition_cost,
                recommendation_priority=str(payload["prio"]),
            )
            session.add(dci)

    session.commit()

    persisted = session.exec(
        select(DuplicateCluster)
        .where(
            DuplicateCluster.owner_user_id == owner_user_id,
            DuplicateCluster.snapshot_date == snap_date,
            DuplicateCluster.replay_key == rk,
            DuplicateCluster.generation_batch_checksum == batch_checksum,
        )
        .order_by(col(DuplicateCluster.cluster_type).asc(), col(DuplicateCluster.cluster_key).asc())
    ).all()

    reco_rows = []
    ids = [int(c.id or 0) for c in persisted]
    if ids:
        reco_rows = session.exec(
            select(DuplicateConsolidationRecommendation)
            .where(col(DuplicateConsolidationRecommendation.duplicate_cluster_id).in_(ids))
            .order_by(col(DuplicateConsolidationRecommendation.id).asc())
        ).all()

    return DuplicateClusterGenerateResponse(
        replayed=False,
        generation_batch_checksum=batch_checksum,
        snapshot_date=snap_date,
        snapshot_date_replay_source=None,
        clusters=[_cluster_read_model(c) for c in persisted],
        consolidation_recommendations=[_reco_read_model(r) for r in reco_rows],
        duplicate_history_snapshots_written=history_written,
    )


def list_clusters_owner(
    session: Session,
    *,
    owner_user_id: int,
    canonical_comic_issue_id: int | None,
    cluster_type: str | None,
    duplication_status: str | None,
    liquidity_profile: str | None,
    recommendation_action: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DuplicateClusterListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    cid_filter = None
    if recommendation_action:
        reco_rows = session.exec(
            select(DuplicateConsolidationRecommendation.duplicate_cluster_id).where(
                DuplicateConsolidationRecommendation.owner_user_id == owner_user_id,
                DuplicateConsolidationRecommendation.recommendation_action == recommendation_action.upper(),
            )
        ).all()
        cid_filter = {int(row[0]) for row in reco_rows if row[0]}
        if not cid_filter:
            return DuplicateClusterListResponse(generation_batch_checksum=None, snapshot_date=None, items=[])

    if latest_only:
        checksum = latest_batch_checksum(session, owner_user_id=owner_user_id)
        if checksum is None:
            return DuplicateClusterListResponse(items=[], generation_batch_checksum=None, snapshot_date=None)
        meta = session.exec(
            select(DuplicateCluster.snapshot_date)
            .where(DuplicateCluster.owner_user_id == owner_user_id, DuplicateCluster.generation_batch_checksum == checksum)
            .order_by(col(DuplicateCluster.id).asc())
            .limit(1)
        ).first()
        sd = meta[0] if meta else utc_today()
        latest_rows = session.exec(
            select(DuplicateCluster)
            .where(
                DuplicateCluster.owner_user_id == owner_user_id,
                DuplicateCluster.generation_batch_checksum == checksum,
                *((
                    DuplicateCluster.canonical_comic_issue_id == canonical_comic_issue_id,
                    )
                    if canonical_comic_issue_id is not None
                    else (),
                ),
                *((DuplicateCluster.cluster_type == cluster_type,) if cluster_type else ()),
                *((DuplicateCluster.duplication_status == duplication_status.upper(),) if duplication_status else ()),
                *((DuplicateCluster.liquidity_profile == liquidity_profile.upper(),) if liquidity_profile else ()),
                *((col(DuplicateCluster.id).in_(sorted(cid_filter)),) if cid_filter is not None else ()),
                *((DuplicateCluster.snapshot_date >= snapshot_date_from,) if snapshot_date_from else ()),
                *((DuplicateCluster.snapshot_date <= snapshot_date_to,) if snapshot_date_to else ()),
            )
            .order_by(col(DuplicateCluster.cluster_type).asc(), col(DuplicateCluster.cluster_key).asc())
            .offset(ofs)
            .limit(lm)
        ).all()
        reads = [_cluster_read_model(row) for row in latest_rows]
        return DuplicateClusterListResponse(generation_batch_checksum=checksum, snapshot_date=sd, items=reads)

    stmt = select(DuplicateCluster).where(DuplicateCluster.owner_user_id == owner_user_id)
    if canonical_comic_issue_id is not None:
        stmt = stmt.where(DuplicateCluster.canonical_comic_issue_id == canonical_comic_issue_id)
    if cluster_type:
        stmt = stmt.where(DuplicateCluster.cluster_type == cluster_type)
    if duplication_status:
        stmt = stmt.where(DuplicateCluster.duplication_status == duplication_status.upper())
    if liquidity_profile:
        stmt = stmt.where(DuplicateCluster.liquidity_profile == liquidity_profile.upper())
    if snapshot_date_from:
        stmt = stmt.where(DuplicateCluster.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateCluster.snapshot_date <= snapshot_date_to)
    if cid_filter is not None:
        stmt = stmt.where(col(DuplicateCluster.id).in_(sorted(cid_filter)))

    rows = session.exec(stmt.order_by(col(DuplicateCluster.snapshot_date).desc(), col(DuplicateCluster.id).desc()).offset(ofs).limit(lm)).all()

    chk = rows[0].generation_batch_checksum if rows else latest_batch_checksum(session, owner_user_id=owner_user_id)
    sd0 = rows[0].snapshot_date if rows else None
    return DuplicateClusterListResponse(
        generation_batch_checksum=chk,
        snapshot_date=sd0,
        items=[_cluster_read_model(r) for r in rows],
    )


def list_clusters_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    canonical_comic_issue_id: int | None,
    cluster_type: str | None,
    duplication_status: str | None,
    liquidity_profile: str | None,
    recommendation_action: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DuplicateClusterListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    cid_filter = None
    if recommendation_action:
        reco_stmt = select(DuplicateConsolidationRecommendation.duplicate_cluster_id).where(
            DuplicateConsolidationRecommendation.recommendation_action == recommendation_action.upper()
        )
        if owner_user_id is not None:
            reco_stmt = reco_stmt.where(DuplicateConsolidationRecommendation.owner_user_id == owner_user_id)
        reco_rows = session.exec(reco_stmt).all()
        cid_filter = {int(row[0]) for row in reco_rows if row[0]}
        if not cid_filter:
            return DuplicateClusterListResponse()

    stmt = select(DuplicateCluster)
    if owner_user_id is not None:
        stmt = stmt.where(DuplicateCluster.owner_user_id == owner_user_id)
    if canonical_comic_issue_id is not None:
        stmt = stmt.where(DuplicateCluster.canonical_comic_issue_id == canonical_comic_issue_id)
    if cluster_type:
        stmt = stmt.where(DuplicateCluster.cluster_type == cluster_type)
    if duplication_status:
        stmt = stmt.where(DuplicateCluster.duplication_status == duplication_status.upper())
    if liquidity_profile:
        stmt = stmt.where(DuplicateCluster.liquidity_profile == liquidity_profile.upper())
    if snapshot_date_from:
        stmt = stmt.where(DuplicateCluster.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateCluster.snapshot_date <= snapshot_date_to)

    stmt = stmt.order_by(col(DuplicateCluster.snapshot_date).desc(), col(DuplicateCluster.cluster_type).asc(), col(DuplicateCluster.id).desc())

    if latest_only:
        tgt_owner = owner_user_id
        if tgt_owner is None:
            agg = session.exec(
                select(
                    DuplicateCluster.owner_user_id,
                    DuplicateCluster.generation_batch_checksum,
                    DuplicateCluster.snapshot_date,
                )
                .group_by(DuplicateCluster.owner_user_id, DuplicateCluster.generation_batch_checksum)
                .order_by(col(DuplicateCluster.snapshot_date).desc())
            ).first()
            if not agg:
                return DuplicateClusterListResponse()
            stmt = stmt.where(
                DuplicateCluster.owner_user_id == int(agg[0]),
                DuplicateCluster.generation_batch_checksum == agg[1],
                DuplicateCluster.snapshot_date == agg[2],
            )
        else:
            chk = latest_batch_checksum(session, owner_user_id=int(tgt_owner))
            if not chk:
                return DuplicateClusterListResponse()
            stmt = stmt.where(DuplicateCluster.owner_user_id == tgt_owner, DuplicateCluster.generation_batch_checksum == chk)

    if cid_filter is not None:
        stmt = stmt.where(col(DuplicateCluster.id).in_(sorted(cid_filter)))

    rows = session.exec(stmt.offset(ofs).limit(lm)).all()
    chk = rows[0].generation_batch_checksum if rows else None
    sd = rows[0].snapshot_date if rows else None
    return DuplicateClusterListResponse(generation_batch_checksum=chk, snapshot_date=sd, items=[_cluster_read_model(r) for r in rows])


def get_cluster_owner(session: Session, *, owner_user_id: int, cluster_id: int) -> DuplicateClusterRead:
    row = session.exec(
        select(DuplicateCluster).where(DuplicateCluster.id == cluster_id, DuplicateCluster.owner_user_id == owner_user_id).limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="duplicate cluster missing")
    return _cluster_read_model(row)


def get_cluster_ops(session: Session, *, owner_user_id: int | None, cluster_id: int) -> DuplicateClusterRead:
    stmt = select(DuplicateCluster).where(DuplicateCluster.id == cluster_id)
    if owner_user_id is not None:
        stmt = stmt.where(DuplicateCluster.owner_user_id == owner_user_id)
    row = session.exec(stmt.limit(1)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="duplicate cluster missing")
    return _cluster_read_model(row)


def _item_read(row: DuplicateClusterItem) -> DuplicateClusterItemRead:
    return DuplicateClusterItemRead(
        id=int(row.id or 0),
        duplicate_cluster_id=int(row.duplicate_cluster_id),
        inventory_item_id=int(row.inventory_item_id),
        portfolio_id=row.portfolio_id,
        grading_status=str(row.grading_status),
        estimated_strength_score=row.estimated_strength_score,
        liquidity_score=row.liquidity_score,
        current_fmv=row.current_fmv,
        acquisition_cost=row.acquisition_cost,
        recommendation_priority=str(row.recommendation_priority),
        created_at=row.created_at,
    )


def list_cluster_items_owner(
    session: Session,
    *,
    owner_user_id: int,
    duplicate_cluster_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    inventory_item_id: int | None,
    limit: int,
    offset: int,
) -> DuplicateClusterItemListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)

    joins = DuplicateClusterItem.duplicate_cluster_id == DuplicateCluster.id
    stmt = select(DuplicateClusterItem).join(DuplicateCluster, joins).where(DuplicateCluster.owner_user_id == owner_user_id)

    if duplicate_cluster_id is not None:
        stmt = stmt.where(DuplicateClusterItem.duplicate_cluster_id == duplicate_cluster_id)
    if inventory_item_id is not None:
        stmt = stmt.where(DuplicateClusterItem.inventory_item_id == inventory_item_id)
    if snapshot_date_from:
        stmt = stmt.where(DuplicateCluster.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateCluster.snapshot_date <= snapshot_date_to)
    if latest_only:
        chk = latest_batch_checksum(session, owner_user_id=owner_user_id)
        if chk is None:
            return DuplicateClusterItemListResponse()
        stmt = stmt.where(DuplicateCluster.generation_batch_checksum == chk)

    rows = session.exec(
        stmt.order_by(col(DuplicateCluster.snapshot_date).desc(), col(DuplicateCluster.id).desc(), col(DuplicateClusterItem.inventory_item_id).asc())
        .offset(ofs)
        .limit(lm)
    ).all()
    return DuplicateClusterItemListResponse(items=[_item_read(r) for r in rows])


def list_cluster_items_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    duplicate_cluster_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    inventory_item_id: int | None,
    limit: int,
    offset: int,
) -> DuplicateClusterItemListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    stmt = select(DuplicateClusterItem).join(DuplicateCluster, DuplicateClusterItem.duplicate_cluster_id == DuplicateCluster.id)
    if owner_user_id is not None:
        stmt = stmt.where(DuplicateCluster.owner_user_id == owner_user_id)
    if duplicate_cluster_id is not None:
        stmt = stmt.where(DuplicateClusterItem.duplicate_cluster_id == duplicate_cluster_id)
    if inventory_item_id is not None:
        stmt = stmt.where(DuplicateClusterItem.inventory_item_id == inventory_item_id)
    if snapshot_date_from:
        stmt = stmt.where(DuplicateCluster.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateCluster.snapshot_date <= snapshot_date_to)

    stmt = stmt.order_by(
        col(DuplicateCluster.snapshot_date).desc(),
        col(DuplicateCluster.id).desc(),
        col(DuplicateClusterItem.inventory_item_id).asc(),
    )

    if latest_only and owner_user_id is not None:
        chk = latest_batch_checksum(session, owner_user_id=int(owner_user_id))
        if chk is None:
            return DuplicateClusterItemListResponse()
        stmt = stmt.where(DuplicateCluster.generation_batch_checksum == chk)

    rows = session.exec(stmt.offset(ofs).limit(lm)).all()
    return DuplicateClusterItemListResponse(items=[_item_read(r) for r in rows])


def list_consolidation_recommendations_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_action: str | None,
    recommendation_status: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DuplicateConsolidationRecommendationListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    stmt = select(DuplicateConsolidationRecommendation).where(DuplicateConsolidationRecommendation.owner_user_id == owner_user_id)
    if recommendation_action:
        stmt = stmt.where(DuplicateConsolidationRecommendation.recommendation_action == recommendation_action.upper())
    if recommendation_status:
        stmt = stmt.where(DuplicateConsolidationRecommendation.recommendation_status == recommendation_status.upper())
    if snapshot_date_from:
        stmt = stmt.where(DuplicateConsolidationRecommendation.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateConsolidationRecommendation.snapshot_date <= snapshot_date_to)
    if latest_only:
        chk = latest_batch_checksum(session, owner_user_id=owner_user_id)
        if chk is None:
            return DuplicateConsolidationRecommendationListResponse()
        cid_list = sorted(
            {
                int(cid)
                for cid in session.exec(
                    select(DuplicateCluster.id).where(
                        DuplicateCluster.owner_user_id == owner_user_id,
                        DuplicateCluster.generation_batch_checksum == chk,
                    )
                ).all()
            }
        )
        if cid_list:
            stmt = stmt.where(col(DuplicateConsolidationRecommendation.duplicate_cluster_id).in_(cid_list))

    rows = session.exec(
        stmt.order_by(
            col(DuplicateConsolidationRecommendation.snapshot_date).desc(),
            col(DuplicateConsolidationRecommendation.id).desc(),
        )
        .offset(ofs)
        .limit(lm)
    ).all()
    return DuplicateConsolidationRecommendationListResponse(items=[_reco_read_model(r) for r in rows])


def list_consolidation_recommendations_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    recommendation_action: str | None,
    recommendation_status: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DuplicateConsolidationRecommendationListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    stmt = select(DuplicateConsolidationRecommendation)
    if owner_user_id is not None:
        stmt = stmt.where(DuplicateConsolidationRecommendation.owner_user_id == owner_user_id)
    if recommendation_action:
        stmt = stmt.where(DuplicateConsolidationRecommendation.recommendation_action == recommendation_action.upper())
    if recommendation_status:
        stmt = stmt.where(DuplicateConsolidationRecommendation.recommendation_status == recommendation_status.upper())
    if snapshot_date_from:
        stmt = stmt.where(DuplicateConsolidationRecommendation.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateConsolidationRecommendation.snapshot_date <= snapshot_date_to)
    if latest_only and owner_user_id is not None:
        chk = latest_batch_checksum(session, owner_user_id=int(owner_user_id))
        if chk is None:
            return DuplicateConsolidationRecommendationListResponse()
        cid_list = sorted(
            {
                int(cid)
                for cid in session.exec(
                    select(DuplicateCluster.id).where(
                        DuplicateCluster.owner_user_id == int(owner_user_id),
                        DuplicateCluster.generation_batch_checksum == chk,
                    )
                ).all()
            }
        )
        if cid_list:
            stmt = stmt.where(col(DuplicateConsolidationRecommendation.duplicate_cluster_id).in_(cid_list))

    rows = session.exec(
        stmt.order_by(
            col(DuplicateConsolidationRecommendation.snapshot_date).desc(),
            col(DuplicateConsolidationRecommendation.id).desc(),
        )
        .offset(ofs)
        .limit(lm)
    ).all()
    return DuplicateConsolidationRecommendationListResponse(items=[_reco_read_model(r) for r in rows])


def _hist_read(row: DuplicateHistorySnapshot) -> DuplicateHistorySnapshotRead:
    return DuplicateHistorySnapshotRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        cluster_key=str(row.cluster_key),
        cluster_type=str(row.cluster_type),
        total_item_count=int(row.total_item_count),
        total_fmv_amount=row.total_fmv_amount,
        duplication_status=str(row.duplication_status),
        checksum=str(row.checksum),
        generation_batch_checksum=str(row.generation_batch_checksum),
        snapshot_date=row.snapshot_date,
        replay_key=str(row.replay_key),
        created_at=row.created_at,
    )


def list_duplicate_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    cluster_key_prefix: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DuplicateHistoryListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    stmt = select(DuplicateHistorySnapshot).where(DuplicateHistorySnapshot.owner_user_id == owner_user_id)
    if cluster_key_prefix:
        stmt = stmt.where(col(DuplicateHistorySnapshot.cluster_key).startswith(cluster_key_prefix))
    if snapshot_date_from:
        stmt = stmt.where(DuplicateHistorySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateHistorySnapshot.snapshot_date <= snapshot_date_to)
    if latest_only:
        chk = latest_batch_checksum(session, owner_user_id=owner_user_id)
        if chk is None:
            return DuplicateHistoryListResponse()
        stmt = stmt.where(DuplicateHistorySnapshot.generation_batch_checksum == chk)

    rows = session.exec(
        stmt.order_by(col(DuplicateHistorySnapshot.snapshot_date).desc(), col(DuplicateHistorySnapshot.id).desc())
        .offset(ofs)
        .limit(lm)
    ).all()
    return DuplicateHistoryListResponse(items=[_hist_read(r) for r in rows])


def list_duplicate_history_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    cluster_key_prefix: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DuplicateHistoryListResponse:
    lm, ofs = clamp_pagination(limit=limit, offset=offset)
    stmt = select(DuplicateHistorySnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(DuplicateHistorySnapshot.owner_user_id == owner_user_id)
    if cluster_key_prefix:
        stmt = stmt.where(col(DuplicateHistorySnapshot.cluster_key).startswith(cluster_key_prefix))
    if snapshot_date_from:
        stmt = stmt.where(DuplicateHistorySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to:
        stmt = stmt.where(DuplicateHistorySnapshot.snapshot_date <= snapshot_date_to)
    if latest_only and owner_user_id is not None:
        chk = latest_batch_checksum(session, owner_user_id=int(owner_user_id))
        if chk is None:
            return DuplicateHistoryListResponse()
        stmt = stmt.where(DuplicateHistorySnapshot.generation_batch_checksum == chk)

    rows = session.exec(
        stmt.order_by(col(DuplicateHistorySnapshot.snapshot_date).desc(), col(DuplicateHistorySnapshot.id).desc())
        .offset(ofs)
        .limit(lm)
    ).all()
    return DuplicateHistoryListResponse(items=[_hist_read(r) for r in rows])


def duplicate_intelligence_summary(session: Session, *, owner_user_id: int) -> DuplicateIntelligenceSummary:
    chk = latest_batch_checksum(session, owner_user_id=owner_user_id)
    if chk is None:
        return DuplicateIntelligenceSummary()

    clusters = session.exec(
        select(DuplicateCluster).where(DuplicateCluster.owner_user_id == owner_user_id, DuplicateCluster.generation_batch_checksum == chk)
    ).all()
    if not clusters:
        return DuplicateIntelligenceSummary(generation_batch_checksum=chk)

    sd = clusters[0].snapshot_date

    graded_overlap_ct = sum(1 for c in clusters if str(c.cluster_type) == "graded_overlap")
    raw_graded_ct = sum(1 for c in clusters if str(c.cluster_type) == "raw_graded_overlap")

    graded_units = sum(int(c.graded_item_count or 0) for c in clusters)
    raw_units = sum(int(c.raw_item_count or 0) for c in clusters)

    overexposed = sum(1 for c in clusters if str(c.duplication_status) == "OVEREXPOSED")

    tail_items = session.exec(
        select(DuplicateClusterItem)
        .join(DuplicateCluster, DuplicateClusterItem.duplicate_cluster_id == DuplicateCluster.id)
        .where(
            DuplicateCluster.owner_user_id == owner_user_id,
            DuplicateCluster.generation_batch_checksum == chk,
            col(DuplicateClusterItem.recommendation_priority).in_(("CONSOLIDATE", "SELL_CANDIDATE")),
        )
    ).all()
    redundant_capital = sum(_money(r.acquisition_cost) for r in tail_items if r.acquisition_cost is not None)

    status_rank = {"OVEREXPOSED": 0, "REDUNDANT": 1, "WATCH": 2, "HEALTHY": 3}

    opps: list[DuplicateOpportunityBrief] = []
    for c in sorted(
        clusters,
        key=lambda row: (status_rank.get(str(row.duplication_status), 9), -(row.total_cost_basis_amount or ZERO), str(row.cluster_key)),
    )[:5]:
        opps.append(
            DuplicateOpportunityBrief(
                cluster_id=int(c.id or 0),
                cluster_key=str(c.cluster_key),
                cluster_type=str(c.cluster_type),
                duplication_status=str(c.duplication_status),
                total_cost_basis_amount=c.total_cost_basis_amount,
                graded_item_count=int(c.graded_item_count),
                raw_item_count=int(c.raw_item_count),
            )
        )

    return DuplicateIntelligenceSummary(
        generation_batch_checksum=chk,
        snapshot_date=sd,
        cluster_count=len(clusters),
        overexposed_cluster_count=overexposed,
        redundant_capital_amount=redundant_capital if redundant_capital > ZERO else None,
        graded_overlap_cluster_count=graded_overlap_ct,
        raw_graded_overlap_cluster_count=raw_graded_ct,
        graded_duplicate_units=graded_units,
        raw_duplicate_units=raw_units,
        strongest_opportunities=opps,
    )


def inventory_duplicate_teaser(session: Session, *, owner_user_id: int, inventory_item_id: int) -> InventoryDuplicateIntelligenceTeaser | None:
    chk = latest_batch_checksum(session, owner_user_id=owner_user_id)
    if chk is None:
        return None

    links = session.exec(
        select(DuplicateClusterItem, DuplicateCluster, DuplicateConsolidationRecommendation)
        .join(DuplicateCluster, DuplicateClusterItem.duplicate_cluster_id == DuplicateCluster.id)
        .outerjoin(
            DuplicateConsolidationRecommendation,
            DuplicateConsolidationRecommendation.duplicate_cluster_id == DuplicateCluster.id,
        )
        .where(
            DuplicateCluster.owner_user_id == owner_user_id,
            DuplicateCluster.generation_batch_checksum == chk,
            DuplicateClusterItem.inventory_item_id == inventory_item_id,
        )
    ).all()
    if not links:
        return None

    cluster_types: set[str] = set()
    worst = "HEALTHY"
    order_w = {"HEALTHY": 0, "WATCH": 1, "REDUNDANT": 2, "OVEREXPOSED": 3}
    primary_action: str | None = None
    rationale: str | None = None
    strengths: dict[int, Decimal] = {}

    for dci, dc, reco in links:
        cluster_types.add(str(dc.cluster_type))
        ds = str(dc.duplication_status)
        if order_w.get(ds, 0) > order_w.get(worst, 0):
            worst = ds
        if reco and reco.recommendation_status == "ACTIVE":
            primary_action = str(reco.recommendation_action)
            rationale = str(reco.rationale_summary)[:220]
        sid = int(dci.inventory_item_id)
        if dci.estimated_strength_score is not None:
            strengths[sid] = _money(dci.estimated_strength_score)

    best_by_cluster: dict[int, int] = {}
    for dci, dc, _reco in links:
        cid = int(dc.id or 0)
        sc = _money(dci.estimated_strength_score) if dci.estimated_strength_score is not None else ZERO
        cur = best_by_cluster.get(cid)
        if cur is None:
            best_by_cluster[cid] = int(dci.inventory_item_id)
        else:
            prev_sc = strengths.get(cur, ZERO)
            if sc > prev_sc or (sc == prev_sc and int(dci.inventory_item_id) < cur):
                best_by_cluster[cid] = int(dci.inventory_item_id)

    is_strongest = len(best_by_cluster) > 0 and all(best_by_cluster[c] == inventory_item_id for c in best_by_cluster)

    return InventoryDuplicateIntelligenceTeaser(
        generation_batch_checksum=chk,
        cluster_types_present=sorted(cluster_types),
        worst_duplication_status=worst,
        is_strongest_copy_in_clusters=is_strongest,
        primary_consolidation_action=primary_action,
        consolidation_teaser=rationale,
    )
