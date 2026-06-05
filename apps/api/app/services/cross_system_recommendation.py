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

# Bound work for read-only GET paths (latest snapshot batch only).
GET_SNAPSHOT_SCAN_LIMIT = 200


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


def _row_passes_filters(
    row: CrossSystemRecommendation,
    *,
    recommendation_type: str | None,
    rank_max: int | None,
    priority_min: float | None,
) -> bool:
    if recommendation_type and row.recommendation_type != recommendation_type.strip().upper():
        return False
    if rank_max is not None and int(row.recommendation_rank) > int(rank_max):
        return False
    if priority_min is not None and float(row.priority_score) < float(priority_min):
        return False
    return True


def _sort_key_read(row: CrossSystemRecommendation) -> tuple:
    return (
        -float(row.priority_score),
        -float(row.confidence_score),
        -(float(row.estimated_value) if row.estimated_value is not None else 0.0),
        int(row.recommendation_rank),
        -int(row.id or 0),
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
    include_decisions: bool = True,
    snapshot_scan_limit: int = GET_SNAPSHOT_SCAN_LIMIT,
) -> tuple[list[CrossSystemRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    snapshot = _latest_snapshot_rows(
        session,
        owner_user_id=owner_user_id,
        scan_limit=max(1, min(int(snapshot_scan_limit), 1000)),
    )
    if not snapshot:
        return [], 0

    release_index = None
    if include_decisions:
        release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)

    filtered: list[CrossSystemRecommendation] = []
    for row in snapshot.values():
        if not _row_passes_filters(
            row,
            recommendation_type=recommendation_type,
            rank_max=rank_max,
            priority_min=priority_min,
        ):
            continue
        if include_decisions and release_index is not None:
            if not title_passes_top_recommendation_quality(
                row.title,
                session=session,
                owner_user_id=owner_user_id,
                release_index=release_index,
            ):
                continue
        filtered.append(row)

    filtered.sort(key=_sort_key_read)
    total = len(filtered)
    page_rows = filtered[offset : offset + limit]

    if not include_decisions or not page_rows:
        return [_to_read(row) for row in page_rows], total

    decision_ctx = build_recommendation_decision_context(session, owner_user_id=owner_user_id)
    items: list[CrossSystemRecommendationRead] = []
    for row in page_rows:
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
    return items, total


def get_cross_system_recommendation_summary(
    session: Session,
    *,
    owner_user_id: int,
) -> CrossSystemRecommendationSummaryRead:
    snapshot = _latest_snapshot_rows(
        session,
        owner_user_id=owner_user_id,
        scan_limit=GET_SNAPSHOT_SCAN_LIMIT,
    )
    if not snapshot:
        return CrossSystemRecommendationSummaryRead(
            total_recommendations=0,
            top_acquisitions=0,
            top_preorders=0,
            top_grading_opportunities=0,
            top_sell_opportunities=0,
            top_rebalance_opportunities=0,
            readiness_status="NOT_READY",
            readiness_reason="No persisted cross-system snapshot. POST /api/v1/cross-system-recommendations/rebuild to refresh.",
        )

    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    top_n = 5
    rows: list[CrossSystemRecommendation] = []
    for row in snapshot.values():
        if not title_passes_top_recommendation_quality(
            row.title,
            session=session,
            owner_user_id=owner_user_id,
            release_index=release_index,
        ):
            continue
        rows.append(row)

    def _count(rec_type: str) -> int:
        return sum(1 for r in rows if r.recommendation_type == rec_type and int(r.recommendation_rank) <= top_n)

    return CrossSystemRecommendationSummaryRead(
        total_recommendations=len(rows),
        top_acquisitions=_count(TYPE_ACQUIRE),
        top_preorders=_count(TYPE_PREORDER),
        top_grading_opportunities=_count(TYPE_GRADE),
        top_sell_opportunities=_count(TYPE_SELL),
        top_rebalance_opportunities=_count(TYPE_REBALANCE),
        readiness_status="READY",
        readiness_reason="",
    )


def rebuild_cross_system_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    refresh_upstream: bool = True,
) -> int:
    return generate_cross_system_recommendations(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=refresh_upstream,
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
    rebuild_cross_system_recommendations(session, owner_user_id=owner_user_id, refresh_upstream=True)
    return list_latest_cross_system_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation_type=recommendation_type,
        rank_max=rank_max,
        priority_min=priority_min,
        limit=limit,
        offset=offset,
    )
