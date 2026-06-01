from __future__ import annotations

from sqlmodel import Session, select

from app.models.future_release_action import FutureReleaseAction
from app.schemas.future_release_action import FutureReleaseActionRead
from app.services.future_release_action_engine import (
    FutureReleaseActionCandidate,
    generate_future_release_actions,
)
from app.services.future_release_matches import latest_future_release_match_rows, persist_future_release_matches


def _action_identity_key(*, series_name: str, issue_number: str) -> tuple[str, str]:
    return (series_name.strip().lower(), issue_number.strip().lower())


def latest_future_release_action_rows(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], FutureReleaseAction]:
    rows = session.exec(
        select(FutureReleaseAction)
        .where(FutureReleaseAction.owner_user_id == owner_user_id)
        .order_by(FutureReleaseAction.created_at.desc(), FutureReleaseAction.id.desc())
    ).all()
    latest: dict[tuple[str, str], FutureReleaseAction] = {}
    for row in rows:
        key = _action_identity_key(series_name=row.series_name, issue_number=row.issue_number)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: FutureReleaseAction) -> FutureReleaseActionRead:
    return FutureReleaseActionRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        series_name=row.series_name,
        issue_number=row.issue_number,
        action_type=row.action_type,  # type: ignore[arg-type]
        priority_score=float(row.priority_score),
        foc_date=row.foc_date.isoformat() if row.foc_date else None,
        release_id=int(row.release_id) if row.release_id is not None else None,
        created_at=row.created_at.isoformat(),
    )


def _snapshot_unchanged(prior: FutureReleaseAction, candidate: FutureReleaseActionCandidate) -> bool:
    return (
        prior.action_type == candidate.action_type
        and abs(float(prior.priority_score) - float(candidate.priority_score)) < 1e-9
        and prior.foc_date == candidate.foc_date
        and prior.release_id == candidate.release_id
    )


def persist_future_release_actions(session: Session, *, owner_user_id: int) -> int:
    matches = list(latest_future_release_match_rows(session, owner_user_id=owner_user_id).values())
    candidates = generate_future_release_actions(matches)
    latest = latest_future_release_action_rows(session, owner_user_id=owner_user_id)
    created = 0
    for candidate in candidates:
        key = _action_identity_key(series_name=candidate.series_name, issue_number=candidate.issue_number)
        prior = latest.get(key)
        if prior is not None and _snapshot_unchanged(prior, candidate):
            continue
        row = FutureReleaseAction(
            owner_user_id=owner_user_id,
            series_name=candidate.series_name,
            issue_number=candidate.issue_number,
            action_type=candidate.action_type,
            priority_score=candidate.priority_score,
            foc_date=candidate.foc_date,
            release_id=candidate.release_id,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def list_future_release_actions(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FutureReleaseActionRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = latest_future_release_action_rows(session, owner_user_id=owner_user_id)
    items = [
        _to_read(row)
        for row in sorted(
            latest.values(),
            key=lambda r: (-float(r.priority_score), r.series_name.lower(), r.issue_number),
        )
    ]
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_future_release_actions(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FutureReleaseActionRead], int]:
    from app.services.collected_runs import persist_collected_runs
    from app.services.next_issues import persist_next_issues

    persist_collected_runs(session, owner_user_id=owner_user_id)
    persist_next_issues(session, owner_user_id=owner_user_id)
    persist_future_release_matches(session, owner_user_id=owner_user_id)
    persist_future_release_actions(session, owner_user_id=owner_user_id)
    return list_future_release_actions(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
