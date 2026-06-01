from __future__ import annotations

from sqlmodel import Session, select

from app.models.next_issue import NextIssue
from app.schemas.next_issue import NextIssueListRead, NextIssueRead
from app.services.next_issue_engine import NextIssueCandidate, generate_next_issues


def _series_identity_key(*, series_name: str) -> str:
    return series_name.strip().lower()


def latest_next_issue_rows(session: Session, *, owner_user_id: int) -> dict[str, NextIssue]:
    rows = session.exec(
        select(NextIssue)
        .where(NextIssue.owner_user_id == owner_user_id)
        .order_by(NextIssue.created_at.desc(), NextIssue.id.desc())
    ).all()
    latest: dict[str, NextIssue] = {}
    for row in rows:
        key = _series_identity_key(series_name=row.series_name)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: NextIssue) -> NextIssueRead:
    return NextIssueRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        series_name=row.series_name,
        current_issue=row.current_issue,
        next_issue=row.next_issue,
        confidence=float(row.confidence),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
    )


def _snapshot_unchanged(prior: NextIssue, candidate: NextIssueCandidate) -> bool:
    return (
        prior.current_issue == candidate.current_issue
        and prior.next_issue == candidate.next_issue
        and abs(float(prior.confidence) - float(candidate.confidence)) < 1e-9
        and prior.rationale == candidate.rationale
    )


def persist_next_issues(session: Session, *, owner_user_id: int) -> int:
    candidates = generate_next_issues(session, owner_user_id=owner_user_id)
    latest = latest_next_issue_rows(session, owner_user_id=owner_user_id)
    created = 0
    for candidate in candidates:
        key = _series_identity_key(series_name=candidate.series_name)
        prior = latest.get(key)
        if prior is not None and _snapshot_unchanged(prior, candidate):
            continue
        row = NextIssue(
            owner_user_id=owner_user_id,
            series_name=candidate.series_name,
            current_issue=candidate.current_issue,
            next_issue=candidate.next_issue,
            confidence=candidate.confidence,
            rationale=candidate.rationale,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def list_next_issues(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[NextIssueRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = latest_next_issue_rows(session, owner_user_id=owner_user_id)
    items = [_to_read(row) for row in sorted(latest.values(), key=lambda r: r.series_name.lower())]
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_next_issues(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[NextIssueRead], int]:
    from app.services.collected_runs import persist_collected_runs

    persist_collected_runs(session, owner_user_id=owner_user_id)
    persist_next_issues(session, owner_user_id=owner_user_id)
    return list_next_issues(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
