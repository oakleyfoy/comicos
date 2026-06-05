"""P62 Phase 1 — read-only Recommendation V3 preview (no V2 persist)."""

from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.services.cross_system_recommendation_engine import build_cross_system_candidates
from app.services.p62_feature_flags import p62_v3_persist_enabled, p62_v3_preview_enabled
from app.services.recommendation_title_index import resolve_release_pair
from app.services.recommendation_v3_components import score_v3_demand_components
from app.services.recommendation_v3_scoring_context import (
    RecommendationV3ScoringContext,
    build_recommendation_v3_scoring_context,
)


def count_persisted_cross_system_rows(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
        ).one()
        or 0
    )


def build_recommendation_v3_preview(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 20,
) -> dict:
    if not p62_v3_preview_enabled():
        return {
            "enabled": False,
            "not_ready": True,
            "reason_codes": ["P62_V3_PREVIEW_DISABLED"],
            "items": [],
            "readiness": None,
            "persisted_row_count": count_persisted_cross_system_rows(session, owner_user_id=owner_user_id),
            "v2_mutated": False,
        }

    persisted_before = count_persisted_cross_system_rows(session, owner_user_id=owner_user_id)
    release_index = None
    from app.services.recommendation_catalog_quality import build_forward_release_title_index

    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)

    candidates = build_cross_system_candidates(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=False,
    )
    candidates.sort(key=lambda c: (-c.priority_score, -c.confidence_score, c.title))
    top = candidates[: max(1, min(limit, 50))]

    issue_ids: list[int] = []
    cand_issue: dict[str, int] = {}
    for cand in top:
        pair = resolve_release_pair(cand.title, release_index)
        if pair is None or pair[0].id is None:
            continue
        iid = int(pair[0].id)
        issue_ids.append(iid)
        cand_issue[cand.title_key] = iid

    ctx: RecommendationV3ScoringContext = build_recommendation_v3_scoring_context(
        session,
        owner_user_id=owner_user_id,
        issue_ids=issue_ids,
    )

    items: list[dict] = []
    for cand in top:
        iid = cand_issue.get(cand.title_key)
        bundle = score_v3_demand_components(ctx, release_issue_id=iid)
        items.append(
            {
                "title": cand.title,
                "recommendation_type": cand.recommendation_type,
                "v2_priority_score": float(cand.priority_score),
                "v2_confidence_score": float(cand.confidence_score),
                "v3_preview_score": bundle.preview_score,
                "release_issue_id": bundle.release_issue_id,
                "demand_intel_status": bundle.demand_intel_status,
                "components": [
                    {
                        "component_name": c.component_name,
                        "component_score": c.component_score,
                        "component_weight": c.component_weight,
                        "explanation": c.explanation,
                    }
                    for c in bundle.components
                ],
            }
        )

    persisted_after = count_persisted_cross_system_rows(session, owner_user_id=owner_user_id)
    v2_mutated = persisted_after != persisted_before

    readiness = ctx.readiness
    not_ready = not readiness.ready and len(items) == 0
    reason_codes = list(readiness.reason_codes)
    if not items and "NO_RELEASE_CATALOG" not in reason_codes:
        if not issue_ids:
            reason_codes.append("NO_MATCHED_ISSUES_IN_PREVIEW")

    return {
        "enabled": True,
        "not_ready": not_ready,
        "reason_codes": reason_codes,
        "items": items,
        "readiness": {
            "ready": readiness.ready,
            "reason_codes": list(readiness.reason_codes),
            "demand_snapshot_count": readiness.demand_snapshot_count,
            "velocity_snapshot_count": readiness.velocity_snapshot_count,
            "spec_snapshot_present": readiness.spec_snapshot_present,
            "spec_row_count": readiness.spec_row_count,
            "demand_median_age_hours": readiness.demand_median_age_hours,
        },
        "persisted_row_count": persisted_after,
        "v2_mutated": v2_mutated,
        "preview_count": len(items),
    }
