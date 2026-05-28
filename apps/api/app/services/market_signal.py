from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    InventoryCopy,
    MarketAcquisitionScore,
    MarketAcquisitionScoreEvidence,
    MarketAcquisitionScoreSnapshot,
    MarketAcquisitionSignal,
    MarketAcquisitionSignalEvidence,
    MarketAcquisitionSignalHistory,
    MarketAcquisitionSignalSnapshot,
    Variant,
)
from app.services.market_feed import append_market_feed_event
from app.schemas.market_signal import (
    InventoryMarketAcquisitionSignalTeaser,
    MarketAcquisitionSignalDetailRead,
    MarketAcquisitionSignalEvidenceListResponse,
    MarketAcquisitionSignalEvidenceRead,
    MarketAcquisitionSignalGeneratePayload,
    MarketAcquisitionSignalGenerateResponse,
    MarketAcquisitionSignalHistoryListResponse,
    MarketAcquisitionSignalHistoryRead,
    MarketAcquisitionSignalListResponse,
    MarketAcquisitionSignalRead,
    MarketAcquisitionSignalSnapshotListResponse,
    MarketAcquisitionSignalSnapshotRead,
)

ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")
SCORE_QUANT = Decimal("0.01")

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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _money(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _score_or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP))
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


def _signal_strength(final_rank_score: Decimal | None) -> str:
    score = _score_or_zero(_money(final_rank_score))
    if score >= Decimal("85"):
        return "ELITE"
    if score >= Decimal("70"):
        return "HIGH"
    if score >= Decimal("50"):
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class _SignalContext:
    score: MarketAcquisitionScore
    score_snapshot: MarketAcquisitionScoreSnapshot
    evidence_map: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class _SignalCandidate:
    signal_type: str
    driver_score: Decimal
    reason: dict[str, Any]


def _score_read(row: MarketAcquisitionSignal) -> MarketAcquisitionSignalRead:
    return MarketAcquisitionSignalRead.model_validate(row, from_attributes=True)


def _snapshot_read(row: MarketAcquisitionSignalSnapshot) -> MarketAcquisitionSignalSnapshotRead:
    return MarketAcquisitionSignalSnapshotRead.model_validate(row, from_attributes=True)


def _history_read(row: MarketAcquisitionSignalHistory) -> MarketAcquisitionSignalHistoryRead:
    return MarketAcquisitionSignalHistoryRead.model_validate(row, from_attributes=True)


def _evidence_read(row: MarketAcquisitionSignalEvidence) -> MarketAcquisitionSignalEvidenceRead:
    return MarketAcquisitionSignalEvidenceRead.model_validate(row, from_attributes=True)


