"""Shared P62 collector scoring helpers."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_v2_scoring_context import build_recommendation_v2_scoring_context
from app.services.recommendation_v3_components import score_v3_demand_components
from app.services.recommendation_v3_scoring_context import (
    RecommendationV3ScoringContext,
    build_recommendation_v3_scoring_context,
)


def _component(bundle, name: str) -> float:
    for comp in bundle.components:
        if comp.component_name == name:
            return float(comp.component_score)
    return 50.0


def issue_intelligence_scores(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: list[int],
    v3_ctx: RecommendationV3ScoringContext | None = None,
    v2_ctx=None,
) -> dict[int, dict[str, float]]:
    if v3_ctx is None:
        v3_ctx = build_recommendation_v3_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    if v2_ctx is None:
        v2_ctx = build_recommendation_v2_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)

    out: dict[int, dict[str, float]] = {}
    if not issue_ids:
        return out
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.id.in_(issue_ids))
    ).all()
    for issue, series in rows:
        iid = int(issue.id or 0)
        bundle = score_v3_demand_components(v3_ctx, release_issue_id=iid)
        fit = v2_ctx.market_user_fit(session, issue=issue, series=series)
        spec = v3_ctx.spec_for_issue(iid)
        out[iid] = {
            "recommendation_score": float(bundle.preview_score),
            "demand_score": _component(bundle, "ISSUE_DEMAND_LEVEL_SCORE"),
            "velocity_score": _component(bundle, "DEMAND_VELOCITY_SCORE"),
            "spec_score": float(spec.opportunity_score) if spec else _component(bundle, "SPEC_OPPORTUNITY_SCORE"),
            "user_preference_score": float(fit.get("user_preference_score") or 50.0),
        }
    return out
