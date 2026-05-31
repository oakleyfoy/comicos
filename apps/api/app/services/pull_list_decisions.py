from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session, select

from app.models.pull_list import PullListDecision
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.recommendation_v2 import RecommendationScoreV2
from app.schemas.pull_list_decision import PullListDecisionRead
from app.services.pull_list_decision_engine import evaluate_pull_list_decision
from app.services.recommendation_v2_engine import _latest_scores_by_issue


def _reasons_from_explanation(explanation: str) -> list[str]:
    if not explanation:
        return []
    try:
        parsed = json.loads(explanation)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        pass
    return [explanation]


def _encode_reasons(reasons: tuple[str, ...]) -> str:
    return json.dumps(list(reasons))


def _to_read(
    session: Session,
    *,
    row: PullListDecision,
    v2: RecommendationScoreV2 | None,
) -> PullListDecisionRead:
    issue = session.get(ReleaseIssue, row.release_id)
    series = session.get(ReleaseSeries, issue.series_id) if issue else None
    return PullListDecisionRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        release_id=int(row.release_id),
        decision_type=row.decision_type,  # type: ignore[arg-type]
        confidence_score=float(row.confidence_score),
        explanation=row.explanation,
        reasons=_reasons_from_explanation(row.explanation),
        created_at=row.created_at,
        comic_title=issue.title if issue else "",
        issue_number=issue.issue_number if issue else "",
        publisher=series.publisher if series else "",
        series_name=series.series_name if series else "",
        release_date=issue.release_date if issue else None,
        foc_date=issue.foc_date if issue else None,
        recommendation_tier=v2.recommendation_tier if v2 else None,
        recommendation_score=float(v2.total_score) if v2 else None,
    )


def _latest_decision_rows(session: Session, *, owner_user_id: int) -> dict[int, PullListDecision]:
    rows = session.exec(
        select(PullListDecision)
        .where(PullListDecision.owner_user_id == owner_user_id)
        .order_by(PullListDecision.created_at.desc(), PullListDecision.id.desc())
    ).all()
    latest: dict[int, PullListDecision] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def generate_pull_list_decisions(session: Session, *, owner_user_id: int) -> int:
    """Append-only decision generation for all owner releases with V2 scores and pull-list issues."""
    from app.models.pull_list import PullList, PullListIssue

    v2_by_issue = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    latest = _latest_decision_rows(session, owner_user_id=owner_user_id)
    target_ids: set[int] = set(v2_by_issue.keys())
    for issue_row in session.exec(
        select(PullListIssue)
        .join(PullList, PullList.id == PullListIssue.pull_list_id)
        .where(PullList.owner_user_id == owner_user_id)
    ).all():
        target_ids.add(int(issue_row.release_id))
    created = 0
    for release_id in sorted(target_ids):
        issue = session.get(ReleaseIssue, release_id)
        if issue is None or issue.owner_user_id != owner_user_id:
            continue
        series = session.get(ReleaseSeries, issue.series_id)
        if series is None:
            continue
        v2 = v2_by_issue.get(release_id)
        result = evaluate_pull_list_decision(
            session, owner_user_id=owner_user_id, issue=issue, series=series, v2=v2
        )
        explanation = _encode_reasons(result.reasons)
        prior = latest.get(release_id)
        if prior is not None:
            if (
                prior.decision_type == result.decision_type
                and prior.explanation == explanation
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
            ):
                continue
        session.add(
            PullListDecision(
                owner_user_id=owner_user_id,
                release_id=release_id,
                decision_type=result.decision_type,
                confidence_score=result.confidence_score,
                explanation=explanation,
            )
        )
        created += 1
    session.commit()
    return created


def list_pull_list_decisions(
    session: Session,
    *,
    owner_user_id: int,
    decision_type: str | None = None,
    tier: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PullListDecisionRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    v2_by_issue = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    latest = _latest_decision_rows(session, owner_user_id=owner_user_id)
    items: list[PullListDecisionRead] = []
    for release_id in sorted(latest.keys()):
        row = latest[release_id]
        if decision_type and row.decision_type != decision_type.strip().upper():
            continue
        v2 = v2_by_issue.get(release_id)
        if tier and (v2 is None or v2.recommendation_tier != tier.strip().upper()):
            continue
        read = _to_read(session, row=row, v2=v2)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.confidence_score, r.release_id))
    total = len(items)
    page = items[offset : offset + limit]
    return page, total


def get_pull_list_decision(session: Session, *, owner_user_id: int, decision_id: int) -> PullListDecisionRead:
    row = session.get(PullListDecision, decision_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Pull list decision not found.")
    v2 = _latest_scores_by_issue(session, owner_user_id=owner_user_id).get(row.release_id)
    return _to_read(session, row=row, v2=v2)


def list_upcoming_pull_list_decisions(
    session: Session,
    *,
    owner_user_id: int,
    decision_type: str | None = None,
    tier: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PullListDecisionRead], int]:
    today = date.today()
    rows, _ = list_pull_list_decisions(
        session,
        owner_user_id=owner_user_id,
        decision_type=decision_type,
        tier=tier,
        publisher=publisher,
        limit=500,
        offset=0,
    )
    upcoming = [
        r
        for r in rows
        if (r.release_date is None or r.release_date >= today)
        and r.decision_type in {"START_RUN", "CONTINUE_RUN", "WATCH"}
    ]
    upcoming.sort(key=lambda r: (r.release_date or date.max, -r.confidence_score))
    total = len(upcoming)
    return upcoming[offset : offset + limit], total