def _load_owner_score_snapshot_or_404(
    session: Session,
    *,
    owner_user_id: int,
    score_snapshot_id: int | None,
    snapshot_date: date | None,
) -> MarketAcquisitionScoreSnapshot:
    stmt = select(MarketAcquisitionScoreSnapshot).where(MarketAcquisitionScoreSnapshot.owner_user_id == owner_user_id)
    if score_snapshot_id is not None:
        row = session.get(MarketAcquisitionScoreSnapshot, score_snapshot_id)
        if row is None or int(row.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=404, detail="Market scoring snapshot not found")
        return row
    if snapshot_date is not None:
        stmt = stmt.where(MarketAcquisitionScoreSnapshot.snapshot_date == snapshot_date)
    row = session.exec(
        stmt.order_by(col(MarketAcquisitionScoreSnapshot.snapshot_date).desc(), col(MarketAcquisitionScoreSnapshot.id).desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No market scoring snapshot available for signal generation")
    return row


def _load_signal_inputs(
    session: Session,
    *,
    score_snapshot_id: int,
) -> list[_SignalContext]:
    scores = list(
        session.exec(
            select(MarketAcquisitionScore)
            .where(MarketAcquisitionScore.market_acquisition_score_snapshot_id == score_snapshot_id)
            .order_by(col(MarketAcquisitionScore.final_rank_score).desc(), col(MarketAcquisitionScore.id).asc())
        ).all(),
    )
    score_ids = [int(row.id or 0) for row in scores]
    evidence_rows = list(
        session.exec(
            select(MarketAcquisitionScoreEvidence)
            .where(col(MarketAcquisitionScoreEvidence.score_id).in_(score_ids or [0]))
            .order_by(col(MarketAcquisitionScoreEvidence.score_id).asc(), col(MarketAcquisitionScoreEvidence.id).asc())
        ).all(),
    )
    evidence_by_score: dict[int, dict[str, dict[str, Any]]] = {}
    for row in evidence_rows:
        score_id = int(row.score_id or 0)
        evidence_by_score.setdefault(score_id, {})[str(row.evidence_type)] = dict(row.evidence_value_json or {})
    snapshot = session.get(MarketAcquisitionScoreSnapshot, score_snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Market scoring snapshot not found")
    return [
        _SignalContext(
            score=row,
            score_snapshot=snapshot,
            evidence_map=evidence_by_score.get(int(row.id or 0), {}),
        )
        for row in scores
    ]


def _select_signal(context: _SignalContext) -> tuple[str, dict[str, Any], dict[str, Any]]:
    score = context.score
    evidence = context.evidence_map
    norm = evidence.get("NORMALIZATION_LAYER", {})
    duplicate = evidence.get("DUPLICATE_INTELLIGENCE", {})
    conc = evidence.get("CONCENTRATION_RISK", {})
    liquidity = evidence.get("LIQUIDITY_ENGINE", {})
    portfolio = evidence.get("PORTFOLIO_STATE", {})

    final_rank_score = _money(score.final_rank_score)
    liquidity_score = _money(score.liquidity_score)
    portfolio_fit_score = _money(score.portfolio_fit_score)
    diversification_score = _money(score.diversification_score)
    concentration_reduction_score = _money(score.concentration_reduction_score)
    grading_upside_score = _money(score.grading_upside_score)
    risk_penalty_score = _money(score.risk_penalty_score)

    price = _money(norm.get("normalized_price"))
    fmv = _money(norm.get("normalized_fmv_estimate"))
    condition_band = str(norm.get("condition_band") or "")
    existing_issue_count = int(duplicate.get("existing_issue_count") or 0)
    duplicate_overlap_penalty = _money(duplicate.get("duplicate_overlap_penalty"))
    publisher_status = str(conc.get("publisher_status") or "")
    title_status = str(conc.get("title_status") or "")
    portfolio_balance_status = str(liquidity.get("portfolio_balance_status") or "")

    candidates: list[_SignalCandidate] = []

    if (
        final_rank_score is not None
        and final_rank_score >= Decimal("70")
        and price is not None
        and fmv is not None
        and fmv > ZERO
        and price <= (fmv * Decimal("0.90")).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
    ):
        discount_pct = ((fmv - price) / fmv * HUNDRED).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
        candidates.append(
            _SignalCandidate(
                signal_type="VALUE_DISLOCATION",
                driver_score=discount_pct,
                reason={
                    "rule": "high_scoring_price_below_fmv",
                    "normalized_price": price,
                    "normalized_fmv_estimate": fmv,
                    "discount_pct": discount_pct,
                },
            )
        )

    if (
        liquidity_score is not None
        and liquidity_score >= Decimal("70")
        and score.recommendation_label in {"BUY", "STRONG_BUY"}
        and portfolio_balance_status in {"WATCH", "HEALTHY", "HIGH", "MEDIUM"}
    ):
        candidates.append(
            _SignalCandidate(
                signal_type="LIQUIDITY_OPPORTUNITY",
                driver_score=liquidity_score,
                reason={
                    "rule": "high_liquidity_and_demand_proxy",
                    "liquidity_score": liquidity_score,
                    "recommendation_label": score.recommendation_label,
                    "portfolio_balance_status": portfolio_balance_status,
                },
            )
        )

    if (
        portfolio_fit_score is not None
        and diversification_score is not None
        and portfolio_fit_score >= Decimal("70")
        and diversification_score >= Decimal("65")
    ):
        candidates.append(
            _SignalCandidate(
                signal_type="PORTFOLIO_GAP_FILL",
                driver_score=((portfolio_fit_score + diversification_score) / Decimal("2")).quantize(
                    SCORE_QUANT,
                    rounding=ROUND_HALF_UP,
                ),
                reason={
                    "rule": "high_fit_and_diversification",
                    "portfolio_fit_score": portfolio_fit_score,
                    "diversification_score": diversification_score,
                    "existing_issue_count": existing_issue_count,
                },
            )
        )

    if (
        concentration_reduction_score is not None
        and concentration_reduction_score >= Decimal("60")
        and {publisher_status, title_status} & {"CRITICAL", "OVEREXPOSED", "CONCENTRATED"}
    ):
        candidates.append(
            _SignalCandidate(
                signal_type="CONCENTRATION_REDUCTION",
                driver_score=concentration_reduction_score,
                reason={
                    "rule": "reduces_existing_overexposure",
                    "concentration_reduction_score": concentration_reduction_score,
                    "publisher_status": publisher_status,
                    "title_status": title_status,
                },
            )
        )

    if (
        grading_upside_score is not None
        and grading_upside_score >= Decimal("70")
        and condition_band in {"FINE", "VF", "NM"}
    ):
        candidates.append(
            _SignalCandidate(
                signal_type="GRADING_UPSIDE",
                driver_score=grading_upside_score,
                reason={
                    "rule": "grading_upside_above_threshold",
                    "grading_upside_score": grading_upside_score,
                    "condition_band": condition_band,
                },
            )
        )

    if existing_issue_count > 0 or (_score_or_zero(duplicate_overlap_penalty) >= Decimal("15")):
        candidates.append(
            _SignalCandidate(
                signal_type="REDUNDANT_ASSET",
                driver_score=max(
                    _score_or_zero(duplicate_overlap_penalty),
                    Decimal(existing_issue_count * 20).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP),
                ),
                reason={
                    "rule": "duplicate_overlap_detected",
                    "existing_issue_count": existing_issue_count,
                    "duplicate_overlap_penalty": duplicate_overlap_penalty,
                },
            )
        )

    if (
        _score_or_zero(risk_penalty_score) >= Decimal("60")
        or _score_or_zero(liquidity_score) <= Decimal("40")
        or score.risk_level == "HIGH"
    ):
        candidates.append(
            _SignalCandidate(
                signal_type="HIGH_RISK_ASSET",
                driver_score=max(
                    _score_or_zero(risk_penalty_score),
                    (HUNDRED - _score_or_zero(liquidity_score)).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP),
                ),
                reason={
                    "rule": "risk_penalty_or_low_liquidity",
                    "risk_penalty_score": risk_penalty_score,
                    "liquidity_score": liquidity_score,
                    "risk_level": score.risk_level,
                },
            )
        )

    if candidates:
        selected = sorted(
            candidates,
            key=lambda row: (
                -row.driver_score,
                TYPE_PRIORITY[row.signal_type],
            ),
        )[0]
    elif _score_or_zero(final_rank_score) < Decimal("50"):
        selected = _SignalCandidate(
            signal_type="HIGH_RISK_ASSET",
            driver_score=_score_or_zero(risk_penalty_score),
            reason={
                "rule": "fallback_low_rank_score",
                "final_rank_score": final_rank_score,
            },
        )
    else:
        component_choices = [
            ("PORTFOLIO_GAP_FILL", _score_or_zero(portfolio_fit_score) + _score_or_zero(diversification_score)),
            ("LIQUIDITY_OPPORTUNITY", _score_or_zero(liquidity_score) * Decimal("2")),
            ("GRADING_UPSIDE", _score_or_zero(grading_upside_score) * Decimal("2")),
            ("CONCENTRATION_REDUCTION", _score_or_zero(concentration_reduction_score) * Decimal("2")),
        ]
        signal_type, driver = sorted(
            component_choices,
            key=lambda row: (-row[1], TYPE_PRIORITY[row[0]]),
        )[0]
        selected = _SignalCandidate(
            signal_type=signal_type,
            driver_score=driver.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP),
            reason={
                "rule": "fallback_component_dominance",
                "portfolio_fit_score": portfolio_fit_score,
                "diversification_score": diversification_score,
                "liquidity_score": liquidity_score,
                "grading_upside_score": grading_upside_score,
                "concentration_reduction_score": concentration_reduction_score,
            },
        )

    supporting_factors = {
        "final_rank_score": final_rank_score,
        "signal_strength": _signal_strength(final_rank_score),
        "confidence_level": score.confidence_level,
        "risk_level": score.risk_level,
        "liquidity_score": liquidity_score,
        "portfolio_fit_score": portfolio_fit_score,
        "diversification_score": diversification_score,
        "concentration_reduction_score": concentration_reduction_score,
        "grading_upside_score": grading_upside_score,
        "risk_penalty_score": risk_penalty_score,
        "duplicate_overlap_penalty": duplicate_overlap_penalty,
        "existing_issue_count": existing_issue_count,
        "condition_band": condition_band or None,
        "normalized_price": price,
        "normalized_fmv_estimate": fmv,
        "publisher_status": publisher_status or None,
        "title_status": title_status or None,
        "portfolio_balance_status": portfolio_balance_status or None,
        "source_score_snapshot_id": int(context.score_snapshot.id or 0),
        "source_score_id": int(score.id or 0),
        "source_score_checksum": score.checksum,
        "source_score_snapshot_checksum": context.score_snapshot.checksum,
        "source_recommendation_label": score.recommendation_label,
        "portfolio_state_existing_issue_count": portfolio.get("existing_issue_count"),
    }
    return selected.signal_type, _json_safe(selected.reason), _json_safe(supporting_factors)


