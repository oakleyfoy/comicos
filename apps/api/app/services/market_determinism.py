"""P39-10 deterministic validation ledger and replay-safe integrity checks."""

from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    MarketAcquisitionCandidate,
    MarketAcquisitionIngestionBatch,
    MarketAcquisitionNormalizedCandidate,
    MarketAcquisitionNormalizationRun,
    MarketAcquisitionOpportunityItem,
    MarketAcquisitionOpportunitySnapshot,
    MarketAcquisitionRawSource,
    MarketAcquisitionScore,
    MarketAcquisitionScoreSnapshot,
    MarketAcquisitionSignal,
    MarketAcquisitionSignalSnapshot,
    MarketDeterminismChecksumAudit,
    MarketDeterminismInvariant,
    MarketDeterminismReplayAudit,
    MarketDeterminismValidationRun,
    MarketIntelligenceFeedEvent,
    MarketIntelligenceFeedSnapshot,
    PortfolioMarketCouplingEdge,
    PortfolioMarketCouplingSnapshot,
)
from app.schemas.market_determinism import (
    MarketDeterminismChecksumAuditRead,
    MarketDeterminismInvariantListResponse,
    MarketDeterminismInvariantRead,
    MarketDeterminismReplayAuditListResponse,
    MarketDeterminismReplayAuditRead,
    MarketDeterminismRunResponse,
    MarketDeterminismValidationRunListResponse,
    MarketDeterminismValidationRunPayload,
    MarketDeterminismValidationRunRead,
)
from app.services.market_feed import _aggregate_events
from app.services.market_ingestion import _hash_payload as _ingestion_hash_payload
from app.services.market_normalization import compute_run_checksum, deterministic_normalize_candidate
from app.services.market_opportunity import (
    PCT_QUANT,
    STRENGTH_SCORE_MAP,
    _bucket_to_numeric,
    _hash_payload as _opportunity_hash_payload,
    _money as _opportunity_money,
    _portfolio_impacts,
    _score_or_zero as _opportunity_score_or_zero,
    _signal_sort_key,
    classify_opportunity_portfolio_view,
)
from app.services.market_scoring import _hash_payload as _score_hash_payload
from app.services.market_signal import _hash_payload as _signal_hash_payload
from app.services.portfolio_market_coupling import (
    _derive_metrics_from_edges,
    _edge_sort_key,
    _hash_payload as _coupling_hash_payload,
    _load_portfolio_lines,
    _portfolio_aggregate,
    _summarize_opp_snap,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(k): _json_safe(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _status(*, failing: bool, warning: bool = False) -> str:
    if failing:
        return "FAIL"
    if warning:
        return "WARNING"
    return "PASS"


@dataclass(slots=True)
class _PipelineArtifacts:
    owner_user_id: int
    snapshot_date: date
    ingestion_batch: MarketAcquisitionIngestionBatch | None
    raw_sources: list[MarketAcquisitionRawSource]
    ingestion_candidates: list[MarketAcquisitionCandidate]
    normalization_run: MarketAcquisitionNormalizationRun | None
    normalized_candidates: list[MarketAcquisitionNormalizedCandidate]
    score_snapshot: MarketAcquisitionScoreSnapshot | None
    scores: list[MarketAcquisitionScore]
    signal_snapshot: MarketAcquisitionSignalSnapshot | None
    signals: list[MarketAcquisitionSignal]
    opportunity_snapshot: MarketAcquisitionOpportunitySnapshot | None
    opportunity_items: list[MarketAcquisitionOpportunityItem]
    coupling_snapshot: PortfolioMarketCouplingSnapshot | None
    coupling_edges: list[PortfolioMarketCouplingEdge]
    feed_snapshot: MarketIntelligenceFeedSnapshot | None
    feed_events: list[MarketIntelligenceFeedEvent]


@dataclass(slots=True)
class _ValidationArtifacts:
    pipeline_checksum: str
    checksum_rows: list[dict[str, Any]]
    invariant_rows: list[dict[str, Any]]
    replay_rows: list[dict[str, Any]]
    validation_status: str
    summary: dict[str, Any]


def _run_read(row: MarketDeterminismValidationRun) -> MarketDeterminismValidationRunRead:
    return MarketDeterminismValidationRunRead.model_validate(row, from_attributes=True)


def _invariant_read(row: MarketDeterminismInvariant) -> MarketDeterminismInvariantRead:
    return MarketDeterminismInvariantRead.model_validate(row, from_attributes=True)


def _checksum_read(row: MarketDeterminismChecksumAudit) -> MarketDeterminismChecksumAuditRead:
    return MarketDeterminismChecksumAuditRead.model_validate(row, from_attributes=True)


def _replay_read(row: MarketDeterminismReplayAudit) -> MarketDeterminismReplayAuditRead:
    return MarketDeterminismReplayAuditRead.model_validate(row, from_attributes=True)


def _latest_stmt(model: Any, *, owner_user_id: int, snapshot_date: date | None = None):
    stmt = select(model).where(model.owner_user_id == owner_user_id)
    if snapshot_date is not None and hasattr(model, "snapshot_date"):
        stmt = stmt.where(model.snapshot_date == snapshot_date)
    return stmt.order_by(
        getattr(model, "snapshot_date", col(model.id)).desc() if hasattr(model, "snapshot_date") else col(model.id).desc(),
        col(model.id).desc(),
    )


def _load_pipeline(session: Session, *, owner_user_id: int, snapshot_date: date | None) -> _PipelineArtifacts:
    coupling_snapshot = session.exec(
        _latest_stmt(
            PortfolioMarketCouplingSnapshot,
            owner_user_id=owner_user_id,
            snapshot_date=snapshot_date,
        )
    ).first()

    opportunity_snapshot: MarketAcquisitionOpportunitySnapshot | None = None
    signal_snapshot: MarketAcquisitionSignalSnapshot | None = None
    score_snapshot: MarketAcquisitionScoreSnapshot | None = None
    normalization_run: MarketAcquisitionNormalizationRun | None = None
    ingestion_batch: MarketAcquisitionIngestionBatch | None = None

    if coupling_snapshot is not None:
        opportunity_snapshot = session.get(
            MarketAcquisitionOpportunitySnapshot,
            int(coupling_snapshot.market_acquisition_opportunity_snapshot_id or 0),
        )
    if opportunity_snapshot is None:
        opportunity_snapshot = session.exec(
            _latest_stmt(
                MarketAcquisitionOpportunitySnapshot,
                owner_user_id=owner_user_id,
                snapshot_date=snapshot_date,
            )
        ).first()
    if opportunity_snapshot is not None:
        signal_snapshot = session.get(
            MarketAcquisitionSignalSnapshot,
            int(opportunity_snapshot.market_acquisition_signal_snapshot_id or 0),
        )
    if signal_snapshot is None:
        signal_snapshot = session.exec(
            _latest_stmt(
                MarketAcquisitionSignalSnapshot,
                owner_user_id=owner_user_id,
                snapshot_date=snapshot_date,
            )
        ).first()
    if signal_snapshot is not None:
        score_snapshot = session.get(
            MarketAcquisitionScoreSnapshot,
            int(signal_snapshot.market_acquisition_score_snapshot_id or 0),
        )
    if score_snapshot is None:
        score_snapshot = session.exec(
            _latest_stmt(MarketAcquisitionScoreSnapshot, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
        ).first()

    scores: list[MarketAcquisitionScore] = []
    normalized_candidates: list[MarketAcquisitionNormalizedCandidate] = []
    ingestion_candidates: list[MarketAcquisitionCandidate] = []
    raw_sources: list[MarketAcquisitionRawSource] = []
    signals: list[MarketAcquisitionSignal] = []
    opportunity_items: list[MarketAcquisitionOpportunityItem] = []
    coupling_edges: list[PortfolioMarketCouplingEdge] = []

    if score_snapshot is not None:
        scores = list(
            session.exec(
                select(MarketAcquisitionScore)
                .where(MarketAcquisitionScore.market_acquisition_score_snapshot_id == int(score_snapshot.id or 0))
                .order_by(
                    col(MarketAcquisitionScore.normalized_candidate_id).asc(),
                    col(MarketAcquisitionScore.id).asc(),
                )
            ).all()
        )
        candidate_ids = [int(row.normalized_candidate_id) for row in scores]
        if candidate_ids:
            normalized_candidates = list(
                session.exec(
                    select(MarketAcquisitionNormalizedCandidate)
                    .where(col(MarketAcquisitionNormalizedCandidate.id).in_(candidate_ids))
                    .order_by(col(MarketAcquisitionNormalizedCandidate.id).asc())
                ).all()
            )
            run_ids = sorted(
                {
                    int(row.normalization_run_id)
                    for row in normalized_candidates
                    if row.normalization_run_id is not None
                }
            )
            if len(run_ids) == 1:
                normalization_run = session.get(MarketAcquisitionNormalizationRun, run_ids[0])
            elif run_ids:
                normalization_run = session.get(MarketAcquisitionNormalizationRun, run_ids[-1])

    if normalization_run is not None:
        ingestion_batch = session.get(
            MarketAcquisitionIngestionBatch,
            int(normalization_run.ingestion_batch_id or 0),
        )
    if ingestion_batch is not None:
        ingestion_candidates = list(
            session.exec(
                select(MarketAcquisitionCandidate)
                .where(MarketAcquisitionCandidate.ingestion_batch_id == int(ingestion_batch.id or 0))
                .order_by(col(MarketAcquisitionCandidate.id).asc())
            ).all()
        )
        raw_sources = list(
            session.exec(
                select(MarketAcquisitionRawSource)
                .where(MarketAcquisitionRawSource.ingestion_batch_id == int(ingestion_batch.id or 0))
                .order_by(col(MarketAcquisitionRawSource.id).asc())
            ).all()
        )
        if not normalized_candidates:
            normalized_candidates = list(
                session.exec(
                    select(MarketAcquisitionNormalizedCandidate)
                    .where(MarketAcquisitionNormalizedCandidate.normalization_run_id == int(normalization_run.id or 0))
                    .order_by(col(MarketAcquisitionNormalizedCandidate.id).asc())
                ).all()
            ) if normalization_run is not None else []

    if signal_snapshot is not None:
        signals = list(
            session.exec(
                select(MarketAcquisitionSignal)
                .where(MarketAcquisitionSignal.market_acquisition_signal_snapshot_id == int(signal_snapshot.id or 0))
                .order_by(
                    col(MarketAcquisitionSignal.scored_candidate_id).asc(),
                    col(MarketAcquisitionSignal.signal_type).asc(),
                    col(MarketAcquisitionSignal.id).asc(),
                )
            ).all()
        )

    if opportunity_snapshot is not None:
        opportunity_items = list(
            session.exec(
                select(MarketAcquisitionOpportunityItem)
                .where(
                    MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
                    == int(opportunity_snapshot.id or 0)
                )
                .order_by(col(MarketAcquisitionOpportunityItem.id).asc())
            ).all()
        )

    if coupling_snapshot is not None:
        coupling_edges = list(
            session.exec(
                select(PortfolioMarketCouplingEdge)
                .where(
                    PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id
                    == int(coupling_snapshot.id or 0)
                )
                .order_by(col(PortfolioMarketCouplingEdge.id).asc())
            ).all()
        )

    resolved_snapshot_date = (
        snapshot_date
        or (coupling_snapshot.snapshot_date if coupling_snapshot is not None else None)
        or (opportunity_snapshot.snapshot_date if opportunity_snapshot is not None else None)
        or (signal_snapshot.snapshot_date if signal_snapshot is not None else None)
        or (score_snapshot.snapshot_date if score_snapshot is not None else None)
        or utc_now().date()
    )

    feed_snapshot = session.exec(
        select(MarketIntelligenceFeedSnapshot)
        .where(
            MarketIntelligenceFeedSnapshot.owner_user_id == owner_user_id,
            MarketIntelligenceFeedSnapshot.snapshot_date == resolved_snapshot_date,
        )
        .order_by(col(MarketIntelligenceFeedSnapshot.id).desc())
    ).first()
    if feed_snapshot is None:
        feed_snapshot = session.exec(
            _latest_stmt(MarketIntelligenceFeedSnapshot, owner_user_id=owner_user_id, snapshot_date=None)
        ).first()
    feed_events = list(
        session.exec(
            select(MarketIntelligenceFeedEvent)
            .where(MarketIntelligenceFeedEvent.owner_user_id == owner_user_id)
            .order_by(
                col(MarketIntelligenceFeedEvent.event_sequence_id).asc(),
                col(MarketIntelligenceFeedEvent.id).asc(),
            )
        ).all()
    )

    return _PipelineArtifacts(
        owner_user_id=owner_user_id,
        snapshot_date=resolved_snapshot_date,
        ingestion_batch=ingestion_batch,
        raw_sources=raw_sources,
        ingestion_candidates=ingestion_candidates,
        normalization_run=normalization_run,
        normalized_candidates=normalized_candidates,
        score_snapshot=score_snapshot,
        scores=scores,
        signal_snapshot=signal_snapshot,
        signals=signals,
        opportunity_snapshot=opportunity_snapshot,
        opportunity_items=opportunity_items,
        coupling_snapshot=coupling_snapshot,
        coupling_edges=coupling_edges,
        feed_snapshot=feed_snapshot,
        feed_events=feed_events,
    )


def _pipeline_checksum(artifacts: _PipelineArtifacts) -> str:
    return _ingestion_hash_payload(
        {
            "owner_user_id": artifacts.owner_user_id,
            "snapshot_date": artifacts.snapshot_date.isoformat(),
            "stages": {
                "ingestion": {
                    "id": int(artifacts.ingestion_batch.id or 0) if artifacts.ingestion_batch else None,
                    "checksum": artifacts.ingestion_batch.batch_checksum if artifacts.ingestion_batch else None,
                },
                "normalization": {
                    "id": int(artifacts.normalization_run.id or 0) if artifacts.normalization_run else None,
                    "checksum": artifacts.normalization_run.run_checksum if artifacts.normalization_run else None,
                },
                "scoring": {
                    "id": int(artifacts.score_snapshot.id or 0) if artifacts.score_snapshot else None,
                    "checksum": artifacts.score_snapshot.checksum if artifacts.score_snapshot else None,
                },
                "signals": {
                    "id": int(artifacts.signal_snapshot.id or 0) if artifacts.signal_snapshot else None,
                    "checksum": artifacts.signal_snapshot.checksum if artifacts.signal_snapshot else None,
                },
                "opportunity": {
                    "id": int(artifacts.opportunity_snapshot.id or 0) if artifacts.opportunity_snapshot else None,
                    "checksum": artifacts.opportunity_snapshot.snapshot_checksum if artifacts.opportunity_snapshot else None,
                },
                "coupling": {
                    "id": int(artifacts.coupling_snapshot.id or 0) if artifacts.coupling_snapshot else None,
                    "checksum": artifacts.coupling_snapshot.snapshot_checksum if artifacts.coupling_snapshot else None,
                },
                "feed": {
                    "id": int(artifacts.feed_snapshot.id or 0) if artifacts.feed_snapshot else None,
                    "checksum": artifacts.feed_snapshot.snapshot_checksum if artifacts.feed_snapshot else None,
                    "event_count": len(artifacts.feed_events),
                },
            },
            "row_fingerprints": {
                "raw_hashes": [row.raw_hash for row in artifacts.raw_sources],
                "normalized_keys": [row.canonical_key for row in artifacts.normalized_candidates],
                "score_checksums": [row.checksum for row in artifacts.scores],
                "signal_checksums": [row.checksum for row in artifacts.signals],
                "opportunity_items": [
                    {
                        "signal_id": int(row.market_acquisition_signal_id),
                        "candidate_id": int(row.candidate_id),
                        "weight": str(row.contribution_weight),
                    }
                    for row in artifacts.opportunity_items
                ],
                "coupling_edges": [
                    {
                        "candidate_id": int(row.market_normalized_candidate_id),
                        "opp_item_id": int(row.market_acquisition_opportunity_item_id),
                        "portfolio_item_id": int(row.portfolio_item_id)
                        if row.portfolio_item_id is not None
                        else None,
                        "type": row.coupling_type,
                        "strength": row.coupling_strength,
                        "score": int(row.coupling_score),
                    }
                    for row in artifacts.coupling_edges
                ],
                "feed_events": [
                    {
                        "sequence": int(row.event_sequence_id),
                        "checksum": row.event_checksum,
                    }
                    for row in artifacts.feed_events
                ],
            },
        }
    )


def _recompute_ingestion_checksum(artifacts: _PipelineArtifacts) -> str | None:
    if artifacts.ingestion_batch is None:
        return None
    return _ingestion_hash_payload(
        {
            "batch_source_type": artifacts.ingestion_batch.batch_source_type,
            "records": [row.raw_record_json for row in artifacts.raw_sources],
        }
    )


def _recompute_normalization_checksum(artifacts: _PipelineArtifacts) -> str | None:
    if artifacts.normalization_run is None:
        return None
    return compute_run_checksum(sorted(artifacts.ingestion_candidates, key=lambda row: int(row.id or 0)))


def _recompute_score_snapshot_checksum(artifacts: _PipelineArtifacts) -> str | None:
    if artifacts.score_snapshot is None:
        return None
    return _score_hash_payload(
        {
            "owner_user_id": artifacts.owner_user_id,
            "snapshot_date": artifacts.score_snapshot.snapshot_date,
            "scores": [
                {
                    "normalized_candidate_id": int(row.normalized_candidate_id),
                    "checksum": row.checksum,
                    "recommendation_label": row.recommendation_label,
                }
                for row in sorted(
                    artifacts.scores,
                    key=lambda row: (int(row.normalized_candidate_id), int(row.id or 0)),
                )
            ],
        }
    )


def _recompute_signal_snapshot_checksum(artifacts: _PipelineArtifacts) -> str | None:
    if artifacts.signal_snapshot is None or artifacts.score_snapshot is None:
        return None
    return _signal_hash_payload(
        {
            "owner_user_id": artifacts.owner_user_id,
            "market_acquisition_score_snapshot_id": int(artifacts.score_snapshot.id or 0),
            "source_score_snapshot_checksum": artifacts.score_snapshot.checksum,
            "signals": [
                {
                    "scored_candidate_id": int(row.scored_candidate_id),
                    "signal_type": row.signal_type,
                    "checksum": row.checksum,
                }
                for row in sorted(
                    artifacts.signals,
                    key=lambda row: (int(row.scored_candidate_id), str(row.signal_type)),
                )
            ],
        }
    )


def _recompute_opportunity_snapshot_checksum(artifacts: _PipelineArtifacts) -> str | None:
    if artifacts.opportunity_snapshot is None or artifacts.signal_snapshot is None:
        return None
    signal_map = {int(row.id or 0): row for row in artifacts.signals}
    score_map = {int(row.id or 0): row for row in artifacts.scores}
    signals = sorted(artifacts.signals, key=_signal_sort_key)
    staged = []
    for sig in signals:
        score = score_map.get(int(sig.scored_candidate_id or 0))
        if score is None:
            continue
        staged.append({"signal": sig, "candidate_id": int(score.normalized_candidate_id or 0), "score": score})
    total_signals = len(signals)
    strengths = [str(row.signal_strength) for row in signals]
    types_ = [str(row.signal_type) for row in signals]
    uniq_candidates = sorted({row["candidate_id"] for row in staged})
    value_dislocation_count = sum(1 for row in types_ if row == "VALUE_DISLOCATION")
    liquidity_opportunity_count = sum(1 for row in types_ if row == "LIQUIDITY_OPPORTUNITY")
    portfolio_gap_fill_count = sum(1 for row in types_ if row == "PORTFOLIO_GAP_FILL")
    concentration_reduction_count = sum(1 for row in types_ if row == "CONCENTRATION_REDUCTION")
    grading_upside_count = sum(1 for row in types_ if row == "GRADING_UPSIDE")
    redundant_asset_count = sum(1 for row in types_ if row == "REDUNDANT_ASSET")
    high_risk_asset_count = sum(1 for row in types_ if row == "HIGH_RISK_ASSET")

    acq_scores: list[Decimal] = []
    strengths_num: list[Decimal] = []
    confidence_num: list[Decimal] = []
    risk_num: list[Decimal] = []
    for row in staged:
        score = row["score"]
        acq_scores.append(_opportunity_score_or_zero(_opportunity_money(score.final_rank_score)))
        strengths_num.append(STRENGTH_SCORE_MAP.get(str(row["signal"].signal_strength), Decimal("50")))
        confidence_num.append(_bucket_to_numeric(str(score.confidence_level)))
        risk_num.append(_bucket_to_numeric(str(score.risk_level)))

    def _mean(values: list[Decimal]) -> Decimal | None:
        if not values:
            return None
        return (sum(values) / Decimal(len(values))).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)

    avg_acquisition_score = _mean(acq_scores)
    avg_signal_strength = _mean(strengths_num)
    avg_confidence_level = _mean(confidence_num)
    avg_risk_level = _mean(risk_num)
    est_gap_cov, est_liq, est_div, est_risk = _portfolio_impacts(signals, score_map)
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
    return _opportunity_hash_payload(
        {
            "owner_user_id": artifacts.owner_user_id,
            "market_acquisition_signal_snapshot_id": int(artifacts.signal_snapshot.id or 0),
            "source_signal_snapshot_checksum": artifacts.signal_snapshot.checksum,
            "opportunity_classification": classification,
            "totals": {
                "total_candidates": len(uniq_candidates),
                "total_signals": total_signals,
                "elite_signal_count": sum(1 for row in strengths if row == "ELITE"),
                "high_signal_count": sum(1 for row in strengths if row == "HIGH"),
                "medium_signal_count": sum(1 for row in strengths if row == "MEDIUM"),
                "low_signal_count": sum(1 for row in strengths if row == "LOW"),
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
                "avg_signal_strength": str(avg_signal_strength) if avg_signal_strength is not None else None,
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
                    "market_acquisition_signal_id": int(row["signal"].id or 0),
                    "signal_checksum": row["signal"].checksum,
                    "candidate_id": int(row["candidate_id"]),
                    "contribution_weight": str(
                        next(
                            (
                                item.contribution_weight
                                for item in artifacts.opportunity_items
                                if int(item.market_acquisition_signal_id) == int(row["signal"].id or 0)
                            ),
                            Decimal("0"),
                        )
                    ),
                }
                for row in staged
            ],
        }
    )


def _recompute_coupling_snapshot_checksum(session: Session, artifacts: _PipelineArtifacts) -> tuple[str | None, dict[str, Any]]:
    if artifacts.coupling_snapshot is None or artifacts.opportunity_snapshot is None:
        return None, {}
    portfolio_lines = _load_portfolio_lines(session, owner_user_id=artifacts.owner_user_id)
    _total_value, total_items = _portfolio_aggregate(session, owner_user_id=artifacts.owner_user_id)
    edge_payloads = [
        {
            "candidate_id": int(row.market_normalized_candidate_id),
            "market_acquisition_opportunity_item_id": int(row.market_acquisition_opportunity_item_id),
            "portfolio_item_id": int(row.portfolio_item_id) if row.portfolio_item_id is not None else None,
            "coupling_type": row.coupling_type,
            "coupling_strength": row.coupling_strength,
            "coupling_score": int(row.coupling_score),
            "explanation_json": _json_safe(row.explanation_json or {}),
        }
        for row in sorted(
            artifacts.coupling_edges,
            key=lambda row: _edge_sort_key(
                {
                    "candidate_id": int(row.market_normalized_candidate_id),
                    "market_acquisition_opportunity_item_id": int(row.market_acquisition_opportunity_item_id),
                    "portfolio_item_id": int(row.portfolio_item_id) if row.portfolio_item_id is not None else None,
                    "coupling_type": row.coupling_type,
                    "coupling_strength": row.coupling_strength,
                    "coupling_score": int(row.coupling_score),
                }
            ),
        )
    ]
    scores_by_candidate = {int(row.normalized_candidate_id): row for row in artifacts.scores}
    candidates_map = {int(row.id or 0): row for row in artifacts.normalized_candidates}
    opp_item_candidate_map = {int(row.id or 0): int(row.candidate_id) for row in artifacts.opportunity_items}
    metrics = _derive_metrics_from_edges(
        edge_payloads,
        opp_items_count=len(artifacts.opportunity_items),
        scores_by_candidate=scores_by_candidate,
        candidates=candidates_map,
        opp_item_candidate_map=opp_item_candidate_map,
    )
    payload = {
        "opportunity_snapshot": _summarize_opp_snap(artifacts.opportunity_snapshot),
        "portfolio_anchor": {
            "total_inventory_items": total_items,
            "lines": sorted(line.portfolio_item_id for line in portfolio_lines),
        },
        "edges": [_json_safe(row) for row in edge_payloads],
    }
    return _coupling_hash_payload(payload), metrics


def _recompute_feed_snapshot_checksum(artifacts: _PipelineArtifacts) -> str | None:
    if artifacts.feed_snapshot is None:
        return None
    _latest, _types, _severity, _heatmap, _failures, checksum = _aggregate_events(
        artifacts.feed_events,
        owner_user_id=artifacts.owner_user_id,
        snapshot_date=artifacts.feed_snapshot.snapshot_date,
    )
    return checksum


def _build_checksum_audits(session: Session, artifacts: _PipelineArtifacts) -> tuple[list[dict[str, Any]], str]:
    pipeline_checksum = _pipeline_checksum(artifacts)
    recomputed_coupling_checksum, coupling_metrics = _recompute_coupling_snapshot_checksum(session, artifacts)
    rows = [
        {
            "stage_name": "ingestion",
            "upstream_stage_name": None,
            "upstream_checksum": None,
            "current_checksum": artifacts.ingestion_batch.batch_checksum if artifacts.ingestion_batch else None,
            "validation_status": _status(
                failing=artifacts.ingestion_batch is None
                or _recompute_ingestion_checksum(artifacts) != artifacts.ingestion_batch.batch_checksum
            ),
            "detail_json": {
                "batch_id": int(artifacts.ingestion_batch.id or 0) if artifacts.ingestion_batch else None,
                "recomputed_checksum": _recompute_ingestion_checksum(artifacts),
                "raw_record_count": len(artifacts.raw_sources),
            },
        },
        {
            "stage_name": "normalization",
            "upstream_stage_name": "ingestion",
            "upstream_checksum": artifacts.ingestion_batch.batch_checksum if artifacts.ingestion_batch else None,
            "current_checksum": artifacts.normalization_run.run_checksum if artifacts.normalization_run else None,
            "validation_status": _status(
                failing=artifacts.normalization_run is None
                or artifacts.ingestion_batch is None
                or int(artifacts.normalization_run.ingestion_batch_id or 0) != int(artifacts.ingestion_batch.id or 0)
                or _recompute_normalization_checksum(artifacts) != artifacts.normalization_run.run_checksum
            ),
            "detail_json": {
                "normalization_run_id": int(artifacts.normalization_run.id or 0)
                if artifacts.normalization_run
                else None,
                "ingestion_batch_id": int(artifacts.normalization_run.ingestion_batch_id or 0)
                if artifacts.normalization_run
                else None,
                "recomputed_checksum": _recompute_normalization_checksum(artifacts),
            },
        },
        {
            "stage_name": "scoring",
            "upstream_stage_name": "normalization",
            "upstream_checksum": artifacts.normalization_run.run_checksum if artifacts.normalization_run else None,
            "current_checksum": artifacts.score_snapshot.checksum if artifacts.score_snapshot else None,
            "validation_status": _status(
                failing=artifacts.score_snapshot is None
                or _recompute_score_snapshot_checksum(artifacts) != artifacts.score_snapshot.checksum
            ),
            "detail_json": {
                "score_snapshot_id": int(artifacts.score_snapshot.id or 0) if artifacts.score_snapshot else None,
                "score_count": len(artifacts.scores),
                "recomputed_checksum": _recompute_score_snapshot_checksum(artifacts),
            },
        },
        {
            "stage_name": "signals",
            "upstream_stage_name": "scoring",
            "upstream_checksum": artifacts.score_snapshot.checksum if artifacts.score_snapshot else None,
            "current_checksum": artifacts.signal_snapshot.checksum if artifacts.signal_snapshot else None,
            "validation_status": _status(
                failing=artifacts.signal_snapshot is None
                or artifacts.score_snapshot is None
                or int(artifacts.signal_snapshot.market_acquisition_score_snapshot_id or 0)
                != int(artifacts.score_snapshot.id or 0)
                or _recompute_signal_snapshot_checksum(artifacts) != artifacts.signal_snapshot.checksum
            ),
            "detail_json": {
                "signal_snapshot_id": int(artifacts.signal_snapshot.id or 0) if artifacts.signal_snapshot else None,
                "signal_count": len(artifacts.signals),
                "recomputed_checksum": _recompute_signal_snapshot_checksum(artifacts),
            },
        },
        {
            "stage_name": "opportunity",
            "upstream_stage_name": "signals",
            "upstream_checksum": artifacts.signal_snapshot.checksum if artifacts.signal_snapshot else None,
            "current_checksum": artifacts.opportunity_snapshot.snapshot_checksum
            if artifacts.opportunity_snapshot
            else None,
            "validation_status": _status(
                failing=artifacts.opportunity_snapshot is None
                or artifacts.signal_snapshot is None
                or int(artifacts.opportunity_snapshot.market_acquisition_signal_snapshot_id or 0)
                != int(artifacts.signal_snapshot.id or 0)
                or _recompute_opportunity_snapshot_checksum(artifacts)
                != artifacts.opportunity_snapshot.snapshot_checksum
            ),
            "detail_json": {
                "opportunity_snapshot_id": int(artifacts.opportunity_snapshot.id or 0)
                if artifacts.opportunity_snapshot
                else None,
                "item_count": len(artifacts.opportunity_items),
                "recomputed_checksum": _recompute_opportunity_snapshot_checksum(artifacts),
            },
        },
        {
            "stage_name": "coupling",
            "upstream_stage_name": "opportunity",
            "upstream_checksum": artifacts.opportunity_snapshot.snapshot_checksum
            if artifacts.opportunity_snapshot
            else None,
            "current_checksum": artifacts.coupling_snapshot.snapshot_checksum if artifacts.coupling_snapshot else None,
            "validation_status": _status(
                failing=artifacts.coupling_snapshot is None
                or artifacts.opportunity_snapshot is None
                or int(artifacts.coupling_snapshot.market_acquisition_opportunity_snapshot_id or 0)
                != int(artifacts.opportunity_snapshot.id or 0)
                or recomputed_coupling_checksum != artifacts.coupling_snapshot.snapshot_checksum
            ),
            "detail_json": {
                "coupling_snapshot_id": int(artifacts.coupling_snapshot.id or 0)
                if artifacts.coupling_snapshot
                else None,
                "edge_count": len(artifacts.coupling_edges),
                "recomputed_checksum": recomputed_coupling_checksum,
                "recomputed_metrics": _json_safe(coupling_metrics),
            },
        },
        {
            "stage_name": "feed",
            "upstream_stage_name": "coupling",
            "upstream_checksum": artifacts.coupling_snapshot.snapshot_checksum if artifacts.coupling_snapshot else None,
            "current_checksum": artifacts.feed_snapshot.snapshot_checksum if artifacts.feed_snapshot else None,
            "validation_status": _status(
                failing=artifacts.feed_snapshot is None
                or _recompute_feed_snapshot_checksum(artifacts) != artifacts.feed_snapshot.snapshot_checksum
            ),
            "detail_json": {
                "feed_snapshot_id": int(artifacts.feed_snapshot.id or 0) if artifacts.feed_snapshot else None,
                "event_count": len(artifacts.feed_events),
                "recomputed_checksum": _recompute_feed_snapshot_checksum(artifacts),
            },
        },
    ]
    return rows, pipeline_checksum


def _build_invariants(session: Session, artifacts: _PipelineArtifacts) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    raw_hashes = [row.raw_hash for row in artifacts.raw_sources]
    raw_hash_recomputed = [
        _ingestion_hash_payload(_json_safe(row.raw_record_json)) == row.raw_hash for row in artifacts.raw_sources
    ]
    rows.append(
        {
            "layer_name": "ingestion",
            "invariant_code": "raw_hash_uniqueness",
            "invariant_status": _status(
                failing=len(raw_hashes) != len(set(raw_hashes)),
                warning=not raw_hashes,
            ),
            "expected_value_json": {"unique_raw_hashes": len(raw_hashes)},
            "actual_value_json": {"distinct_raw_hashes": len(set(raw_hashes))},
            "detail_json": {"batch_id": int(artifacts.ingestion_batch.id or 0) if artifacts.ingestion_batch else None},
        }
    )
    rows.append(
        {
            "layer_name": "ingestion",
            "invariant_code": "raw_hash_determinism",
            "invariant_status": _status(
                failing=any(not ok for ok in raw_hash_recomputed),
                warning=not raw_hash_recomputed,
            ),
            "expected_value_json": {"matching_hashes": len(raw_hash_recomputed)},
            "actual_value_json": {"matching_hashes": sum(1 for ok in raw_hash_recomputed if ok)},
            "detail_json": {"mismatch_count": sum(1 for ok in raw_hash_recomputed if not ok)},
        }
    )

    normalized_by_candidate = {
        int(row.ingestion_candidate_id): row for row in artifacts.normalized_candidates
    }
    normalization_mismatches = 0
    for candidate in artifacts.ingestion_candidates:
        normalized_row = normalized_by_candidate.get(int(candidate.id or 0))
        if normalized_row is None:
            normalization_mismatches += 1
            continue
        derived = deterministic_normalize_candidate(candidate)
        if (
            derived["canonical_key"] != normalized_row.canonical_key
            or derived["normalization_status"] != normalized_row.normalization_status
        ):
            normalization_mismatches += 1
    rows.append(
        {
            "layer_name": "normalization",
            "invariant_code": "canonical_key_stability",
            "invariant_status": _status(
                failing=normalization_mismatches > 0,
                warning=not artifacts.ingestion_candidates,
            ),
            "expected_value_json": {"candidate_count": len(artifacts.ingestion_candidates)},
            "actual_value_json": {"stable_candidates": len(artifacts.ingestion_candidates) - normalization_mismatches},
            "detail_json": {"mismatch_count": normalization_mismatches},
        }
    )

    score_groups: dict[str, set[tuple[str | None, str]]] = defaultdict(set)
    for row in artifacts.scores:
        score_groups[row.checksum].add(
            (
                str(row.final_rank_score) if row.final_rank_score is not None else None,
                str(row.recommendation_label),
            )
        )
    score_mismatch = sum(1 for values in score_groups.values() if len(values) > 1)
    rows.append(
        {
            "layer_name": "scoring",
            "invariant_code": "identical_candidate_identical_score",
            "invariant_status": _status(failing=score_mismatch > 0, warning=not artifacts.scores),
            "expected_value_json": {"checksum_groups": len(score_groups)},
            "actual_value_json": {"stable_groups": len(score_groups) - score_mismatch},
            "detail_json": {"mismatch_groups": score_mismatch},
        }
    )

    score_by_id = {int(row.id or 0): row for row in artifacts.scores}
    signal_groups: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for row in artifacts.signals:
        score = score_by_id.get(int(row.scored_candidate_id or 0))
        if score is None:
            continue
        signal_groups[score.checksum].add((row.signal_type, row.signal_strength, row.checksum))
    signal_mismatch = sum(1 for values in signal_groups.values() if len(values) > 1)
    rows.append(
        {
            "layer_name": "signals",
            "invariant_code": "identical_score_identical_signal",
            "invariant_status": _status(failing=signal_mismatch > 0, warning=not artifacts.signals),
            "expected_value_json": {"score_groups": len(signal_groups)},
            "actual_value_json": {"stable_groups": len(signal_groups) - signal_mismatch},
            "detail_json": {"mismatch_groups": signal_mismatch},
        }
    )

    opp_signal_ids = [int(row.market_acquisition_signal_id) for row in artifacts.opportunity_items]
    rows.append(
        {
            "layer_name": "opportunity",
            "invariant_code": "identical_signals_identical_grouping",
            "invariant_status": _status(
                failing=len(opp_signal_ids) != len(set(opp_signal_ids))
                or (
                    artifacts.opportunity_snapshot is not None
                    and _recompute_opportunity_snapshot_checksum(artifacts)
                    != artifacts.opportunity_snapshot.snapshot_checksum
                ),
                warning=artifacts.opportunity_snapshot is None,
            ),
            "expected_value_json": {"item_count": len(opp_signal_ids)},
            "actual_value_json": {"distinct_signal_ids": len(set(opp_signal_ids))},
            "detail_json": {
                "recomputed_checksum": _recompute_opportunity_snapshot_checksum(artifacts),
                "snapshot_checksum": artifacts.opportunity_snapshot.snapshot_checksum
                if artifacts.opportunity_snapshot
                else None,
            },
        }
    )

    edge_payloads = [
        {
            "candidate_id": int(row.market_normalized_candidate_id),
            "market_acquisition_opportunity_item_id": int(row.market_acquisition_opportunity_item_id),
            "portfolio_item_id": int(row.portfolio_item_id) if row.portfolio_item_id is not None else None,
            "coupling_type": row.coupling_type,
            "coupling_strength": row.coupling_strength,
            "coupling_score": int(row.coupling_score),
        }
        for row in artifacts.coupling_edges
    ]
    stored_edge_order = [tuple(_json_safe(row).values()) for row in edge_payloads]
    sorted_edge_order = [tuple(_json_safe(row).values()) for row in sorted(edge_payloads, key=_edge_sort_key)]
    recomputed_coupling_checksum, coupling_metrics = _recompute_coupling_snapshot_checksum(session, artifacts)
    rows.append(
        {
            "layer_name": "coupling",
            "invariant_code": "stable_edge_ordering",
            "invariant_status": _status(
                failing=stored_edge_order != sorted_edge_order,
                warning=artifacts.coupling_snapshot is None,
            ),
            "expected_value_json": {"edge_count": len(sorted_edge_order)},
            "actual_value_json": {"edge_count": len(stored_edge_order)},
            "detail_json": {"ordering_changed": stored_edge_order != sorted_edge_order},
        }
    )
    rows.append(
        {
            "layer_name": "coupling",
            "invariant_code": "stable_alignment_metrics",
            "invariant_status": _status(
                failing=artifacts.coupling_snapshot is None
                or recomputed_coupling_checksum != artifacts.coupling_snapshot.snapshot_checksum
                or int(coupling_metrics.get("aligned_opportunity_count", -1))
                != int(artifacts.coupling_snapshot.aligned_opportunity_count or 0),
                warning=artifacts.coupling_snapshot is None,
            ),
            "expected_value_json": _json_safe(coupling_metrics),
            "actual_value_json": {
                "aligned_opportunity_count": artifacts.coupling_snapshot.aligned_opportunity_count
                if artifacts.coupling_snapshot
                else None,
                "misaligned_opportunity_count": artifacts.coupling_snapshot.misaligned_opportunity_count
                if artifacts.coupling_snapshot
                else None,
                "high_fit_market_items": artifacts.coupling_snapshot.high_fit_market_items
                if artifacts.coupling_snapshot
                else None,
                "portfolio_market_alignment_score": (
                    str(artifacts.coupling_snapshot.portfolio_market_alignment_score)
                    if artifacts.coupling_snapshot
                    and artifacts.coupling_snapshot.portfolio_market_alignment_score is not None
                    else None
                ),
            },
            "detail_json": {"recomputed_checksum": recomputed_coupling_checksum},
        }
    )

    ordering_ok = True
    expected_sequence = 1
    for row in artifacts.feed_events:
        if int(row.event_sequence_id) != expected_sequence:
            ordering_ok = False
            break
        expected_sequence += 1
    rows.append(
        {
            "layer_name": "feed",
            "invariant_code": "stable_event_ordering",
            "invariant_status": _status(failing=not ordering_ok, warning=not artifacts.feed_events),
            "expected_value_json": {"event_count": len(artifacts.feed_events)},
            "actual_value_json": {"last_sequence_id": artifacts.feed_events[-1].event_sequence_id if artifacts.feed_events else 0},
            "detail_json": {"contiguous_sequences": ordering_ok},
        }
    )
    rows.append(
        {
            "layer_name": "feed",
            "invariant_code": "stable_replay_reconstruction",
            "invariant_status": _status(
                failing=artifacts.feed_snapshot is None
                or _recompute_feed_snapshot_checksum(artifacts) != artifacts.feed_snapshot.snapshot_checksum,
                warning=artifacts.feed_snapshot is None,
            ),
            "expected_value_json": {"recomputed_checksum": _recompute_feed_snapshot_checksum(artifacts)},
            "actual_value_json": {
                "snapshot_checksum": artifacts.feed_snapshot.snapshot_checksum if artifacts.feed_snapshot else None
            },
            "detail_json": {"feed_snapshot_id": int(artifacts.feed_snapshot.id or 0) if artifacts.feed_snapshot else None},
        }
    )
    return rows


def _build_replay_audits(session: Session, artifacts: _PipelineArtifacts, *, pipeline_checksum: str) -> list[dict[str, Any]]:
    recomputed_coupling_checksum, coupling_metrics = _recompute_coupling_snapshot_checksum(session, artifacts)
    event_checksum_ok = True
    event_mismatch_ids: list[int] = []
    expected_sequence = 1
    for row in artifacts.feed_events:
        recomputed = _hash_payload(
            {
                "owner_user_id": row.owner_user_id,
                "event_type": row.event_type,
                "severity": row.severity,
                "snapshot_date": row.snapshot_date,
                "ingestion_batch_id": row.ingestion_batch_id,
                "normalization_run_id": row.normalization_run_id,
                "scoring_run_id": row.scoring_run_id,
                "signal_snapshot_id": row.signal_snapshot_id,
                "opportunity_snapshot_id": row.opportunity_snapshot_id,
                "coupling_snapshot_id": row.coupling_snapshot_id,
                "event_payload_json": row.event_payload_json,
            }
        )
        if recomputed != row.event_checksum or int(row.event_sequence_id) != expected_sequence:
            event_checksum_ok = False
            event_mismatch_ids.append(int(row.id or 0))
        expected_sequence += 1

    return [
        {
            "artifact_type": "INGESTION_BATCH",
            "artifact_key": str(int(artifacts.ingestion_batch.id or 0)) if artifacts.ingestion_batch else "missing",
            "replay_status": _status(
                failing=artifacts.ingestion_batch is None
                or _recompute_ingestion_checksum(artifacts) != artifacts.ingestion_batch.batch_checksum
            ),
            "original_checksum": artifacts.ingestion_batch.batch_checksum if artifacts.ingestion_batch else None,
            "replay_checksum": _recompute_ingestion_checksum(artifacts),
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"raw_record_count": len(artifacts.raw_sources)},
        },
        {
            "artifact_type": "NORMALIZATION_RUN",
            "artifact_key": str(int(artifacts.normalization_run.id or 0)) if artifacts.normalization_run else "missing",
            "replay_status": _status(
                failing=artifacts.normalization_run is None
                or _recompute_normalization_checksum(artifacts) != artifacts.normalization_run.run_checksum
            ),
            "original_checksum": artifacts.normalization_run.run_checksum if artifacts.normalization_run else None,
            "replay_checksum": _recompute_normalization_checksum(artifacts),
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"candidate_count": len(artifacts.ingestion_candidates)},
        },
        {
            "artifact_type": "SCORE_SNAPSHOT",
            "artifact_key": str(int(artifacts.score_snapshot.id or 0)) if artifacts.score_snapshot else "missing",
            "replay_status": _status(
                failing=artifacts.score_snapshot is None
                or _recompute_score_snapshot_checksum(artifacts) != artifacts.score_snapshot.checksum
            ),
            "original_checksum": artifacts.score_snapshot.checksum if artifacts.score_snapshot else None,
            "replay_checksum": _recompute_score_snapshot_checksum(artifacts),
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"score_count": len(artifacts.scores)},
        },
        {
            "artifact_type": "SIGNAL_SNAPSHOT",
            "artifact_key": str(int(artifacts.signal_snapshot.id or 0)) if artifacts.signal_snapshot else "missing",
            "replay_status": _status(
                failing=artifacts.signal_snapshot is None
                or _recompute_signal_snapshot_checksum(artifacts) != artifacts.signal_snapshot.checksum
            ),
            "original_checksum": artifacts.signal_snapshot.checksum if artifacts.signal_snapshot else None,
            "replay_checksum": _recompute_signal_snapshot_checksum(artifacts),
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"signal_count": len(artifacts.signals)},
        },
        {
            "artifact_type": "OPPORTUNITY_SNAPSHOT",
            "artifact_key": str(int(artifacts.opportunity_snapshot.id or 0)) if artifacts.opportunity_snapshot else "missing",
            "replay_status": _status(
                failing=artifacts.opportunity_snapshot is None
                or _recompute_opportunity_snapshot_checksum(artifacts)
                != artifacts.opportunity_snapshot.snapshot_checksum
            ),
            "original_checksum": artifacts.opportunity_snapshot.snapshot_checksum
            if artifacts.opportunity_snapshot
            else None,
            "replay_checksum": _recompute_opportunity_snapshot_checksum(artifacts),
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"item_count": len(artifacts.opportunity_items)},
        },
        {
            "artifact_type": "COUPLING_SNAPSHOT",
            "artifact_key": str(int(artifacts.coupling_snapshot.id or 0)) if artifacts.coupling_snapshot else "missing",
            "replay_status": _status(
                failing=artifacts.coupling_snapshot is None
                or recomputed_coupling_checksum != artifacts.coupling_snapshot.snapshot_checksum
            ),
            "original_checksum": artifacts.coupling_snapshot.snapshot_checksum if artifacts.coupling_snapshot else None,
            "replay_checksum": recomputed_coupling_checksum,
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"metrics": _json_safe(coupling_metrics), "edge_count": len(artifacts.coupling_edges)},
        },
        {
            "artifact_type": "FEED_EVENT_STREAM",
            "artifact_key": str(len(artifacts.feed_events)),
            "replay_status": _status(failing=not event_checksum_ok, warning=not artifacts.feed_events),
            "original_checksum": artifacts.feed_events[-1].event_checksum if artifacts.feed_events else None,
            "replay_checksum": artifacts.feed_events[-1].event_checksum if event_checksum_ok and artifacts.feed_events else None,
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"mismatch_event_ids": event_mismatch_ids},
        },
        {
            "artifact_type": "FEED_SNAPSHOT",
            "artifact_key": str(int(artifacts.feed_snapshot.id or 0)) if artifacts.feed_snapshot else "missing",
            "replay_status": _status(
                failing=artifacts.feed_snapshot is None
                or _recompute_feed_snapshot_checksum(artifacts) != artifacts.feed_snapshot.snapshot_checksum
            ),
            "original_checksum": artifacts.feed_snapshot.snapshot_checksum if artifacts.feed_snapshot else None,
            "replay_checksum": _recompute_feed_snapshot_checksum(artifacts),
            "pipeline_checksum": pipeline_checksum,
            "detail_json": {"event_count": len(artifacts.feed_events)},
        },
    ]


