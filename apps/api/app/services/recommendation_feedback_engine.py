"""P73-03 recommendation feedback intelligence engine (observe / measure / calibrate)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone

from sqlmodel import Session, select, func

from app.models.p70_market_refresh import P70MarketFmvTrendPoint, P70MarketRefreshRun
from app.models.p72_grading_analytics import P72GradingOutcome
from app.models.recommendation_feedback_snapshot import (
    P73RecommendationCategoryCalibrationSnapshot,
    P73RecommendationEffectivenessSnapshot,
    P73RecommendationFeedbackBundleSnapshot,
)
from app.models.recommendation_outcome import P73RecommendationOutcome
from app.schemas.recommendation_analytics import P73RecommendationAccuracyMetricsRead
from app.schemas.recommendation_feedback_intelligence import (
    P73CategoryCalibrationRead,
    P73GradingContextRead,
    P73MarketContextRead,
    P73RecommendationConfidenceRead,
    P73RecommendationEffectivenessRead,
    P73RecommendationQualityDashboardRead,
    P73TypeEffectivenessRead,
)
from app.services.recommendation_analytics_service import (
    _float_roi,
    _load_owner_data,
    _normalize_rec_type,
    _pct,
    build_category_performance_read,
    build_profitability_read,
)
from app.services.recommendation_confidence_service import (
    build_recommendation_confidence,
    persist_confidence_snapshot,
)

P73_CALIBRATION_CATEGORIES = (
    "FIRST_APPEARANCE",
    "KEY_ISSUE",
    "VARIANT",
    "CREATOR",
    "PUBLISHER_EVENT",
    "MILESTONE_ISSUE",
    "FRANCHISE_EXPANSION",
)


def _normalize_calibration_category(raw: str) -> str:
    key = (raw or "GENERAL").strip().upper().replace(" ", "_")
    aliases = {
        "CREATOR_EVENT": "CREATOR",
        "FIRST_APP": "FIRST_APPEARANCE",
        "KEY": "KEY_ISSUE",
        "MILESTONE": "MILESTONE_ISSUE",
        "FRANCHISE": "FRANCHISE_EXPANSION",
    }
    key = aliases.get(key, key)
    if key in P73_CALIBRATION_CATEGORIES:
        return key
    if key == "GENERAL":
        return "KEY_ISSUE"
    return "KEY_ISSUE"


def _accuracy_label(expected: float, actual: float) -> str:
    if expected <= 0 and actual <= 0:
        return "MEDIUM"
    denom = max(abs(expected), 1.0)
    delta = abs(actual - expected) / denom
    if delta <= 0.15:
        return "HIGH"
    if delta <= 0.35:
        return "MEDIUM"
    return "LOW"


def load_market_context(session: Session, *, owner_user_id: int) -> P73MarketContextRead:
    trend_count = int(
        session.exec(
            select(func.count()).select_from(P70MarketFmvTrendPoint).where(
                P70MarketFmvTrendPoint.owner_user_id == owner_user_id
            )
        ).one()
    )
    run_count = int(
        session.exec(
            select(func.count()).select_from(P70MarketRefreshRun).where(
                P70MarketRefreshRun.owner_user_id == owner_user_id
            )
        ).one()
    )
    strength = min(100.0, trend_count * 2.0 + run_count * 5.0)
    return P73MarketContextRead(
        fmv_trend_point_count=trend_count,
        market_refresh_run_count=run_count,
        market_signal_strength=strength,
    )


def load_grading_context(session: Session, *, owner_user_id: int) -> P73GradingContextRead:
    rows = list(
        session.exec(select(P72GradingOutcome).where(P72GradingOutcome.owner_user_id == owner_user_id)).all()
    )
    if not rows:
        return P73GradingContextRead(
            grading_outcome_count=0,
            grading_hit_rate_pct=0.0,
            grading_avg_actual_roi_pct=0.0,
        )
    hits = sum(1 for r in rows if r.recommendation_accuracy.upper() in {"HIT", "ACCURATE", "HIGH"})
    rois = [float(r.actual_roi_pct) for r in rows]
    return P73GradingContextRead(
        grading_outcome_count=len(rows),
        grading_hit_rate_pct=_pct(hits, len(rows)),
        grading_avg_actual_roi_pct=round(sum(rois) / len(rois), 1) if rois else 0.0,
    )


def build_category_calibration(
    outcomes: list[P73RecommendationOutcome],
) -> list[P73CategoryCalibrationRead]:
    buckets: dict[str, list[P73RecommendationOutcome]] = defaultdict(list)
    for o in outcomes:
        buckets[_normalize_calibration_category(o.recommendation_category)].append(o)

    rows: list[P73CategoryCalibrationRead] = []
    for cat in P73_CALIBRATION_CATEGORIES:
        group = buckets.get(cat, [])
        rois = [_float_roi(o.actual_roi_pct) for o in group if o.actual_roi_pct is not None]
        rois_clean = [r for r in rois if r is not None]
        successes = sum(1 for o in group if o.attribution_accurate is True)
        samples = sum(1 for o in group if o.attribution_accurate is not None)
        rows.append(
            P73CategoryCalibrationRead(
                calibration_category=cat,
                recommendation_count=len(group),
                success_rate_pct=_pct(successes, samples) if samples else 0.0,
                average_roi_pct=round(sum(rois_clean) / len(rois_clean), 1) if rois_clean else 0.0,
                median_roi_pct=round(statistics.median(rois_clean), 1) if rois_clean else 0.0,
            )
        )
    return rows


def build_recommendation_effectiveness(
    outcomes: list[P73RecommendationOutcome],
    accuracy: P73RecommendationAccuracyMetricsRead,
    *,
    snapshot_id: int = 0,
    generated_at: datetime | None = None,
) -> P73RecommendationEffectivenessRead:
    profit = build_profitability_read(outcomes)
    by_type: list[P73TypeEffectivenessRead] = []
    for rec_type in ("BUY", "GRADE", "SELL", "WATCH"):
        group = [o for o in outcomes if _normalize_rec_type(o.recommendation_type) == rec_type]
        exp_rois = [_float_roi(o.expected_roi_pct) for o in group if o.expected_roi_pct is not None]
        act_rois = [_float_roi(o.actual_roi_pct) for o in group if o.actual_roi_pct is not None]
        exp_rois = [r for r in exp_rois if r is not None]
        act_rois = [r for r in act_rois if r is not None]
        exp_avg = round(sum(exp_rois) / len(exp_rois), 1) if exp_rois else 0.0
        act_avg = round(sum(act_rois) / len(act_rois), 1) if act_rois else 0.0
        wins = sum(1 for r in act_rois if r > 0)
        losses = sum(1 for r in act_rois if r < 0)
        by_type.append(
            P73TypeEffectivenessRead(
                recommendation_type=rec_type,
                expected_roi_pct=exp_avg,
                actual_roi_pct=act_avg,
                win_rate_pct=_pct(wins, len(act_rois)),
                loss_rate_pct=_pct(losses, len(act_rois)),
                accuracy_label=_accuracy_label(exp_avg, act_avg),
            )
        )
    return P73RecommendationEffectivenessRead(
        win_rate_pct=accuracy.win_rate_pct,
        loss_rate_pct=accuracy.loss_rate_pct,
        expected_roi_pct=profit.expected_roi_pct,
        actual_roi_pct=profit.actual_roi_pct,
        recommendation_accuracy_pct=accuracy.success_rate_pct,
        by_type=by_type,
        snapshot_id=snapshot_id,
        generated_at=generated_at or datetime.now(timezone.utc),
    )


def _rank_types(
    category_rows: list,
    *,
    best: bool,
) -> list[str]:
    scored = [(c.recommendation_type, c.average_roi_pct * 0.6 + c.success_rate_pct * 0.4) for c in category_rows]
    scored.sort(key=lambda x: x[1], reverse=best)
    return [t for t, _score in scored[:2]]


def persist_feedback_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    overall_accuracy_pct: float,
    overall_roi_pct: float,
    confidence: P73RecommendationConfidenceRead,
    effectiveness: P73RecommendationEffectivenessRead,
    calibration: list[P73CategoryCalibrationRead],
    market: P73MarketContextRead,
    grading: P73GradingContextRead,
) -> P73RecommendationFeedbackBundleSnapshot:
    bundle = P73RecommendationFeedbackBundleSnapshot(
        owner_user_id=owner_user_id,
        overall_accuracy_pct=overall_accuracy_pct,
        overall_roi_pct=overall_roi_pct,
    )
    session.add(bundle)
    session.flush()
    bundle_id = int(bundle.id or 0)

    conf_id = persist_confidence_snapshot(
        session,
        owner_user_id=owner_user_id,
        bundle_snapshot_id=bundle_id,
        confidence=confidence,
        market=market,
        grading=grading,
    )
    confidence.snapshot_id = conf_id

    eff_row = P73RecommendationEffectivenessSnapshot(
        owner_user_id=owner_user_id,
        bundle_snapshot_id=bundle_id,
        win_rate_pct=effectiveness.win_rate_pct,
        loss_rate_pct=effectiveness.loss_rate_pct,
        expected_roi_pct=effectiveness.expected_roi_pct,
        actual_roi_pct=effectiveness.actual_roi_pct,
        recommendation_accuracy_pct=effectiveness.recommendation_accuracy_pct,
        by_type_json={"by_type": [t.model_dump(mode="json") for t in effectiveness.by_type]},
    )
    session.add(eff_row)
    session.flush()
    effectiveness.snapshot_id = int(eff_row.id or 0)

    for row in calibration:
        session.add(
            P73RecommendationCategoryCalibrationSnapshot(
                owner_user_id=owner_user_id,
                bundle_snapshot_id=bundle_id,
                calibration_category=row.calibration_category,
                recommendation_count=row.recommendation_count,
                success_rate_pct=row.success_rate_pct,
                average_roi_pct=row.average_roi_pct,
                median_roi_pct=row.median_roi_pct,
            )
        )
    session.commit()
    session.refresh(bundle)
    return bundle


def run_recommendation_feedback_engine(
    session: Session,
    *,
    owner_user_id: int,
    persist: bool = True,
) -> P73RecommendationQualityDashboardRead:
    from app.services.recommendation_analytics_service import _accuracy_metrics

    outcomes, events_by_outcome = _load_owner_data(session, owner_user_id)
    accuracy = _accuracy_metrics(outcomes, events_by_outcome)
    profitability = build_profitability_read(outcomes)
    category_performance = build_category_performance_read(outcomes)
    market = load_market_context(session, owner_user_id=owner_user_id)
    grading = load_grading_context(session, owner_user_id=owner_user_id)
    calibration = build_category_calibration(outcomes)
    confidence = build_recommendation_confidence(
        outcomes=outcomes,
        category_rows=category_performance,
        market=market,
        grading=grading,
    )
    effectiveness = build_recommendation_effectiveness(outcomes, accuracy)

    overall_accuracy = accuracy.success_rate_pct
    overall_roi = profitability.actual_roi_pct

    bundle_id = 0
    generated_at = datetime.now(timezone.utc)
    if persist:
        bundle = persist_feedback_snapshots(
            session,
            owner_user_id=owner_user_id,
            overall_accuracy_pct=overall_accuracy,
            overall_roi_pct=overall_roi,
            confidence=confidence,
            effectiveness=effectiveness,
            calibration=calibration,
            market=market,
            grading=grading,
        )
        bundle_id = int(bundle.id or 0)
        generated_at = bundle.generated_at
        confidence.generated_at = generated_at
        effectiveness.generated_at = generated_at

    return P73RecommendationQualityDashboardRead(
        bundle_snapshot_id=bundle_id,
        generated_at=generated_at,
        overall_accuracy_pct=overall_accuracy,
        overall_roi_pct=overall_roi,
        confidence=confidence,
        category_calibration=calibration,
        effectiveness=effectiveness,
        category_performance=category_performance,
        best_recommendation_types=_rank_types(category_performance, best=True),
        worst_recommendation_types=_rank_types(category_performance, best=False),
        market_context=market,
        grading_context=grading,
    )