def generate_market_signals_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketAcquisitionSignalGeneratePayload,
) -> MarketAcquisitionSignalGenerateResponse:
    score_snapshot = _load_owner_score_snapshot_or_404(
        session,
        owner_user_id=owner_user_id,
        score_snapshot_id=payload.score_snapshot_id,
        snapshot_date=payload.snapshot_date,
    )
    snapshot_date = score_snapshot.snapshot_date
    inputs = _load_signal_inputs(session, score_snapshot_id=int(score_snapshot.id or 0))

    staged_rows: list[dict[str, Any]] = []
    for ctx in inputs:
        signal_type, reason_json, supporting_factors = _select_signal(ctx)
        signal_checksum = _hash_payload(
            {
                "score_id": int(ctx.score.id or 0),
                "score_checksum": ctx.score.checksum,
                "score_snapshot_checksum": ctx.score_snapshot.checksum,
                "signal_type": signal_type,
                "signal_strength": _signal_strength(ctx.score.final_rank_score),
                "signal_score": _money(ctx.score.final_rank_score),
                "confidence_level": ctx.score.confidence_level,
                "risk_level": ctx.score.risk_level,
                "reason": reason_json,
                "supporting_factors": supporting_factors,
            }
        )
        staged_rows.append(
            {
                "scored_candidate_id": int(ctx.score.id or 0),
                "owner_user_id": owner_user_id,
                "signal_type": signal_type,
                "signal_strength": _signal_strength(ctx.score.final_rank_score),
                "signal_score": _money(ctx.score.final_rank_score),
                "confidence_level": ctx.score.confidence_level,
                "risk_level": ctx.score.risk_level,
                "signal_reason_json": reason_json,
                "supporting_factors_json": supporting_factors,
                "checksum": signal_checksum,
                "snapshot_date": ctx.score.snapshot_date,
                "evidence_payloads": [
                    {
                        "evidence_type": "SOURCE_SCORE",
                        "source_id": int(ctx.score.id or 0),
                        "source_table": "market_acquisition_score",
                        "evidence_value_json": {
                            "score_snapshot_id": int(ctx.score.market_acquisition_score_snapshot_id or 0),
                            "score_checksum": ctx.score.checksum,
                            "recommendation_label": ctx.score.recommendation_label,
                            "final_rank_score": _money(ctx.score.final_rank_score),
                        },
                    },
                    {
                        "evidence_type": "SCORING_FACTORS",
                        "source_id": int(ctx.score.id or 0),
                        "source_table": "market_acquisition_score",
                        "evidence_value_json": {
                            "liquidity_score": _money(ctx.score.liquidity_score),
                            "portfolio_fit_score": _money(ctx.score.portfolio_fit_score),
                            "concentration_reduction_score": _money(ctx.score.concentration_reduction_score),
                            "duplicate_overlap_penalty": supporting_factors.get("duplicate_overlap_penalty"),
                            "grading_upside_score": _money(ctx.score.grading_upside_score),
                            "risk_penalty_score": _money(ctx.score.risk_penalty_score),
                        },
                    },
                    {
                        "evidence_type": "TRACEABILITY",
                        "source_id": int(ctx.score_snapshot.id or 0),
                        "source_table": "market_acquisition_score_snapshot",
                        "evidence_value_json": {
                            "signal_type": signal_type,
                            "signal_strength": _signal_strength(ctx.score.final_rank_score),
                            "signal_reason_json": reason_json,
                            "source_score_snapshot_checksum": ctx.score_snapshot.checksum,
                            "source_score_id": int(ctx.score.id or 0),
                        },
                    },
                ],
            }
        )

    snapshot_checksum = _hash_payload(
        {
            "owner_user_id": owner_user_id,
            "market_acquisition_score_snapshot_id": int(score_snapshot.id or 0),
            "source_score_snapshot_checksum": score_snapshot.checksum,
            "signals": [
                {
                    "scored_candidate_id": row["scored_candidate_id"],
                    "signal_type": row["signal_type"],
                    "checksum": row["checksum"],
                }
                for row in sorted(staged_rows, key=lambda row: (row["scored_candidate_id"], row["signal_type"]))
            ],
        }
    )

    existing_snapshot = session.exec(
        select(MarketAcquisitionSignalSnapshot)
        .where(
            MarketAcquisitionSignalSnapshot.owner_user_id == owner_user_id,
            MarketAcquisitionSignalSnapshot.market_acquisition_score_snapshot_id == int(score_snapshot.id or 0),
            MarketAcquisitionSignalSnapshot.checksum == snapshot_checksum,
        )
        .order_by(col(MarketAcquisitionSignalSnapshot.id).desc())
    ).first()
    if existing_snapshot is not None:
        total_existing = int(
            session.exec(
                select(func.count()).where(
                    MarketAcquisitionSignal.market_acquisition_signal_snapshot_id == int(existing_snapshot.id or 0)
                )
            ).one()
            or 0
        )
        return MarketAcquisitionSignalGenerateResponse(
            replayed=True,
            snapshot=_snapshot_read(existing_snapshot),
            total_signals=total_existing,
        )

    signal_types = [row["signal_type"] for row in staged_rows]
    strengths = [row["signal_strength"] for row in staged_rows]
    snapshot = MarketAcquisitionSignalSnapshot(
        market_acquisition_score_snapshot_id=int(score_snapshot.id or 0),
        owner_user_id=owner_user_id,
        total_signals=len(staged_rows),
        elite_signal_count=sum(1 for row in strengths if row == "ELITE"),
        high_signal_count=sum(1 for row in strengths if row == "HIGH"),
        medium_signal_count=sum(1 for row in strengths if row == "MEDIUM"),
        low_signal_count=sum(1 for row in strengths if row == "LOW"),
        value_dislocation_count=sum(1 for row in signal_types if row == "VALUE_DISLOCATION"),
        liquidity_opportunity_count=sum(1 for row in signal_types if row == "LIQUIDITY_OPPORTUNITY"),
        portfolio_gap_fill_count=sum(1 for row in signal_types if row == "PORTFOLIO_GAP_FILL"),
        concentration_reduction_count=sum(1 for row in signal_types if row == "CONCENTRATION_REDUCTION"),
        grading_upside_count=sum(1 for row in signal_types if row == "GRADING_UPSIDE"),
        redundant_asset_count=sum(1 for row in signal_types if row == "REDUNDANT_ASSET"),
        high_risk_asset_count=sum(1 for row in signal_types if row == "HIGH_RISK_ASSET"),
        checksum=snapshot_checksum,
        snapshot_date=score_snapshot.snapshot_date,
        created_at=utc_now(),
    )
    session.add(snapshot)
    session.flush()

    history_rows: list[MarketAcquisitionSignalHistory] = []
    evidence_rows: list[MarketAcquisitionSignalEvidence] = []
    for staged in staged_rows:
        signal_row = MarketAcquisitionSignal(
            market_acquisition_signal_snapshot_id=int(snapshot.id or 0),
            scored_candidate_id=staged["scored_candidate_id"],
            owner_user_id=staged["owner_user_id"],
            signal_type=staged["signal_type"],
            signal_strength=staged["signal_strength"],
            signal_score=staged["signal_score"],
            confidence_level=staged["confidence_level"],
            risk_level=staged["risk_level"],
            signal_reason_json=staged["signal_reason_json"],
            supporting_factors_json=staged["supporting_factors_json"],
            checksum=staged["checksum"],
            snapshot_date=staged["snapshot_date"],
            created_at=utc_now(),
        )
        session.add(signal_row)
        session.flush()
        signal_id = int(signal_row.id or 0)
        for ev in staged["evidence_payloads"]:
            evidence_rows.append(
                MarketAcquisitionSignalEvidence(
                    market_acquisition_signal_id=signal_id,
                    evidence_type=ev["evidence_type"],
                    source_id=ev["source_id"],
                    source_table=ev["source_table"],
                    evidence_value_json=_json_safe(ev["evidence_value_json"]),
                    created_at=utc_now(),
                )
            )
        history_rows.append(
            MarketAcquisitionSignalHistory(
                owner_user_id=owner_user_id,
                scored_candidate_id=staged["scored_candidate_id"],
                signal_type=staged["signal_type"],
                signal_strength=staged["signal_strength"],
                signal_score=staged["signal_score"],
                confidence_level=staged["confidence_level"],
                risk_level=staged["risk_level"],
                checksum=staged["checksum"],
                snapshot_date=staged["snapshot_date"],
                created_at=utc_now(),
            )
        )

    for row in evidence_rows + history_rows:
        session.add(row)
    append_market_feed_event(
        session,
        owner_user_id=owner_user_id,
        event_type="SIGNALS_GENERATED",
        severity="INFO",
        snapshot_date=snapshot_date,
        event_payload_json={
            "signal_snapshot_id": int(snapshot.id or 0),
            "source_score_snapshot_id": int(score_snapshot.id or 0),
            "snapshot_checksum": snapshot_checksum,
            "total_signals": len(staged_rows),
            "elite_signal_count": snapshot.elite_signal_count,
            "high_signal_count": snapshot.high_signal_count,
            "medium_signal_count": snapshot.medium_signal_count,
            "low_signal_count": snapshot.low_signal_count,
        },
        signal_snapshot_id=int(snapshot.id or 0),
    )
    append_market_feed_event(
        session,
        owner_user_id=owner_user_id,
        event_type="SNAPSHOT_CREATED",
        severity="INFO",
        snapshot_date=snapshot_date,
        event_payload_json={
            "layer": "signals",
            "signal_snapshot_id": int(snapshot.id or 0),
            "snapshot_checksum": snapshot_checksum,
        },
        signal_snapshot_id=int(snapshot.id or 0),
    )
    session.commit()
    session.refresh(snapshot)
    return MarketAcquisitionSignalGenerateResponse(
        replayed=False,
        snapshot=_snapshot_read(snapshot),
        total_signals=len(staged_rows),
    )