def _evaluate_validation(session: Session, *, owner_user_id: int, snapshot_date: date | None) -> _ValidationArtifacts:
    artifacts = _load_pipeline(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
    checksum_rows, pipeline_checksum = _build_checksum_audits(session, artifacts)
    invariant_rows = _build_invariants(session, artifacts)
    replay_rows = _build_replay_audits(session, artifacts, pipeline_checksum=pipeline_checksum)

    fail_count = sum(1 for row in checksum_rows if row["validation_status"] == "FAIL")
    fail_count += sum(1 for row in invariant_rows if row["invariant_status"] == "FAIL")
    fail_count += sum(1 for row in replay_rows if row["replay_status"] == "FAIL")
    warning_count = sum(1 for row in checksum_rows if row["validation_status"] == "WARNING")
    warning_count += sum(1 for row in invariant_rows if row["invariant_status"] == "WARNING")
    warning_count += sum(1 for row in replay_rows if row["replay_status"] == "WARNING")

    summary = {
        "snapshot_date": artifacts.snapshot_date.isoformat(),
        "stages_present": {
            "ingestion": artifacts.ingestion_batch is not None,
            "normalization": artifacts.normalization_run is not None,
            "scoring": artifacts.score_snapshot is not None,
            "signals": artifacts.signal_snapshot is not None,
            "opportunity": artifacts.opportunity_snapshot is not None,
            "coupling": artifacts.coupling_snapshot is not None,
            "feed": artifacts.feed_snapshot is not None,
        },
        "counts": {
            "checksum_audits": len(checksum_rows),
            "invariants": len(invariant_rows),
            "replay_audits": len(replay_rows),
            "failures": fail_count,
            "warnings": warning_count,
        },
    }
    return _ValidationArtifacts(
        pipeline_checksum=pipeline_checksum,
        checksum_rows=checksum_rows,
        invariant_rows=invariant_rows,
        replay_rows=replay_rows,
        validation_status="FAIL" if fail_count else ("WARNING" if warning_count else "PASS"),
        summary=summary,
    )


def _load_run_bundle(
    session: Session,
    *,
    run_row: MarketDeterminismValidationRun,
) -> MarketDeterminismRunResponse:
    invariants = list(
        session.exec(
            select(MarketDeterminismInvariant)
            .where(MarketDeterminismInvariant.market_determinism_validation_run_id == int(run_row.id or 0))
            .order_by(
                col(MarketDeterminismInvariant.layer_name).asc(),
                col(MarketDeterminismInvariant.invariant_code).asc(),
                col(MarketDeterminismInvariant.id).asc(),
            )
        ).all()
    )
    checksum_rows = list(
        session.exec(
            select(MarketDeterminismChecksumAudit)
            .where(MarketDeterminismChecksumAudit.market_determinism_validation_run_id == int(run_row.id or 0))
            .order_by(col(MarketDeterminismChecksumAudit.id).asc())
        ).all()
    )
    replay_rows = list(
        session.exec(
            select(MarketDeterminismReplayAudit)
            .where(MarketDeterminismReplayAudit.market_determinism_validation_run_id == int(run_row.id or 0))
            .order_by(col(MarketDeterminismReplayAudit.id).asc())
        ).all()
    )
    return MarketDeterminismRunResponse(
        replayed=False,
        run=_run_read(run_row),
        checksum_audits=[_checksum_read(row) for row in checksum_rows],
        invariants=[_invariant_read(row) for row in invariants],
        replay_audits=[_replay_read(row) for row in replay_rows],
    )


def run_market_validation(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketDeterminismValidationRunPayload,
) -> tuple[MarketDeterminismRunResponse, bool]:
    evaluated = _evaluate_validation(
        session,
        owner_user_id=owner_user_id,
        snapshot_date=payload.snapshot_date,
    )
    validation_checksum = _ingestion_hash_payload(
        {
            "owner_user_id": owner_user_id,
            "snapshot_date": payload.snapshot_date.isoformat() if payload.snapshot_date is not None else None,
            "pipeline_checksum": evaluated.pipeline_checksum,
        }
    )
    existing = session.exec(
        select(MarketDeterminismValidationRun)
        .where(
            MarketDeterminismValidationRun.owner_user_id == owner_user_id,
            MarketDeterminismValidationRun.validation_checksum == validation_checksum,
        )
        .order_by(col(MarketDeterminismValidationRun.id).desc())
    ).first()
    if existing is not None:
        bundle = _load_run_bundle(session, run_row=existing)
        bundle.replayed = True
        return bundle, False

    run_row = MarketDeterminismValidationRun(
        owner_user_id=owner_user_id,
        validation_status=evaluated.validation_status,
        validation_checksum=validation_checksum,
        pipeline_checksum=evaluated.pipeline_checksum,
        snapshot_date=payload.snapshot_date or date.fromisoformat(evaluated.summary["snapshot_date"]),
        total_stages_checked=len(evaluated.checksum_rows),
        total_invariants_checked=len(evaluated.invariant_rows),
        total_replays_checked=len(evaluated.replay_rows),
        invariant_failure_count=sum(
            1 for row in evaluated.invariant_rows if row["invariant_status"] == "FAIL"
        ),
        checksum_mismatch_count=sum(
            1 for row in evaluated.checksum_rows if row["validation_status"] == "FAIL"
        ),
        replay_failure_count=sum(1 for row in evaluated.replay_rows if row["replay_status"] == "FAIL"),
        ordering_failure_count=sum(
            1
            for row in evaluated.invariant_rows
            if row["invariant_code"] in {"stable_edge_ordering", "stable_event_ordering"}
            and row["invariant_status"] == "FAIL"
        ),
        validation_summary_json=_json_safe(evaluated.summary),
        created_at=utc_now(),
    )
    session.add(run_row)
    session.flush()

    run_id = int(run_row.id or 0)
    for row in evaluated.invariant_rows:
        session.add(
            MarketDeterminismInvariant(
                market_determinism_validation_run_id=run_id,
                owner_user_id=owner_user_id,
                layer_name=str(row["layer_name"]),
                invariant_code=str(row["invariant_code"]),
                invariant_status=str(row["invariant_status"]),
                expected_value_json=_json_safe(row.get("expected_value_json")),
                actual_value_json=_json_safe(row.get("actual_value_json")),
                detail_json=_json_safe(row.get("detail_json") or {}),
                created_at=utc_now(),
            )
        )
    for row in evaluated.checksum_rows:
        session.add(
            MarketDeterminismChecksumAudit(
                market_determinism_validation_run_id=run_id,
                owner_user_id=owner_user_id,
                stage_name=str(row["stage_name"]),
                upstream_stage_name=row.get("upstream_stage_name"),
                validation_status=str(row["validation_status"]),
                upstream_checksum=row.get("upstream_checksum"),
                current_checksum=row.get("current_checksum"),
                pipeline_checksum=evaluated.pipeline_checksum,
                detail_json=_json_safe(row.get("detail_json") or {}),
                created_at=utc_now(),
            )
        )
    for row in evaluated.replay_rows:
        session.add(
            MarketDeterminismReplayAudit(
                market_determinism_validation_run_id=run_id,
                owner_user_id=owner_user_id,
                artifact_type=str(row["artifact_type"]),
                artifact_key=str(row["artifact_key"]),
                replay_status=str(row["replay_status"]),
                original_checksum=row.get("original_checksum"),
                replay_checksum=row.get("replay_checksum"),
                pipeline_checksum=evaluated.pipeline_checksum,
                detail_json=_json_safe(row.get("detail_json") or {}),
                created_at=utc_now(),
            )
        )
    session.commit()
    session.refresh(run_row)
    return _load_run_bundle(session, run_row=run_row), True


def _get_validation_run_owner_or_404(
    session: Session,
    *,
    owner_user_id: int,
    validation_run_id: int,
) -> MarketDeterminismValidationRun:
    row = session.get(MarketDeterminismValidationRun, validation_run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="market determinism validation run not found")
    return row


def get_validation_run_owner(
    session: Session,
    *,
    owner_user_id: int,
    validation_run_id: int,
) -> MarketDeterminismRunResponse:
    return _load_run_bundle(
        session,
        run_row=_get_validation_run_owner_or_404(
            session,
            owner_user_id=owner_user_id,
            validation_run_id=validation_run_id,
        ),
    )


def get_validation_run_ops(
    session: Session,
    *,
    validation_run_id: int,
    owner_user_id: int | None = None,
) -> MarketDeterminismRunResponse:
    row = session.get(MarketDeterminismValidationRun, validation_run_id)
    if row is None or (owner_user_id is not None and int(row.owner_user_id) != owner_user_id):
        raise HTTPException(status_code=404, detail="market determinism validation run not found")
    return _load_run_bundle(session, run_row=row)


def list_validation_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    validation_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketDeterminismValidationRunListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketDeterminismValidationRun).where(
        MarketDeterminismValidationRun.owner_user_id == owner_user_id
    )
    if validation_status:
        stmt = stmt.where(MarketDeterminismValidationRun.validation_status == validation_status)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketDeterminismValidationRun.snapshot_date).desc(),
                col(MarketDeterminismValidationRun.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketDeterminismValidationRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_validation_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    validation_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketDeterminismValidationRunListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketDeterminismValidationRun)
    if owner_user_id is not None:
        stmt = stmt.where(MarketDeterminismValidationRun.owner_user_id == owner_user_id)
    if validation_status:
        stmt = stmt.where(MarketDeterminismValidationRun.validation_status == validation_status)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketDeterminismValidationRun.snapshot_date).desc(),
                col(MarketDeterminismValidationRun.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketDeterminismValidationRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_invariants_owner(
    session: Session,
    *,
    owner_user_id: int,
    validation_run_id: int | None = None,
    invariant_status: str | None = None,
    layer_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketDeterminismInvariantListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketDeterminismInvariant).where(MarketDeterminismInvariant.owner_user_id == owner_user_id)
    if validation_run_id is not None:
        stmt = stmt.where(MarketDeterminismInvariant.market_determinism_validation_run_id == validation_run_id)
    if invariant_status:
        stmt = stmt.where(MarketDeterminismInvariant.invariant_status == invariant_status)
    if layer_name:
        stmt = stmt.where(MarketDeterminismInvariant.layer_name == layer_name)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketDeterminismInvariant.created_at).desc(),
                col(MarketDeterminismInvariant.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketDeterminismInvariantListResponse(
        items=[_invariant_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_invariants_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    validation_run_id: int | None = None,
    invariant_status: str | None = None,
    layer_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketDeterminismInvariantListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketDeterminismInvariant)
    if owner_user_id is not None:
        stmt = stmt.where(MarketDeterminismInvariant.owner_user_id == owner_user_id)
    if validation_run_id is not None:
        stmt = stmt.where(MarketDeterminismInvariant.market_determinism_validation_run_id == validation_run_id)
    if invariant_status:
        stmt = stmt.where(MarketDeterminismInvariant.invariant_status == invariant_status)
    if layer_name:
        stmt = stmt.where(MarketDeterminismInvariant.layer_name == layer_name)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketDeterminismInvariant.created_at).desc(),
                col(MarketDeterminismInvariant.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketDeterminismInvariantListResponse(
        items=[_invariant_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_replay_audits_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    validation_run_id: int | None = None,
    replay_status: str | None = None,
    artifact_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketDeterminismReplayAuditListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketDeterminismReplayAudit)
    if owner_user_id is not None:
        stmt = stmt.where(MarketDeterminismReplayAudit.owner_user_id == owner_user_id)
    if validation_run_id is not None:
        stmt = stmt.where(MarketDeterminismReplayAudit.market_determinism_validation_run_id == validation_run_id)
    if replay_status:
        stmt = stmt.where(MarketDeterminismReplayAudit.replay_status == replay_status)
    if artifact_type:
        stmt = stmt.where(MarketDeterminismReplayAudit.artifact_type == artifact_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketDeterminismReplayAudit.created_at).desc(),
                col(MarketDeterminismReplayAudit.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketDeterminismReplayAuditListResponse(
        items=[_replay_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )
