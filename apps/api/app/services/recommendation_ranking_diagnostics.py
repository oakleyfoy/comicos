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
from app.services.cross_system_recommendation_engine import (
    _confidence_for_persist,
    _priority_for_persist,
    build_cross_system_candidates,
    generate_cross_system_recommendations,
)


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
    score_trace: dict[tuple[str, str], tuple[float, float, float, float, float, float]] | None = None,
) -> RecommendationRankingAuditRead:
    scores = [float(i.priority_score) for i in items]
    null_count = sum(1 for i in items if i.priority_score is None)
    distinct = len({round(s, 4) for s in scores})
    top20 = scores[:20]
    spread = (max(top20) - min(top20)) if len(top20) >= 2 else 0.0
    top_score = scores[0] if scores else None
    tied_top = sum(1 for s in scores if top_score is not None and abs(s - top_score) < 1e-9) if scores else 0
    rows = []
    for i in items:
        trace_key = (i.recommendation_type.strip().upper(), i.title.strip().lower())
        raw_norm = score_trace.get(trace_key) if score_trace else None
        computed = raw_norm[2] if raw_norm and len(raw_norm) > 2 else None
        raw_conf = raw_norm[3] if raw_norm and len(raw_norm) > 3 else None
        norm_conf = raw_norm[4] if raw_norm and len(raw_norm) > 4 else None
        computed_conf = raw_norm[5] if raw_norm and len(raw_norm) > 5 else None
        rows.append(
            RecommendationRankingAuditRow(
                rank=int(i.recommendation_rank),
                title=i.title,
                priority_score=float(i.priority_score),
                confidence_score=float(i.confidence_score),
                recommendation_type=i.recommendation_type,
                raw_priority_score=raw_norm[0] if raw_norm else None,
                normalized_priority_score=raw_norm[1] if raw_norm else None,
                computed_priority_score=computed,
                raw_confidence_score=raw_conf,
                normalized_confidence_score=norm_conf,
                computed_confidence_score=computed_conf,
            )
        )
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


def build_score_trace_map(
    session: Session,
    *,
    owner_user_id: int,
    refresh_upstream: bool = False,
) -> dict[tuple[str, str], tuple[float, float, float, float, float, float]]:
    trace_candidates = build_cross_system_candidates(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=refresh_upstream,
    )
    return {
        (c.recommendation_type.strip().upper(), c.title_key): (
            round(float(c.raw_priority_score or c.priority_score), 2),
            round(float(c.normalized_priority_score or c.priority_score), 2),
            round(float(_priority_for_persist(c)), 2),
            round(float(c.raw_confidence_score or c.confidence_score), 4),
            round(float(c.normalized_confidence_score or c.confidence_score), 4),
            round(float(_confidence_for_persist(c)), 4),
        )
        for c in trace_candidates
    }


def build_recommendation_ranking_audit(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
    refresh: bool = True,
) -> RecommendationRankingAuditRead:
    if refresh:
        from app.services.daily_action_engine import generate_daily_actions
        from app.services.unified_collector_intelligence import generate_unified_collector_recommendations

        generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
        generate_daily_actions(session, owner_user_id=owner_user_id, refresh_unified=False)
        generate_cross_system_recommendations(session, owner_user_id=owner_user_id, refresh_upstream=False)
    score_trace = build_score_trace_map(session, owner_user_id=owner_user_id, refresh_upstream=False)
    items, total = list_latest_cross_system_recommendations(
        session,
        owner_user_id=owner_user_id,
        limit=min(max(limit, 1), 200),
        offset=0,
    )
    return audit_from_listed_items(items, total_count=total, score_trace=score_trace)


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
