"""Audit helpers for cross-system / Top Recommendations ranking."""

from __future__ import annotations

from statistics import mean

from sqlmodel import Session

from app.schemas.cross_system_recommendation import CrossSystemRecommendationRead
from app.schemas.recommendation_ranking import (
    RecommendationRankingAuditRead,
    RecommendationRankingAuditRow,
    RecommendationRankingDiagnosticsRead,
)
from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations


def _is_strictly_score_ordered(scores: list[float]) -> bool:
    for idx in range(len(scores) - 1):
        if scores[idx] + 1e-9 < scores[idx + 1]:
            return False
    return True


def _looks_alphabetical_by_title(titles: list[str]) -> bool:
    if len(titles) < 3:
        return False
    normalized = [t.strip().lower() for t in titles]
    return normalized == sorted(normalized)


def audit_from_listed_items(
    items: list[CrossSystemRecommendationRead],
    *,
    total_count: int,
) -> RecommendationRankingAuditRead:
    scores = [float(i.priority_score) for i in items]
    null_count = sum(1 for i in items if i.priority_score is None)
    distinct = len({round(s, 4) for s in scores})
    top20 = scores[:20]
    spread = (max(top20) - min(top20)) if len(top20) >= 2 else 0.0
    top_score = scores[0] if scores else None
    tied_top = sum(1 for s in scores if top_score is not None and abs(s - top_score) < 1e-9) if scores else 0
    rows = [
        RecommendationRankingAuditRow(
            rank=int(i.recommendation_rank),
            title=i.title,
            priority_score=float(i.priority_score),
            confidence_score=float(i.confidence_score),
            recommendation_type=i.recommendation_type,
        )
        for i in items
    ]
    titles = [i.title for i in items]
    return RecommendationRankingAuditRead(
        total_count=total_count,
        listed_count=len(items),
        min_score=min(scores) if scores else None,
        max_score=max(scores) if scores else None,
        average_score=round(mean(scores), 4) if scores else None,
        distinct_score_count=distinct,
        top_20_score_spread=round(spread, 4),
        null_priority_count=null_count,
        identical_top_score_count=tied_top,
        sort_order_valid=_is_strictly_score_ordered(scores),
        appears_alphabetical_by_title=_looks_alphabetical_by_title(titles),
        items=rows,
    )


def build_recommendation_ranking_audit(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
    refresh: bool = True,
) -> RecommendationRankingAuditRead:
    if refresh:
        generate_cross_system_recommendations(session, owner_user_id=owner_user_id)
    items, total = list_latest_cross_system_recommendations(
        session,
        owner_user_id=owner_user_id,
        limit=min(max(limit, 1), 200),
        offset=0,
    )
    return audit_from_listed_items(items, total_count=total)


def diagnostics_from_audit(audit: RecommendationRankingAuditRead) -> RecommendationRankingDiagnosticsRead:
    return RecommendationRankingDiagnosticsRead(
        min_score=audit.min_score,
        max_score=audit.max_score,
        average_score=audit.average_score,
        distinct_score_count=audit.distinct_score_count,
        top_20_score_spread=audit.top_20_score_spread,
        null_priority_count=audit.null_priority_count,
        sort_order_valid=audit.sort_order_valid,
        appears_alphabetical_by_title=audit.appears_alphabetical_by_title,
    )
