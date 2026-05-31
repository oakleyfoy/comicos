from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.spec_intelligence import SpecScore
from app.schemas.spec_intelligence import SpecAgentExecutionRead, SpecScoreRead
from app.services.spec_intelligence import AGENT_SPEC_SCORING, run_with_spec_execution

PUBLISHER_STRENGTH = {
    "MARVEL": 10.0,
    "DC": 9.0,
    "IMAGE": 8.0,
    "IDW": 6.0,
    "BOOM!": 5.0,
}

SIGNAL_WEIGHTS = {
    "NEW_NUMBER_ONE": 18.0,
    "FIRST_APPEARANCE": 24.0,
    "NEW_CHARACTER": 20.0,
    "ORIGIN_ISSUE": 15.0,
    "ANNIVERSARY_ISSUE": 8.0,
    "MILESTONE_NUMBERING": 12.0,
    "DEATH_ISSUE": 14.0,
    "STATUS_QUO_CHANGE": 10.0,
    "VARIANT_RATIO": 6.0,
    "INCENTIVE_VARIANT": 8.0,
    "HIGH_RATIO_VARIANT": 12.0,
    "OPEN_ORDER_VARIANT": 3.0,
}


def _score_grade(score: float) -> str:
    if score >= 50:
        return "BUY"
    if score >= 25:
        return "WATCH"
    return "PASS"


def _latest_score_by_issue(session: Session, *, issue_ids: list[int]) -> dict[int, SpecScore]:
    rows = (
        session.exec(
            select(SpecScore)
            .where(SpecScore.release_issue_id.in_(issue_ids))
            .order_by(SpecScore.created_at.desc(), SpecScore.id.desc())
        ).all()
        if issue_ids
        else []
    )
    latest: dict[int, SpecScore] = {}
    for row in rows:
        if row.release_issue_id not in latest:
            latest[row.release_issue_id] = row
    return latest


def build_spec_score(
    session: Session,
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> SpecScore:
    signals = session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == int(issue.id or 0))).all()
    variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == int(issue.id or 0))).all()
    series_issue_count = len(
        session.exec(select(ReleaseIssue).where(ReleaseIssue.series_id == issue.series_id)).all()
    )
    publisher_bonus = PUBLISHER_STRENGTH.get(series.publisher.upper(), 4.0)
    signal_breakdown: dict[str, float] = {}
    score = publisher_bonus + min(series_issue_count, 10)
    for signal in signals:
        added = SIGNAL_WEIGHTS.get(signal.signal_type, 0.0)
        if signal.signal_type == "VARIANT_RATIO":
            ratio = signal.signal_payload_json.get("ratio_value")
            if isinstance(ratio, int):
                added += min(float(ratio) / 10.0, 10.0)
        score += added
        signal_breakdown[signal.signal_type] = signal_breakdown.get(signal.signal_type, 0.0) + added
    creator_bonus = sum(2.0 for variant in variants if variant.cover_artist)
    score += min(creator_bonus, 6.0)
    confidence = round(min(0.98, 0.4 + len(signals) * 0.08 + min(len(variants), 3) * 0.05), 3)
    clamped = round(max(0.0, min(100.0, score)), 2)
    return SpecScore(
        release_issue_id=int(issue.id or 0),
        score_value=clamped,
        score_grade=_score_grade(clamped),
        confidence_score=confidence,
        score_payload_json={
            "publisher_strength": publisher_bonus,
            "series_history_count": series_issue_count,
            "signal_breakdown": signal_breakdown,
            "variant_count": len(variants),
            "creator_bonus": min(creator_bonus, 6.0),
        },
    )


def run_spec_scoring(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[SpecScoreRead], SpecAgentExecutionRead]:
    def runner():
        created: list[SpecScore] = []
        issues = session.exec(
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
        ).all()
        latest = _latest_score_by_issue(session, issue_ids=[int(issue.id or 0) for issue, _ in issues])
        for issue, series in issues:
            candidate = build_spec_score(session, issue=issue, series=series)
            previous = latest.get(int(issue.id or 0))
            if previous is not None and previous.score_payload_json == candidate.score_payload_json and previous.score_value == candidate.score_value:
                continue
            session.add(candidate)
            created.append(candidate)
        session.commit()
        for row in created:
            session.refresh(row)
        return [SpecScoreRead.model_validate(row) for row in created]

    result, execution = run_with_spec_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_SPEC_SCORING,
        runner=runner,
    )
    return result, SpecAgentExecutionRead.model_validate(execution)


def list_scores_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(SpecScore)
        .join(ReleaseIssue, SpecScore.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecScore.created_at.desc(), SpecScore.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [SpecScoreRead.model_validate(row) for row in page], len(rows)
