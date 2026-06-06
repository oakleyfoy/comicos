"""P73-03 rule-based recommendation confidence (0–100; no external ML)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.models.recommendation_outcome import P73RecommendationOutcome
from app.schemas.recommendation_analytics import P73RecommendationCategoryPerformanceRead
from app.schemas.recommendation_feedback_intelligence import (
    P73GradingContextRead,
    P73MarketContextRead,
    P73RecommendationConfidenceRead,
)
from app.services.recommendation_analytics_service import _float_roi, _normalize_rec_type, _pct


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _type_confidence(
    *,
    rec_type: str,
    category_rows: list[P73RecommendationCategoryPerformanceRead],
    outcomes: list[P73RecommendationOutcome],
    market: P73MarketContextRead,
    grading: P73GradingContextRead,
) -> int:
    row = next((c for c in category_rows if c.recommendation_type == rec_type), None)
    count = row.recommendation_count if row else 0
    success = row.success_rate_pct if row else 0.0
    avg_roi = row.average_roi_pct if row else 0.0

    sample_boost = min(count, 25) / 25.0 * 20.0
    success_component = success * 0.55
    roi_component = max(-10.0, min(15.0, avg_roi * 0.25))
    base = 25.0 + success_component + sample_boost + roi_component

    if rec_type == "GRADE" and grading.grading_outcome_count > 0:
        base += min(10.0, grading.grading_hit_rate_pct * 0.1)
    if rec_type in {"BUY", "SELL"} and market.fmv_trend_point_count > 0:
        base += min(8.0, market.market_signal_strength * 0.08)

    type_outcomes = [o for o in outcomes if _normalize_rec_type(o.recommendation_type) == rec_type]
    attributed = [o for o in type_outcomes if o.attribution_accurate is not None]
    if attributed:
        match_rate = sum(1 for o in attributed if o.attribution_accurate) / len(attributed) * 100.0
        base += (match_rate - 50.0) * 0.15

    if count == 0:
        return _clamp_score(50.0 + (5.0 if market.fmv_trend_point_count else 0.0))

    return _clamp_score(base)


def build_recommendation_confidence(
    *,
    outcomes: list[P73RecommendationOutcome],
    category_rows: list[P73RecommendationCategoryPerformanceRead],
    market: P73MarketContextRead,
    grading: P73GradingContextRead,
    snapshot_id: int = 0,
    generated_at: datetime | None = None,
) -> P73RecommendationConfidenceRead:
    return P73RecommendationConfidenceRead(
        buy_confidence=_type_confidence(
            rec_type="BUY",
            category_rows=category_rows,
            outcomes=outcomes,
            market=market,
            grading=grading,
        ),
        grade_confidence=_type_confidence(
            rec_type="GRADE",
            category_rows=category_rows,
            outcomes=outcomes,
            market=market,
            grading=grading,
        ),
        sell_confidence=_type_confidence(
            rec_type="SELL",
            category_rows=category_rows,
            outcomes=outcomes,
            market=market,
            grading=grading,
        ),
        watch_confidence=_type_confidence(
            rec_type="WATCH",
            category_rows=category_rows,
            outcomes=outcomes,
            market=market,
            grading=grading,
        ),
        snapshot_id=snapshot_id,
        generated_at=generated_at or datetime.now(timezone.utc),
    )


def persist_confidence_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    bundle_snapshot_id: int,
    confidence: P73RecommendationConfidenceRead,
    market: P73MarketContextRead,
    grading: P73GradingContextRead,
) -> int:
    from app.models.recommendation_feedback_snapshot import P73RecommendationConfidenceSnapshot

    row = P73RecommendationConfidenceSnapshot(
        owner_user_id=owner_user_id,
        bundle_snapshot_id=bundle_snapshot_id,
        buy_confidence=confidence.buy_confidence,
        grade_confidence=confidence.grade_confidence,
        sell_confidence=confidence.sell_confidence,
        watch_confidence=confidence.watch_confidence,
        metadata_json={
            "market": market.model_dump(mode="json"),
            "grading": grading.model_dump(mode="json"),
        },
    )
    session.add(row)
    session.flush()
    return int(row.id or 0)
