"""P62 — Recommendation V3 P61 component calculators (preview only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.demand_intelligence import TREND_INSUFFICIENT, TREND_RISING
from app.services.recommendation_v3_scoring_context import RecommendationV3ScoringContext

V3_COMPONENT_NAMES = (
    "COMMUNITY_DEMAND_SCORE",
    "ISSUE_DEMAND_LEVEL_SCORE",
    "DEMAND_VELOCITY_SCORE",
    "DEMAND_ACCELERATION_SCORE",
    "SPEC_OPPORTUNITY_SCORE",
)

V3_COMPONENT_WEIGHTS: dict[str, float] = {
    "COMMUNITY_DEMAND_SCORE": 0.08,
    "ISSUE_DEMAND_LEVEL_SCORE": 0.10,
    "DEMAND_VELOCITY_SCORE": 0.06,
    "DEMAND_ACCELERATION_SCORE": 0.03,
    "SPEC_OPPORTUNITY_SCORE": 0.07,
}


@dataclass(frozen=True)
class V3ScoreComponentResult:
    component_name: str
    component_score: float
    component_weight: float
    explanation: str


@dataclass(frozen=True)
class V3ComponentBundle:
    components: tuple[V3ScoreComponentResult, ...]
    preview_score: float
    release_issue_id: int | None
    demand_intel_status: str


def _neutral(score: float = 50.0, explain: str = "No P61 match") -> float:
    return round(max(0.0, min(100.0, score)), 2)


def score_v3_demand_components(
    ctx: RecommendationV3ScoringContext,
    *,
    release_issue_id: int | None,
) -> V3ComponentBundle:
    iid = int(release_issue_id or 0)
    status = ctx.status_for_issue(iid) if iid > 0 else None
    demand_status = status.status if status else "NOT_MATCHED"
    demand = ctx.demand_for_issue(iid) if iid > 0 else None
    velocity = ctx.velocity_for_issue(iid) if iid > 0 else None
    spec = ctx.spec_for_issue(iid) if iid > 0 else None

    if demand is not None:
        community = _neutral(float(demand.community_demand_score), "LoCG community demand")
        level = _neutral(float(demand.combined_demand_score), "Combined issue demand level")
        comm_expl = f"pull={demand.pull_count} want={demand.want_count}"
        level_expl = f"entity_rollup={demand.entity_rollup_score:.1f}"
    else:
        community = _neutral(50.0)
        level = _neutral(50.0)
        comm_expl = demand_status
        level_expl = demand_status

    if velocity is not None and velocity.trend_label != TREND_INSUFFICIENT:
        vel = _neutral(float(velocity.velocity_score), "7d velocity")
        vel_expl = f"window=7 delta={velocity.combined_score_delta:.1f} trend={velocity.trend_label}"
        if velocity.trend_label == TREND_RISING:
            accel = _neutral(min(100.0, 50.0 + float(velocity.acceleration_score)), "Rising acceleration")
            accel_expl = f"acceleration={velocity.acceleration_score:.1f}"
        else:
            accel = _neutral(max(40.0, float(velocity.acceleration_score)), "Acceleration (non-rising)")
            accel_expl = velocity.trend_label
    else:
        vel = _neutral(50.0)
        vel_expl = TREND_INSUFFICIENT
        accel = _neutral(50.0)
        accel_expl = TREND_INSUFFICIENT

    if spec is not None:
        spec_score = _neutral(float(spec.opportunity_score), "Spec opportunity row")
        spec_expl = f"rank={spec.rank} horizon={spec.horizon_bucket}"
    else:
        spec_score = _neutral(50.0)
        spec_expl = "Not in owner spec snapshot"

    components = (
        V3ScoreComponentResult("COMMUNITY_DEMAND_SCORE", community, V3_COMPONENT_WEIGHTS["COMMUNITY_DEMAND_SCORE"], comm_expl),
        V3ScoreComponentResult("ISSUE_DEMAND_LEVEL_SCORE", level, V3_COMPONENT_WEIGHTS["ISSUE_DEMAND_LEVEL_SCORE"], level_expl),
        V3ScoreComponentResult("DEMAND_VELOCITY_SCORE", vel, V3_COMPONENT_WEIGHTS["DEMAND_VELOCITY_SCORE"], vel_expl),
        V3ScoreComponentResult("DEMAND_ACCELERATION_SCORE", accel, V3_COMPONENT_WEIGHTS["DEMAND_ACCELERATION_SCORE"], accel_expl),
        V3ScoreComponentResult("SPEC_OPPORTUNITY_SCORE", spec_score, V3_COMPONENT_WEIGHTS["SPEC_OPPORTUNITY_SCORE"], spec_expl),
    )
    weight_total = sum(c.component_weight for c in components)
    weighted = sum(c.component_score * c.component_weight for c in components) / max(weight_total, 0.01)
    preview_score = round(max(0.0, min(100.0, weighted)), 2)

    return V3ComponentBundle(
        components=components,
        preview_score=preview_score,
        release_issue_id=iid if iid > 0 else None,
        demand_intel_status=demand_status,
    )
