from __future__ import annotations

from sqlmodel import Session

from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.schemas.cross_system_recommendation import (
    CrossSystemRecommendationRead,
    CrossSystemRecommendationSummaryRead,
)
from app.services.cross_system_recommendation_engine import (
    TYPE_ACQUIRE,
    TYPE_GRADE,
    TYPE_PREORDER,
    TYPE_REBALANCE,
    TYPE_SELL,
    generate_cross_system_recommendations,
    _latest_snapshot_rows,
)
from app.services.recommendation_catalog_quality import (
    build_forward_release_title_index,
    title_passes_top_recommendation_quality,
)
from app.services.recommendation_decision_engine import (
    build_recommendation_decision_context,
    decision_for_cross_system,
)


def _to_read(
    row: CrossSystemRecommendation,
    *,
    decision=None,
) -> CrossSystemRecommendationRead:
    return CrossSystemRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        recommendation_type=row.recommendation_type,
        priority_score=float(row.priority_score),
        confidence_score=float(row.confidence_score),
        title=row.title,
        estimated_value=float(row.estimated_value) if row.estimated_value is not None else None,
        recommendation_rank=int(row.recommendation_rank),
        source_systems=list(row.source_systems or []),
        rationale=row.rationale,
        created_at=row.created_at,
        decision=decision,
    )


def list_latest_cross_system_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    rank_max: int | None = None,
    priority_min: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CrossSystemRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    snapshot = _latest_snapshot_rows(session, owner_user_id=owner_user_id)
    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    decision_ctx = build_recommendation_decision_context(session, owner_user_id=owner_user_id)
    items: list[CrossSystemRecommendationRead] = []
    for rank in sorted(snapshot.keys()):
        row = snapshot[rank]
        if recommendation_type and row.recommendation_type != recommendation_type.strip().upper():
            continue
        if rank_max is not None and int(row.recommendation_rank) > int(rank_max):
            continue
        if priority_min is not None and float(row.priority_score) < float(priority_min):
            continue
        if not title_passes_top_recommendation_quality(
            row.title,
            session=session,
            owner_user_id=owner_user_id,
            release_index=release_index,
        ):
            continue
        decision = decision_for_cross_system(
            recommendation_type=row.recommendation_type,
            title=row.title,
            priority_score=float(row.priority_score),
            confidence_score=float(row.confidence_score),
            rationale=row.rationale,
            source_systems=list(row.source_systems or []),
            estimated_value=float(row.estimated_value) if row.estimated_value is not None else None,
            session=session,
            owner_user_id=owner_user_id,
            ctx=decision_ctx,
        )
        items.append(_to_read(row, decision=decision))
    items.sort(
        key=lambda r: (
            -r.priority_score,
            -r.confidence_score,
            -(r.estimated_value or 0.0),
            r.recommendation_rank,
            -r.id,
        )
    )
    total = len(items)
    return items[offset : offset + limit], total


def get_cross_system_recommendation_summary(
    session: Session,
    *,
    owner_user_id: int,
) -> CrossSystemRecommendationSummaryRead:
    items, total = list_latest_cross_system_recommendations(session, owner_user_id=owner_user_id, limit=500, offset=0)
    top_n = 5

    def _count(rec_type: str) -> int:
        return sum(1 for i in items if i.recommendation_type == rec_type and i.recommendation_rank <= top_n)

    return CrossSystemRecommendationSummaryRead(
        total_recommendations=total,
        top_acquisitions=_count(TYPE_ACQUIRE),
        top_preorders=_count(TYPE_PREORDER),
        top_grading_opportunities=_count(TYPE_GRADE),
        top_sell_opportunities=_count(TYPE_SELL),
        top_rebalance_opportunities=_count(TYPE_REBALANCE),
    )


def refresh_and_list_latest_cross_system_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    rank_max: int | None = None,
    priority_min: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CrossSystemRecommendationRead], int]:
    generate_cross_system_recommendations(session, owner_user_id=owner_user_id, refresh_upstream=True)
    return list_latest_cross_system_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation_type=recommendation_type,
        rank_max=rank_max,
        priority_min=priority_min,
        limit=limit,
        offset=offset,
    )
