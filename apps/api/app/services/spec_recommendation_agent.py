from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.models.spec_intelligence import SpecRecommendation, SpecScore
from app.schemas.spec_intelligence import SpecAgentExecutionRead, SpecRecommendationRead
from app.services.personalization_agent import score_issue_for_owner
from app.services.spec_intelligence import AGENT_SPEC_RECOMMENDATION, run_with_spec_execution


def latest_score_rows_for_owner(session: Session, *, owner_user_id: int) -> list[SpecScore]:
    rows = session.exec(
        select(SpecScore)
        .join(ReleaseIssue, SpecScore.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecScore.created_at.desc(), SpecScore.id.desc())
    ).all()
    latest: dict[int, SpecScore] = {}
    for row in rows:
        if row.release_issue_id not in latest:
            latest[row.release_issue_id] = row
    return list(latest.values())


def _recommendation_type(score: float) -> str:
    if score >= 82:
        return "STRONG_BUY"
    if score >= 62:
        return "BUY"
    if score >= 38:
        return "WATCH"
    return "PASS"


def _build_reason(signals: list[str], matched_preferences: list[str], recommendation_type: str) -> str:
    parts = [f"{recommendation_type} based on release intelligence signals"]
    if signals:
        parts.append(f"signals: {', '.join(signals[:4])}")
    if matched_preferences:
        parts.append(f"matched preferences: {', '.join(matched_preferences[:4])}")
    parts.append("advisory only; no order or inventory mutation.")
    return ". ".join(parts)


def run_spec_recommendations(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[SpecRecommendationRead], SpecAgentExecutionRead]:
    def runner():
        created: list[SpecRecommendation] = []
        latest_scores = latest_score_rows_for_owner(session, owner_user_id=owner_user_id)
        issues = {
            int(issue.id or 0): (issue, series)
            for issue, series in session.exec(
                select(ReleaseIssue, ReleaseSeries)
                .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
                .where(ReleaseIssue.owner_user_id == owner_user_id)
            ).all()
        }
        for score in latest_scores:
            issue_pair = issues.get(score.release_issue_id)
            if issue_pair is None:
                continue
            issue, series = issue_pair
            personalization = score_issue_for_owner(
                session,
                owner_user_id=owner_user_id,
                issue=issue,
                series=series,
                base_score=score.score_value,
            )
            signals = [
                row.signal_type
                for row in session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == int(issue.id or 0))).all()
            ]
            adjusted_score = float(personalization["adjusted_score"])
            rec_type = _recommendation_type(adjusted_score)
            recommendation = SpecRecommendation(
                release_issue_id=score.release_issue_id,
                recommendation_type=rec_type,
                recommendation_score=adjusted_score,
                confidence_score=round(min(0.99, score.confidence_score + 0.05), 3),
                recommendation_reason=_build_reason(
                    signals,
                    list(personalization["matched_preferences"]),
                    rec_type,
                ),
            )
            session.add(recommendation)
            created.append(recommendation)
        session.commit()
        for row in created:
            session.refresh(row)
        return [SpecRecommendationRead.model_validate(row) for row in created]

    result, execution = run_with_spec_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_SPEC_RECOMMENDATION,
        runner=runner,
    )
    return result, SpecAgentExecutionRead.model_validate(execution)


def list_recommendations_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(SpecRecommendation)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecRecommendation.created_at.desc(), SpecRecommendation.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [SpecRecommendationRead.model_validate(row) for row in page], len(rows)
