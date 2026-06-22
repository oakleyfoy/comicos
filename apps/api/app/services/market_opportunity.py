"""P39-05 deterministic market acquisition opportunity snapshots (aggregation only)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.models import (
    InventoryCopy,
    MarketAcquisitionOpportunityEvidence,
    MarketAcquisitionOpportunityHistory,
    MarketAcquisitionOpportunityItem,
    MarketAcquisitionOpportunitySnapshot,
    MarketAcquisitionScore,
    MarketAcquisitionScoreSnapshot,
    MarketAcquisitionSignal,
    MarketAcquisitionSignalSnapshot,
    PortfolioLiquiditySnapshot,
)
from app.services.market_feed import append_market_feed_event
from app.schemas.market_opportunity import (
    InventoryMarketAcquisitionOpportunityTeaser,
    MarketAcquisitionOpportunityDetailRead,
    MarketAcquisitionOpportunityEvidenceListResponse,
    MarketAcquisitionOpportunityEvidenceRead,
    MarketAcquisitionOpportunityGeneratePayload,
    MarketAcquisitionOpportunityGenerateResponse,
    MarketAcquisitionOpportunityHistoryListResponse,
    MarketAcquisitionOpportunityHistoryRead,
    MarketAcquisitionOpportunityItemListResponse,
    MarketAcquisitionOpportunityItemRead,
    MarketAcquisitionOpportunitySnapshotListResponse,
    MarketAcquisitionOpportunitySnapshotRead,
)

ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")
PCT_QUANT = Decimal("0.0001")
WGHT_QUANT = Decimal("0.000001")

STRENGTH_ORDER = {"ELITE": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
TYPE_PRIORITY = {
    "HIGH_RISK_ASSET": 0,
    "REDUNDANT_ASSET": 1,
    "VALUE_DISLOCATION": 2,
    "PORTFOLIO_GAP_FILL": 3,
    "CONCENTRATION_REDUCTION": 4,
    "LIQUIDITY_OPPORTUNITY": 5,
    "GRADING_UPSIDE": 6,
}

STRENGTH_SCORE_MAP = {
    "ELITE": Decimal("100"),
    "HIGH": Decimal("75"),
    "MEDIUM": Decimal("50"),
    "LOW": Decimal("25"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _money(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _score_or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
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


def _bucket_to_numeric(bucket: str) -> Decimal:
    u = bucket.strip().upper()
    if u == "LOW":
        return Decimal("33")
    if u == "MEDIUM":
        return Decimal("66")
    if u == "HIGH":
        return Decimal("100")
    return Decimal("50")


def _signal_sort_key(row: MarketAcquisitionSignal) -> tuple[int, int, int]:
    return (
        int(TYPE_PRIORITY.get(str(row.signal_type), 99)),
        int(STRENGTH_ORDER.get(str(row.signal_strength), 99)),
        int(row.id or 0),
    )


def _raw_contribution(signal_type: str, signal_strength: str) -> int:
    t_rank = int(TYPE_PRIORITY.get(signal_type, 99))
    s_rank = int(STRENGTH_ORDER.get(signal_strength, 3))
    type_factor = max(1, 8 - min(t_rank, 7))
    strength_factor = max(1, 4 - s_rank)
    return type_factor * strength_factor


def _normalize_contribution_weights(raws: list[int]) -> list[Decimal]:
    n = len(raws)
    if n == 0:
        return []
    total = sum(raws)
    micro = 1_000_000
    if total <= 0:
        eq = micro // n
        rem = micro - eq * n
        return [
            (Decimal(eq + (1 if i < rem else 0)) / Decimal(micro)).quantize(
                WGHT_QUANT, rounding=ROUND_HALF_UP
            )
            for i in range(n)
        ]

    allocated = 0
    out: list[Decimal] = []
    for idx, raw in enumerate(raws):
        if idx == n - 1:
            mic = micro - allocated
        else:
            mic = (raw * micro) // total
            allocated += mic
        out.append((Decimal(mic) / Decimal(micro)).quantize(WGHT_QUANT, rounding=ROUND_HALF_UP))
    return out


def _quantize_pct(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def classify_opportunity_portfolio_view(
    *,
    total_signals: int,
    value_dislocation_count: int,
    grading_upside_count: int,
    liquidity_opportunity_count: int,
    portfolio_gap_fill_count: int,
    concentration_reduction_count: int,
    redundant_asset_count: int,
    high_risk_asset_count: int,
    avg_acquisition_score: Decimal | None,
) -> str:
    if total_signals <= 0:
        return "LOW_OPPORTUNITY"
    avg_rank = avg_acquisition_score if avg_acquisition_score is not None else ZERO

    elite_drivers = value_dislocation_count + grading_upside_count
    if elite_drivers >= 3 and avg_rank >= Decimal("70"):
        return "ELITE_OPPORTUNITY"

    risk_stack = redundant_asset_count + high_risk_asset_count
    if risk_stack >= max(3, (total_signals + 1) // 2):
        return "LOW_OPPORTUNITY"

    diversify_core = (
        liquidity_opportunity_count >= 2
        and portfolio_gap_fill_count + concentration_reduction_count >= 4
    )
    balanced = (
        liquidity_opportunity_count >= 1
        and portfolio_gap_fill_count + concentration_reduction_count >= 2
    )
    if diversify_core or balanced:
        return "STRONG_OPPORTUNITY"

    if avg_rank < Decimal("45") and risk_stack >= 2:
        return "LOW_OPPORTUNITY"

    mixed_driver = elite_drivers >= 1 or liquidity_opportunity_count >= 1
    return "MODERATE_OPPORTUNITY" if mixed_driver else "LOW_OPPORTUNITY"


def _portfolio_impacts(
    signals: list[MarketAcquisitionSignal],
    scores_by_id: dict[int, MarketAcquisitionScore],
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    pg = sum(1 for s in signals if s.signal_type == "PORTFOLIO_GAP_FILL")
    cov = min(HUNDRED, Decimal(pg) * Decimal("12.5000"))

    liq_sum = ZERO
    for s in signals:
        if str(s.signal_type) != "LIQUIDITY_OPPORTUNITY":
            continue
        sc = scores_by_id.get(int(s.scored_candidate_id or 0))
        if sc is None:
            continue
        liq_sum += _score_or_zero(_money(sc.liquidity_score))

    liquidity_gain = min(
        HUNDRED,
        liq_sum * Decimal("0.3500")
        + Decimal(sum(1 for s in signals if s.signal_type == "LIQUIDITY_OPPORTUNITY"))
        * Decimal("2.2500"),
    )

    conc_scores: list[Decimal] = []
    for s in signals:
        if str(s.signal_type) not in {"CONCENTRATION_REDUCTION", "PORTFOLIO_GAP_FILL"}:
            continue
        sc = scores_by_id.get(int(s.scored_candidate_id or 0))
        if sc is None:
            continue
        conc_scores.append(_score_or_zero(_money(sc.concentration_reduction_score)))

    conc_avg = ZERO
    if conc_scores:
        conc_avg = (sum(conc_scores) / Decimal(len(conc_scores))).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    cr_ct = sum(1 for s in signals if s.signal_type == "CONCENTRATION_REDUCTION")
    diversify = min(
        HUNDRED,
        Decimal(cr_ct) * Decimal("9.2500")
        + Decimal(pg) * Decimal("7.1000")
        + conc_avg * Decimal("0.1200"),
    )

    risky_penalties: list[Decimal] = []
    risky_ct = 0
    for s in signals:
        if str(s.signal_type) != "HIGH_RISK_ASSET":
            continue
        risky_ct += 1
        sc = scores_by_id.get(int(s.scored_candidate_id or 0))
        if sc is None:
            continue
        risky_penalties.append(_score_or_zero(_money(sc.risk_penalty_score)))

    pen_avg = ZERO
    if risky_penalties:
        pen_avg = (sum(risky_penalties) / Decimal(len(risky_penalties))).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    risk_adjust = (
        Decimal("-1.0000")
        * (Decimal(str(risky_ct)) * Decimal("7.5000") + pen_avg * Decimal("0.1800"))
    ).quantize(
        Decimal("0.0100"),
        rounding=ROUND_HALF_UP,
    )
    return (
        cov.quantize(Decimal("0.0100"), rounding=ROUND_HALF_UP),
        liquidity_gain.quantize(Decimal("0.0100"), rounding=ROUND_HALF_UP),
        diversify.quantize(Decimal("0.0100"), rounding=ROUND_HALF_UP),
        risk_adjust,
    )


def _snapshot_read(
    row: MarketAcquisitionOpportunitySnapshot,
) -> MarketAcquisitionOpportunitySnapshotRead:
    return MarketAcquisitionOpportunitySnapshotRead.model_validate(row, from_attributes=True)


def _item_read(row: MarketAcquisitionOpportunityItem) -> MarketAcquisitionOpportunityItemRead:
    return MarketAcquisitionOpportunityItemRead.model_validate(row, from_attributes=True)


def _history_read(
    row: MarketAcquisitionOpportunityHistory,
) -> MarketAcquisitionOpportunityHistoryRead:
    return MarketAcquisitionOpportunityHistoryRead.model_validate(row, from_attributes=True)


def _evidence_read(
    row: MarketAcquisitionOpportunityEvidence,
) -> MarketAcquisitionOpportunityEvidenceRead:
    return MarketAcquisitionOpportunityEvidenceRead.model_validate(row, from_attributes=True)


def _load_owner_signal_snapshot_or_404(
    session: Session,
    *,
    owner_user_id: int,
    signal_snapshot_id: int | None,
    snapshot_date: date | None,
) -> MarketAcquisitionSignalSnapshot:
    stmt = select(MarketAcquisitionSignalSnapshot).where(
        MarketAcquisitionSignalSnapshot.owner_user_id == owner_user_id
    )
    if signal_snapshot_id is not None:
        row = session.get(MarketAcquisitionSignalSnapshot, signal_snapshot_id)
        if row is None or int(row.owner_user_id or 0) != owner_user_id:
            raise HTTPException(status_code=404, detail="Market signal snapshot not found")
        return row
    if snapshot_date is not None:
        stmt = stmt.where(MarketAcquisitionSignalSnapshot.snapshot_date == snapshot_date)
    row = session.exec(
        stmt.order_by(
            col(MarketAcquisitionSignalSnapshot.snapshot_date).desc(),
            col(MarketAcquisitionSignalSnapshot.id).desc(),
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No market signal snapshot available for opportunity aggregation",
        )
    return row


def generate_market_opportunities_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketAcquisitionOpportunityGeneratePayload,
) -> MarketAcquisitionOpportunityGenerateResponse:
    signal_snap = _load_owner_signal_snapshot_or_404(
        session,
        owner_user_id=owner_user_id,
        signal_snapshot_id=payload.signal_snapshot_id,
        snapshot_date=payload.snapshot_date,
    )
    signals = list(
        session.exec(
            select(MarketAcquisitionSignal).where(
                MarketAcquisitionSignal.market_acquisition_signal_snapshot_id
                == int(signal_snap.id or 0),
            ),
        ).all(),
    )
    signals.sort(key=_signal_sort_key)
    if not signals:
        raise HTTPException(status_code=400, detail="Selected signal snapshot has no signals")

    scored_ids = [int(s.scored_candidate_id or 0) for s in signals]
    score_rows = list(
        session.exec(
            select(MarketAcquisitionScore).where(col(MarketAcquisitionScore.id).in_(scored_ids))
        ).all(),
    )
    scores_by_id = {int(r.id or 0): r for r in score_rows}

    staged: list[dict[str, Any]] = []
    for sig in signals:
        score = scores_by_id.get(int(sig.scored_candidate_id or 0))
        if score is None:
            raise HTTPException(
                status_code=500, detail="Signal references missing persisted score row"
            )
        staged.append(
            {
                "signal": sig,
                "candidate_id": int(score.normalized_candidate_id or 0),
                "score": score,
            }
        )

    raws = [
        _raw_contribution(str(r["signal"].signal_type), str(r["signal"].signal_strength))
        for r in staged
    ]
    weights = _normalize_contribution_weights(raws)

    total_signals = len(signals)
    strengths = [str(s.signal_strength) for s in signals]
    types_ = [str(s.signal_type) for s in signals]
    uniq_candidates = sorted({row["candidate_id"] for row in staged})

    value_dislocation_count = sum(1 for t in types_ if t == "VALUE_DISLOCATION")
    liquidity_opportunity_count = sum(1 for t in types_ if t == "LIQUIDITY_OPPORTUNITY")
    portfolio_gap_fill_count = sum(1 for t in types_ if t == "PORTFOLIO_GAP_FILL")
    concentration_reduction_count = sum(1 for t in types_ if t == "CONCENTRATION_REDUCTION")
    grading_upside_count = sum(1 for t in types_ if t == "GRADING_UPSIDE")
    redundant_asset_count = sum(1 for t in types_ if t == "REDUNDANT_ASSET")
    high_risk_asset_count = sum(1 for t in types_ if t == "HIGH_RISK_ASSET")

    acq_scores: list[Decimal] = []
    strengths_num: list[Decimal] = []
    confidence_num: list[Decimal] = []
    risk_num: list[Decimal] = []
    for row in staged:
        sc = row["score"]
        acq_scores.append(_score_or_zero(_money(sc.final_rank_score)))
        strengths_num.append(
            STRENGTH_SCORE_MAP.get(str(row["signal"].signal_strength), Decimal("50"))
        )
        confidence_num.append(_bucket_to_numeric(str(sc.confidence_level)))
        risk_num.append(_bucket_to_numeric(str(sc.risk_level)))

    def _mean(vals: list[Decimal]) -> Decimal | None:
        if not vals:
            return None
        return (sum(vals) / Decimal(len(vals))).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)

    avg_acquisition_score = _mean(acq_scores)
    avg_signal_strength = _mean(strengths_num)
    avg_confidence_level = _mean(confidence_num)
    avg_risk_level = _mean(risk_num)

    est_gap_cov, est_liq, est_div, est_risk = _portfolio_impacts(signals, scores_by_id)

    classification = classify_opportunity_portfolio_view(
        total_signals=total_signals,
        value_dislocation_count=value_dislocation_count,
        grading_upside_count=grading_upside_count,
        liquidity_opportunity_count=liquidity_opportunity_count,
        portfolio_gap_fill_count=portfolio_gap_fill_count,
        concentration_reduction_count=concentration_reduction_count,
        redundant_asset_count=redundant_asset_count,
        high_risk_asset_count=high_risk_asset_count,
        avg_acquisition_score=avg_acquisition_score,
    )

    item_payloads: list[dict[str, Any]] = []
    for row, weight in zip(staged, weights, strict=True):
        sig = row["signal"]
        sc = row["score"]
        item_payloads.append(
            {
                "market_acquisition_signal_id": int(sig.id or 0),
                "signal_checksum": sig.checksum,
                "candidate_id": int(row["candidate_id"]),
                "contribution_weight": str(weight),
                "acquisition_score": _money(sc.final_rank_score),
            }
        )

    checksum = _hash_payload(
        {
            "owner_user_id": owner_user_id,
            "market_acquisition_signal_snapshot_id": int(signal_snap.id or 0),
            "source_signal_snapshot_checksum": signal_snap.checksum,
            "opportunity_classification": classification,
            "totals": {
                "total_candidates": len(uniq_candidates),
                "total_signals": total_signals,
                "elite_signal_count": sum(1 for s in strengths if s == "ELITE"),
                "high_signal_count": sum(1 for s in strengths if s == "HIGH"),
                "medium_signal_count": sum(1 for s in strengths if s == "MEDIUM"),
                "low_signal_count": sum(1 for s in strengths if s == "LOW"),
                "value_dislocation_count": value_dislocation_count,
                "liquidity_opportunity_count": liquidity_opportunity_count,
                "portfolio_gap_fill_count": portfolio_gap_fill_count,
                "concentration_reduction_count": concentration_reduction_count,
                "grading_upside_count": grading_upside_count,
                "redundant_asset_count": redundant_asset_count,
                "high_risk_asset_count": high_risk_asset_count,
                "estimated_portfolio_gap_coverage": str(est_gap_cov),
                "estimated_liquidity_gain": str(est_liq),
                "estimated_diversification_gain": str(est_div),
                "estimated_risk_adjustment": str(est_risk),
                "avg_signal_strength": str(avg_signal_strength)
                if avg_signal_strength is not None
                else None,
                "avg_acquisition_score": str(avg_acquisition_score)
                if avg_acquisition_score is not None
                else None,
                "avg_confidence_level": str(avg_confidence_level)
                if avg_confidence_level is not None
                else None,
                "avg_risk_level": str(avg_risk_level) if avg_risk_level is not None else None,
            },
            "items": [
                {
                    "market_acquisition_signal_id": p["market_acquisition_signal_id"],
                    "signal_checksum": p["signal_checksum"],
                    "candidate_id": p["candidate_id"],
                    "contribution_weight": p["contribution_weight"],
                }
                for p in item_payloads
            ],
        }
    )

    existing = session.exec(
        select(MarketAcquisitionOpportunitySnapshot)
        .where(
            MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id,
            MarketAcquisitionOpportunitySnapshot.market_acquisition_signal_snapshot_id
            == int(signal_snap.id or 0),
            MarketAcquisitionOpportunitySnapshot.snapshot_checksum == checksum,
        )
        .order_by(col(MarketAcquisitionOpportunitySnapshot.id).desc())
    ).first()
    if existing is not None:
        total_existing = int(
            session.exec(
                select(func.count()).where(
                    MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                    == int(existing.id or 0),
                ),
            ).one()
            or 0
        )
        return MarketAcquisitionOpportunityGenerateResponse(
            replayed=True,
            snapshot=_snapshot_read(existing),
            total_items=total_existing,
        )

    score_snap = session.get(
        MarketAcquisitionScoreSnapshot, int(signal_snap.market_acquisition_score_snapshot_id or 0)
    )
    if score_snap is None:
        raise HTTPException(status_code=500, detail="Signal snapshot missing score snapshot parent")

    snap_date = signal_snap.snapshot_date
    snap = MarketAcquisitionOpportunitySnapshot(
        market_acquisition_signal_snapshot_id=int(signal_snap.id or 0),
        owner_user_id=owner_user_id,
        opportunity_classification=classification,
        total_candidates=len(uniq_candidates),
        total_signals=total_signals,
        elite_signal_count=sum(1 for s in strengths if s == "ELITE"),
        high_signal_count=sum(1 for s in strengths if s == "HIGH"),
        medium_signal_count=sum(1 for s in strengths if s == "MEDIUM"),
        low_signal_count=sum(1 for s in strengths if s == "LOW"),
        value_dislocation_count=value_dislocation_count,
        liquidity_opportunity_count=liquidity_opportunity_count,
        portfolio_gap_fill_count=portfolio_gap_fill_count,
        concentration_reduction_count=concentration_reduction_count,
        grading_upside_count=grading_upside_count,
        redundant_asset_count=redundant_asset_count,
        high_risk_asset_count=high_risk_asset_count,
        estimated_portfolio_gap_coverage=est_gap_cov,
        estimated_liquidity_gain=est_liq,
        estimated_diversification_gain=est_div,
        estimated_risk_adjustment=est_risk,
        avg_signal_strength=_quantize_pct(avg_signal_strength),
        avg_acquisition_score=_quantize_pct(avg_acquisition_score),
        avg_confidence_level=_quantize_pct(avg_confidence_level),
        avg_risk_level=_quantize_pct(avg_risk_level),
        snapshot_checksum=checksum,
        snapshot_date=snap_date,
        created_at=utc_now(),
    )
    session.add(snap)
    session.flush()

    liq_ctx = session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(PortfolioLiquiditySnapshot.owner_user_id == owner_user_id)
        .order_by(
            col(PortfolioLiquiditySnapshot.snapshot_date).desc(),
            col(PortfolioLiquiditySnapshot.id).desc(),
        )
    ).first()

    cand_sorted = sorted(uniq_candidates)
    conc_vals = [
        _score_or_zero(
            _money(scores_by_id[int(sig.scored_candidate_id or 0)].concentration_reduction_score)
        )
        for sig in signals
        if str(sig.signal_type) == "CONCENTRATION_REDUCTION"
        and int(sig.scored_candidate_id or 0) in scores_by_id
    ]

    evidences: list[MarketAcquisitionOpportunityEvidence] = [
        MarketAcquisitionOpportunityEvidence(
            market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
            evidence_type="SIGNAL_LAYER",
            source_id=int(signal_snap.id or 0),
            source_table="market_acquisition_signal_snapshot",
            evidence_value_json=_json_safe(
                {
                    "checksum": signal_snap.checksum,
                    "total_signals_signal_snapshot": signal_snap.total_signals,
                    "market_acquisition_score_snapshot_id": int(
                        signal_snap.market_acquisition_score_snapshot_id or 0
                    ),
                },
            ),
            created_at=utc_now(),
        ),
        MarketAcquisitionOpportunityEvidence(
            market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
            evidence_type="SCORING_LAYER",
            source_id=int(score_snap.id or 0),
            source_table="market_acquisition_score_snapshot",
            evidence_value_json=_json_safe(
                {
                    "checksum": score_snap.checksum,
                    "total_candidates_scored": score_snap.total_candidates_scored,
                },
            ),
            created_at=utc_now(),
        ),
        MarketAcquisitionOpportunityEvidence(
            market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
            evidence_type="NORMALIZATION_LAYER",
            source_id=None,
            source_table="market_acquisition_normalized_candidate",
            evidence_value_json=_json_safe({"normalized_candidate_ids": cand_sorted}),
            created_at=utc_now(),
        ),
        MarketAcquisitionOpportunityEvidence(
            market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
            evidence_type="PORTFOLIO_CONTEXT",
            source_id=int(liq_ctx.id or 0) if liq_ctx is not None else None,
            source_table="portfolio_liquidity_snapshot" if liq_ctx is not None else None,
            evidence_value_json=_json_safe(
                {
                    "portfolio_liquidity_snapshot_id": int(liq_ctx.id or 0)
                    if liq_ctx is not None
                    else None,
                    "liquidity_efficiency_score": _money(liq_ctx.liquidity_efficiency_score)
                    if liq_ctx
                    else None,
                },
            ),
            created_at=utc_now(),
        ),
        MarketAcquisitionOpportunityEvidence(
            market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
            evidence_type="CONCENTRATION_RISK",
            source_id=None,
            source_table=None,
            evidence_value_json=_json_safe(
                {
                    "concentration_reduction_signal_count": concentration_reduction_count,
                    "avg_concentration_reduction_score_on_signals": str(conc_vals[0])
                    if len(conc_vals) == 1
                    else (
                        str(
                            (sum(conc_vals) / Decimal(len(conc_vals))).quantize(
                                Decimal("0.0001"), rounding=ROUND_HALF_UP
                            )
                        )
                        if conc_vals
                        else None
                    ),
                },
            ),
            created_at=utc_now(),
        ),
    ]
    history = MarketAcquisitionOpportunityHistory(
        owner_user_id=owner_user_id,
        market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
        snapshot_checksum=checksum,
        total_candidates=len(uniq_candidates),
        elite_signal_count=snap.elite_signal_count,
        high_signal_count=snap.high_signal_count,
        estimated_portfolio_gap_coverage=est_gap_cov,
        estimated_diversification_gain=est_div,
        snapshot_date=snap_date,
        created_at=utc_now(),
    )

    for row, payload_, weight in zip(staged, item_payloads, weights, strict=True):
        sig = row["signal"]
        sc = row["score"]
        session.add(
            MarketAcquisitionOpportunityItem(
                market_acquisition_opportunity_snapshot_id=int(snap.id or 0),
                candidate_id=int(row["candidate_id"]),
                market_acquisition_signal_id=int(sig.id or 0),
                owner_user_id=owner_user_id,
                signal_type=str(sig.signal_type),
                signal_strength=str(sig.signal_strength),
                acquisition_score=payload_["acquisition_score"],
                confidence_level=str(sc.confidence_level),
                risk_level=str(sc.risk_level),
                contribution_weight=weight,
                snapshot_date=snap_date,
                created_at=utc_now(),
            )
        )

    for ev in evidences:
        session.add(ev)
    session.add(history)
    append_market_feed_event(
        session,
        owner_user_id=owner_user_id,
        event_type="OPPORTUNITIES_GENERATED",
        severity="INFO",
        snapshot_date=snap_date,
        event_payload_json={
            "opportunity_snapshot_id": int(snap.id or 0),
            "signal_snapshot_id": int(signal_snap.id or 0),
            "snapshot_checksum": checksum,
            "total_candidates": len(uniq_candidates),
            "total_signals": total_signals,
            "opportunity_classification": classification,
        },
        opportunity_snapshot_id=int(snap.id or 0),
        signal_snapshot_id=int(signal_snap.id or 0),
    )
    append_market_feed_event(
        session,
        owner_user_id=owner_user_id,
        event_type="SNAPSHOT_CREATED",
        severity="INFO",
        snapshot_date=snap_date,
        event_payload_json={
            "layer": "opportunities",
            "opportunity_snapshot_id": int(snap.id or 0),
            "snapshot_checksum": checksum,
        },
        opportunity_snapshot_id=int(snap.id or 0),
    )
    session.commit()
    session.refresh(snap)

    total_items = int(
        session.exec(
            select(func.count()).where(
                MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                == int(snap.id or 0),
            ),
        ).one()
        or 0
    )
    return MarketAcquisitionOpportunityGenerateResponse(
        replayed=False,
        snapshot=_snapshot_read(snap),
        total_items=total_items,
    )


def list_opportunity_items_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int | None,
    signal_type: str | None,
    signal_strength: str | None,
    risk_level: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunityItemListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    tgt_snapshot_id = snapshot_id
    if tgt_snapshot_id is None:
        latest = session.exec(
            select(MarketAcquisitionOpportunitySnapshot)
            .where(MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id)
            .order_by(
                col(MarketAcquisitionOpportunitySnapshot.snapshot_date).desc(),
                col(MarketAcquisitionOpportunitySnapshot.id).desc(),
            ),
        ).first()
        tgt_snapshot_id = int(latest.id or 0) if latest else None

    stmt = select(MarketAcquisitionOpportunityItem).where(
        MarketAcquisitionOpportunityItem.owner_user_id == owner_user_id
    )
    if tgt_snapshot_id is not None:
        stmt = stmt.where(
            MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
            == tgt_snapshot_id
        )

    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.signal_strength == signal_strength)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.snapshot_date <= snapshot_date_to)

    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(
                    MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                ).desc(),
                col(MarketAcquisitionOpportunityItem.id).asc(),
            )
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunityItemListResponse(
        items=[_item_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def list_opportunity_items_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    snapshot_id: int | None,
    signal_type: str | None,
    signal_strength: str | None,
    risk_level: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunityItemListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionOpportunityItem)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.owner_user_id == owner_user_id)
    if snapshot_id is not None:
        stmt = stmt.where(
            MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
            == snapshot_id
        )

    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.signal_strength == signal_strength)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityItem.snapshot_date <= snapshot_date_to)

    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionOpportunityItem.owner_user_id).asc(),
                col(MarketAcquisitionOpportunityItem.snapshot_date).desc(),
                col(
                    MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                ).desc(),
                col(MarketAcquisitionOpportunityItem.id).asc(),
            )
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunityItemListResponse(
        items=[_item_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def list_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunitySnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionOpportunitySnapshot).where(
        MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id
    )
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionOpportunitySnapshot.snapshot_date).desc(),
                col(MarketAcquisitionOpportunitySnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunitySnapshotListResponse(
        items=[_snapshot_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def list_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunitySnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionOpportunitySnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionOpportunitySnapshot.snapshot_date).desc(),
                col(MarketAcquisitionOpportunitySnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunitySnapshotListResponse(
        items=[_snapshot_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def _snapshot_owner_row_or_404(
    session: Session, *, owner_user_id: int, opportunity_snapshot_id: int
) -> MarketAcquisitionOpportunitySnapshot:
    row = session.get(MarketAcquisitionOpportunitySnapshot, opportunity_snapshot_id)
    if row is None or int(row.owner_user_id or -1) != owner_user_id:
        raise HTTPException(status_code=404, detail="Market opportunity snapshot not found")
    return row


def _snapshot_ops_row_or_404(
    session: Session, *, opportunity_snapshot_id: int
) -> MarketAcquisitionOpportunitySnapshot:
    row = session.get(MarketAcquisitionOpportunitySnapshot, opportunity_snapshot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market opportunity snapshot not found")
    return row


def get_opportunity_detail_owner(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_snapshot_id: int,
) -> MarketAcquisitionOpportunityDetailRead:
    snap = _snapshot_owner_row_or_404(
        session, owner_user_id=owner_user_id, opportunity_snapshot_id=opportunity_snapshot_id
    )
    items = list(
        session.exec(
            select(MarketAcquisitionOpportunityItem)
            .where(
                MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                == int(snap.id or 0)
            )
            .order_by(
                col(MarketAcquisitionOpportunityItem.id).asc(),
            ),
        ).all(),
    )
    return MarketAcquisitionOpportunityDetailRead(
        snapshot=_snapshot_read(snap), items=[_item_read(i) for i in items]
    )


def get_opportunity_detail_ops(
    session: Session, *, opportunity_snapshot_id: int
) -> MarketAcquisitionOpportunityDetailRead:
    snap = _snapshot_ops_row_or_404(session, opportunity_snapshot_id=opportunity_snapshot_id)
    items = list(
        session.exec(
            select(MarketAcquisitionOpportunityItem)
            .where(
                MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                == int(snap.id or 0)
            )
            .order_by(
                col(MarketAcquisitionOpportunityItem.id).asc(),
            ),
        ).all(),
    )
    return MarketAcquisitionOpportunityDetailRead(
        snapshot=_snapshot_read(snap), items=[_item_read(i) for i in items]
    )


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_snapshot_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunityEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(MarketAcquisitionOpportunityEvidence)
        .join(
            MarketAcquisitionOpportunitySnapshot,
            MarketAcquisitionOpportunityEvidence.market_acquisition_opportunity_snapshot_id
            == MarketAcquisitionOpportunitySnapshot.id,
        )
        .where(MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id)
    )
    if opportunity_snapshot_id is not None:
        stmt = stmt.where(
            MarketAcquisitionOpportunityEvidence.market_acquisition_opportunity_snapshot_id
            == opportunity_snapshot_id
        )
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date <= snapshot_date_to)

    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(col(MarketAcquisitionOpportunityEvidence.id).asc())
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunityEvidenceListResponse(
        items=[_evidence_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    opportunity_snapshot_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunityEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionOpportunityEvidence).join(
        MarketAcquisitionOpportunitySnapshot,
        MarketAcquisitionOpportunityEvidence.market_acquisition_opportunity_snapshot_id
        == MarketAcquisitionOpportunitySnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id)
    if opportunity_snapshot_id is not None:
        stmt = stmt.where(
            MarketAcquisitionOpportunityEvidence.market_acquisition_opportunity_snapshot_id
            == opportunity_snapshot_id
        )
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunitySnapshot.snapshot_date <= snapshot_date_to)

    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(col(MarketAcquisitionOpportunityEvidence.id).asc())
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunityEvidenceListResponse(
        items=[_evidence_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_snapshot_id: int | None = None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunityHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionOpportunityHistory).where(
        MarketAcquisitionOpportunityHistory.owner_user_id == owner_user_id
    )
    if opportunity_snapshot_id is not None:
        stmt = stmt.where(
            MarketAcquisitionOpportunityHistory.market_acquisition_opportunity_snapshot_id
            == opportunity_snapshot_id,
        )
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(col(MarketAcquisitionOpportunityHistory.created_at).desc())
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunityHistoryListResponse(
        items=[_history_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    opportunity_snapshot_id: int | None = None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionOpportunityHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionOpportunityHistory)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityHistory.owner_user_id == owner_user_id)
    if opportunity_snapshot_id is not None:
        stmt = stmt.where(
            MarketAcquisitionOpportunityHistory.market_acquisition_opportunity_snapshot_id
            == opportunity_snapshot_id,
        )
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionOpportunityHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(col(MarketAcquisitionOpportunityHistory.created_at).desc())
            .offset(offset)
            .limit(limit),
        ).all(),
    )
    return MarketAcquisitionOpportunityHistoryListResponse(
        items=[_history_read(r) for r in rows], total_items=total, limit=limit, offset=offset
    )


def inventory_market_opportunity_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryMarketAcquisitionOpportunityTeaser | None:
    issue_row = session.exec(
        select(InventoryCopy.catalog_issue_id).where(
            InventoryCopy.user_id == owner_user_id,
            InventoryCopy.id == inventory_item_id,
        )
    ).first()
    if issue_row is None:
        return None
    catalog_issue_id = int(issue_row)

    opp_item = session.exec(
        select(MarketAcquisitionOpportunityItem)
        .join(
            MarketAcquisitionSignal,
            MarketAcquisitionOpportunityItem.market_acquisition_signal_id
            == MarketAcquisitionSignal.id,
        )
        .join(
            MarketAcquisitionScore,
            MarketAcquisitionSignal.scored_candidate_id == MarketAcquisitionScore.id,
        )
        .where(
            MarketAcquisitionOpportunityItem.owner_user_id == owner_user_id,
            or_(
                MarketAcquisitionScore.catalog_issue_id == catalog_issue_id,
                MarketAcquisitionScore.canonical_comic_issue_id == catalog_issue_id,
            ),
        )
        .order_by(
            col(MarketAcquisitionOpportunityItem.snapshot_date).desc(),
            col(MarketAcquisitionOpportunityItem.id).desc(),
        )
    ).first()
    if opp_item is None:
        return None

    snap = session.get(
        MarketAcquisitionOpportunitySnapshot,
        int(opp_item.market_acquisition_opportunity_snapshot_id or 0),
    )
    if snap is None:
        return None

    return InventoryMarketAcquisitionOpportunityTeaser(
        opportunity_classification=str(snap.opportunity_classification),
        signal_strength=str(opp_item.signal_strength),
        snapshot_date=snap.snapshot_date,
    )
