"""Audit collector-significance contribution to Top Recommendations ranking."""

from __future__ import annotations

from statistics import mean

from sqlmodel import Session

from app.schemas.recommendation_ranking import (
    IntelligenceLeaderRow,
    IntelligenceSignalContribution,
    RecommendationIntelligenceAuditRead,
    RecommendationRankingAuditRead,
    RecommendationRankingAuditRow,
)
from app.services.cross_system_recommendation_engine import build_cross_system_candidates
from app.services.recommendation_intelligence_enrichment import CollectorSignificanceScoreBreakdown
from app.services.recommendation_intelligence_ranking import rank_order_changed_by_collector_boost


def _breakdown_from_candidate(cand) -> CollectorSignificanceScoreBreakdown | None:
    return getattr(cand, "collector_score_breakdown", None)


def _leader_rows(
    items: list[tuple[str, float]],
    *,
    limit: int = 15,
) -> list[IntelligenceLeaderRow]:
    ranked = sorted(items, key=lambda x: (-x[1], x[0].lower()))[:limit]
    return [
        IntelligenceLeaderRow(title=title, score=round(score, 2), rank=idx + 1)
        for idx, (title, score) in enumerate(ranked)
    ]


def build_intelligence_audit_from_candidates(
    candidates: list,
    *,
    limit: int = 100,
) -> RecommendationIntelligenceAuditRead:
    top = candidates[: max(1, limit)]
    breakdowns: list[tuple[str, CollectorSignificanceScoreBreakdown]] = []
    for cand in top:
        bd = _breakdown_from_candidate(cand)
        if bd is not None:
            breakdowns.append((cand.title, bd))

    if not breakdowns:
        return RecommendationIntelligenceAuditRead(listed_count=len(top))

    def _sum_weighted(getter, weight: float) -> float:
        return sum(getter(bd) * weight for _, bd in breakdowns)

    contributions = [
        IntelligenceSignalContribution(
            signal="milestone",
            total_weighted_points=round(_sum_weighted(lambda b: b.milestone_score, 1.25), 2),
            average_component_score=round(mean(b.milestone_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.milestone_score >= 2.0),
        ),
        IntelligenceSignalContribution(
            signal="creator",
            total_weighted_points=round(_sum_weighted(lambda b: b.creator_score, 1.2), 2),
            average_component_score=round(mean(b.creator_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.creator_score >= 2.0),
        ),
        IntelligenceSignalContribution(
            signal="homage",
            total_weighted_points=round(_sum_weighted(lambda b: b.homage_score, 1.2), 2),
            average_component_score=round(mean(b.homage_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.homage_score >= 2.0),
        ),
        IntelligenceSignalContribution(
            signal="audience",
            total_weighted_points=round(_sum_weighted(lambda b: b.audience_score, 1.0), 2),
            average_component_score=round(mean(b.audience_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.audience_score >= 1.0),
        ),
        IntelligenceSignalContribution(
            signal="franchise",
            total_weighted_points=round(_sum_weighted(lambda b: b.franchise_score, 0.42), 2),
            average_component_score=round(mean(b.franchise_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.franchise_score >= 6.0),
        ),
        IntelligenceSignalContribution(
            signal="publisher",
            total_weighted_points=round(_sum_weighted(lambda b: b.publisher_score, 0.38), 2),
            average_component_score=round(mean(b.publisher_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.publisher_score >= 4.0),
        ),
        IntelligenceSignalContribution(
            signal="historical_demand",
            total_weighted_points=round(_sum_weighted(lambda b: b.historical_demand_score, 0.32), 2),
            average_component_score=round(mean(b.historical_demand_score for _, b in breakdowns), 2),
            rows_with_signal=sum(1 for _, b in breakdowns if b.historical_demand_score >= 2.0),
        ),
    ]

    milestone_leaders = _leader_rows([(t, b.milestone_score) for t, b in breakdowns])
    creator_leaders = _leader_rows([(t, b.creator_score) for t, b in breakdowns])
    homage_leaders = _leader_rows([(t, b.homage_score) for t, b in breakdowns])

    return RecommendationIntelligenceAuditRead(
        listed_count=len(top),
        rank_order_affected_by_intelligence=rank_order_changed_by_collector_boost(top),
        contribution=contributions,
        top_milestone=milestone_leaders,
        top_creator=creator_leaders,
        top_homage=homage_leaders,
    )


def attach_intelligence_scores_to_audit_rows(
    audit: RecommendationRankingAuditRead,
    candidates: list,
) -> None:
    by_key = {
        (c.recommendation_type.strip().upper(), c.title_key): c
        for c in candidates
    }
    for row in audit.items:
        from app.services.recommendation_title_normalize import normalize_recommendation_title_key

        key = (row.recommendation_type.strip().upper(), normalize_recommendation_title_key(row.title))
        cand = by_key.get(key)
        if cand is None:
            continue
        bd = _breakdown_from_candidate(cand)
        if bd is None:
            continue
        row.base_score = bd.base_score
        row.franchise_score = bd.franchise_score
        row.publisher_score = bd.publisher_score
        row.creator_score = bd.creator_score
        row.milestone_score = bd.milestone_score
        row.homage_score = bd.homage_score
        row.audience_score = bd.audience_score
        row.collector_ranking_boost = bd.ranking_boost
        row.final_pre_spread_score = bd.final_score


def build_recommendation_intelligence_validation(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
    refresh_upstream: bool = False,
) -> tuple[list, RecommendationIntelligenceAuditRead]:
    candidates = build_cross_system_candidates(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=refresh_upstream,
    )
    candidates.sort(
        key=lambda c: (float(c.priority_score), c.title_key),
        reverse=True,
    )
    intel = build_intelligence_audit_from_candidates(candidates, limit=limit)
    return candidates, intel