def list_signals_owner(
    session: Session,
    *,
    owner_user_id: int,
    signal_type: str | None = None,
    signal_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionSignalListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignal).where(MarketAcquisitionSignal.owner_user_id == owner_user_id)
    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_strength == signal_strength)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignal.snapshot_date).desc(),
                col(MarketAcquisitionSignal.signal_score).desc(),
                col(MarketAcquisitionSignal.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalListResponse(
        items=[_score_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_signals_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    signal_type: str | None = None,
    signal_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionSignalListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignal)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionSignal.owner_user_id == owner_user_id)
    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_strength == signal_strength)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignal.snapshot_date).desc(),
                col(MarketAcquisitionSignal.signal_score).desc(),
                col(MarketAcquisitionSignal.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalListResponse(
        items=[_score_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def _get_signal_owner_or_404(
    session: Session,
    *,
    owner_user_id: int,
    signal_id: int,
) -> MarketAcquisitionSignal:
    row = session.get(MarketAcquisitionSignal, signal_id)
    if row is None or int(row.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Market acquisition signal not found")
    return row


def _get_signal_ops_or_404(session: Session, *, signal_id: int) -> MarketAcquisitionSignal:
    row = session.get(MarketAcquisitionSignal, signal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market acquisition signal not found")
    return row


def get_signal_owner(
    session: Session,
    *,
    owner_user_id: int,
    signal_id: int,
) -> MarketAcquisitionSignalDetailRead:
    row = _get_signal_owner_or_404(session, owner_user_id=owner_user_id, signal_id=signal_id)
    evidence = list(
        session.exec(
            select(MarketAcquisitionSignalEvidence)
            .where(MarketAcquisitionSignalEvidence.market_acquisition_signal_id == int(row.id or 0))
            .order_by(col(MarketAcquisitionSignalEvidence.id).asc())
        ).all()
    )
    return MarketAcquisitionSignalDetailRead(
        signal=_score_read(row),
        evidence=[_evidence_read(item) for item in evidence],
    )


def get_signal_ops(session: Session, *, signal_id: int) -> MarketAcquisitionSignalDetailRead:
    row = _get_signal_ops_or_404(session, signal_id=signal_id)
    evidence = list(
        session.exec(
            select(MarketAcquisitionSignalEvidence)
            .where(MarketAcquisitionSignalEvidence.market_acquisition_signal_id == int(row.id or 0))
            .order_by(col(MarketAcquisitionSignalEvidence.id).asc())
        ).all()
    )
    return MarketAcquisitionSignalDetailRead(
        signal=_score_read(row),
        evidence=[_evidence_read(item) for item in evidence],
    )


def list_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionSignalSnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignalSnapshot).where(MarketAcquisitionSignalSnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignalSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignalSnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignalSnapshot.snapshot_date).desc(),
                col(MarketAcquisitionSignalSnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionSignalSnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignalSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionSignalSnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignalSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignalSnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignalSnapshot.snapshot_date).desc(),
                col(MarketAcquisitionSignalSnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    signal_type: str | None = None,
    signal_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    signal_id: int | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionSignalEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignalEvidence).join(
        MarketAcquisitionSignal,
        MarketAcquisitionSignalEvidence.market_acquisition_signal_id == MarketAcquisitionSignal.id,
    )
    stmt = stmt.where(MarketAcquisitionSignal.owner_user_id == owner_user_id)
    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_strength == signal_strength)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.risk_level == risk_level)
    if signal_id is not None:
        stmt = stmt.where(MarketAcquisitionSignalEvidence.market_acquisition_signal_id == signal_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignal.snapshot_date).desc(),
                col(MarketAcquisitionSignalEvidence.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalEvidenceListResponse(
        items=[_evidence_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    signal_type: str | None = None,
    signal_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    signal_id: int | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionSignalEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignalEvidence).join(
        MarketAcquisitionSignal,
        MarketAcquisitionSignalEvidence.market_acquisition_signal_id == MarketAcquisitionSignal.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionSignal.owner_user_id == owner_user_id)
    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionSignal.signal_strength == signal_strength)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionSignal.risk_level == risk_level)
    if signal_id is not None:
        stmt = stmt.where(MarketAcquisitionSignalEvidence.market_acquisition_signal_id == signal_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignal.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignal.snapshot_date).desc(),
                col(MarketAcquisitionSignalEvidence.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalEvidenceListResponse(
        items=[_evidence_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    signal_type: str | None = None,
    signal_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionSignalHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignalHistory).where(MarketAcquisitionSignalHistory.owner_user_id == owner_user_id)
    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.signal_strength == signal_strength)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignalHistory.snapshot_date).desc(),
                col(MarketAcquisitionSignalHistory.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalHistoryListResponse(
        items=[_history_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    signal_type: str | None = None,
    signal_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionSignalHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionSignalHistory)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.owner_user_id == owner_user_id)
    if signal_type is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.signal_type == signal_type)
    if signal_strength is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.signal_strength == signal_strength)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionSignalHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionSignalHistory.snapshot_date).desc(),
                col(MarketAcquisitionSignalHistory.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketAcquisitionSignalHistoryListResponse(
        items=[_history_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def inventory_market_signal_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryMarketAcquisitionSignalTeaser | None:
    issue_id = session.exec(
        select(ComicIssue.id)
        .join(Variant, Variant.comic_issue_id == ComicIssue.id)
        .join(InventoryCopy, InventoryCopy.variant_id == Variant.id)
        .where(
            InventoryCopy.user_id == owner_user_id,
            InventoryCopy.id == inventory_item_id,
        )
    ).first()
    if issue_id is None:
        return None
    signal_row = session.exec(
        select(MarketAcquisitionSignal)
        .join(MarketAcquisitionScore, MarketAcquisitionSignal.scored_candidate_id == MarketAcquisitionScore.id)
        .where(
            MarketAcquisitionSignal.owner_user_id == owner_user_id,
            MarketAcquisitionScore.canonical_comic_issue_id == int(issue_id),
        )
        .order_by(
            col(MarketAcquisitionSignal.snapshot_date).desc(),
            col(MarketAcquisitionSignal.signal_score).desc(),
            col(MarketAcquisitionSignal.id).desc(),
        )
    ).first()
    if signal_row is None:
        return None
    return InventoryMarketAcquisitionSignalTeaser(
        signal_type=str(signal_row.signal_type),
        signal_strength=str(signal_row.signal_strength),
        signal_score=str(_money(signal_row.signal_score)) if signal_row.signal_score is not None else None,
        confidence_level=str(signal_row.confidence_level),
        risk_level=str(signal_row.risk_level),
        snapshot_date=signal_row.snapshot_date,
    )
