from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, func, select

from app.models.recommendation_v2 import (
    RecommendationDecisionV2,
    RecommendationRunV2,
    RecommendationScoreComponentV2,
    RecommendationScoreV2,
)
from app.models.release_intelligence import ReleaseIssue
from app.services.recommendation_v2_engine import _latest_scores_by_issue


@dataclass(frozen=True)
class LiveP51_04OutputAssessment:
    """Evidence that P51-04 produced real scored output for an owner (not just code/deploy)."""

    latest_issue_score_count: int
    total_v2_score_rows: int
    completed_runs_with_scores: int
    latest_run_recommendations_created: int
    component_rows_for_owner: int
    decision_rows_for_owner: int
    release_issue_count: int
    live_output_ready: bool
    blocking_reasons: tuple[str, ...]


def assess_live_p51_04_output(session: Session, *, owner_user_id: int) -> LiveP51_04OutputAssessment:
    latest = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    latest_count = len(latest)

    total_rows = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationScoreV2)
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )

    completed_runs = session.exec(
        select(RecommendationRunV2)
        .where(RecommendationRunV2.owner_user_id == owner_user_id)
        .where(RecommendationRunV2.status == "COMPLETED")
        .order_by(RecommendationRunV2.id.desc())
    ).all()
    runs_with_scores = sum(1 for run in completed_runs if (run.recommendations_created or 0) > 0)
    latest_run_created = int(completed_runs[0].recommendations_created) if completed_runs else 0

    component_rows = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationScoreComponentV2)
            .join(
                RecommendationScoreV2,
                RecommendationScoreComponentV2.recommendation_score_id == RecommendationScoreV2.id,
            )
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )

    decision_rows = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationDecisionV2)
            .join(
                RecommendationScoreV2,
                RecommendationDecisionV2.recommendation_score_id == RecommendationScoreV2.id,
            )
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )

    issue_count = (
        session.scalar(
            select(func.count())
            .select_from(ReleaseIssue)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        )
        or 0
    )

    reasons: list[str] = []
    if issue_count > 0 and latest_count == 0:
        reasons.append("No latest issue-level Recommendation V2 scores for owner catalog.")
    if total_rows == 0:
        reasons.append("No Recommendation V2 score rows persisted.")
    if runs_with_scores == 0:
        reasons.append("No completed V2 run with recommendations_created > 0.")
    elif latest_run_created == 0 and completed_runs:
        reasons.append("Most recent completed V2 run produced zero recommendations.")
    if latest_count > 0 and component_rows == 0:
        reasons.append("V2 score components missing for owner output.")
    if latest_count > 0 and decision_rows < latest_count:
        reasons.append("V2 explanations/decisions incomplete vs latest issue scores.")

    live_ready = len(reasons) == 0 and latest_count > 0 and total_rows > 0 and runs_with_scores > 0

    return LiveP51_04OutputAssessment(
        latest_issue_score_count=latest_count,
        total_v2_score_rows=int(total_rows),
        completed_runs_with_scores=runs_with_scores,
        latest_run_recommendations_created=latest_run_created,
        component_rows_for_owner=int(component_rows),
        decision_rows_for_owner=int(decision_rows),
        release_issue_count=int(issue_count),
        live_output_ready=live_ready,
        blocking_reasons=tuple(reasons),
    )
