from __future__ import annotations

from sqlmodel import Session, select

from app.models.recommendation_v2 import RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.recommendation_v2 import RecommendationComparisonEntryRead, RecommendationV2ComparisonRead
from app.services.recommendation_v2_engine import _latest_scores_by_issue
from app.services.spec_recommendation_agent import list_recommendations_for_owner


def _issue_map(session: Session, *, owner_user_id: int) -> dict[int, tuple[ReleaseIssue, ReleaseSeries]]:
    return {
        int(issue.id or 0): (issue, series)
        for issue, series in session.exec(
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        ).all()
    }


def _movement_reason(*, v1_score: float, v2_score: float, v2_tier: str, v2_type: str) -> str:
    delta = v2_score - v1_score
    if delta >= 8:
        return f"V2 up {delta:.1f} — P51 intelligence ({v2_type}, tier {v2_tier})"
    if delta <= -8:
        return f"V2 down {abs(delta):.1f} — weaker franchise/market/user fit vs V1 publisher+#1 bias"
    return f"Stable shift {delta:+.1f}"


def compare_v1_v2_recommendations(session: Session, *, owner_user_id: int, limit: int = 100) -> RecommendationV2ComparisonRead:
    v1_rows, _ = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=500, offset=0)
    v1_by_issue: dict[int, float] = {}
    for row in v1_rows:
        if row.release_issue_id not in v1_by_issue:
            v1_by_issue[row.release_issue_id] = float(row.recommendation_score)

    v2_latest = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    issues = _issue_map(session, owner_user_id=owner_user_id)

    v1_ranked = sorted(v1_by_issue.items(), key=lambda x: x[1], reverse=True)[:limit]
    v2_ranked = sorted(v2_latest.values(), key=lambda s: s.total_score, reverse=True)[:limit]

    v1_rank_map = {issue_id: idx + 1 for idx, (issue_id, _) in enumerate(v1_ranked)}
    v2_rank_map = {score.release_issue_id: idx + 1 for idx, score in enumerate(v2_ranked)}

    entries: list[RecommendationComparisonEntryRead] = []
    moved_up = 0
    moved_down = 0
    all_issue_ids = set(v1_rank_map) | set(v2_rank_map)
    for issue_id in all_issue_ids:
        pair = issues.get(issue_id)
        if not pair:
            continue
        issue, series = pair
        v1_score = v1_by_issue.get(issue_id, 0.0)
        v2_row = v2_latest.get(issue_id)
        v2_score = float(v2_row.total_score) if v2_row else 0.0
        r1 = v1_rank_map.get(issue_id)
        r2 = v2_rank_map.get(issue_id)
        rank_change = None
        if r1 is not None and r2 is not None:
            rank_change = r1 - r2
            if rank_change >= 5:
                moved_up += 1
            elif rank_change <= -5:
                moved_down += 1
        entries.append(
            RecommendationComparisonEntryRead(
                release_issue_id=issue_id,
                series_name=series.series_name,
                issue_number=issue.issue_number,
                title=issue.title,
                v1_score=round(v1_score, 2),
                v2_score=round(v2_score, 2),
                v1_rank=r1,
                v2_rank=r2,
                rank_change=rank_change,
                movement_reason=_movement_reason(
                    v1_score=v1_score,
                    v2_score=v2_score,
                    v2_tier=v2_row.recommendation_tier if v2_row else "PASS",
                    v2_type=v2_row.recommendation_type if v2_row else "NEW_OPPORTUNITY",
                ),
            )
        )

    entries.sort(key=lambda e: abs((e.rank_change or 0)), reverse=True)
    return RecommendationV2ComparisonRead(
        entries=entries[:limit],
        books_moved_up=moved_up,
        books_moved_down=moved_down,
        v1_sample_size=len(v1_ranked),
        v2_sample_size=len(v2_ranked),
    )
