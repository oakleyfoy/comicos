from __future__ import annotations

from sqlmodel import Session, select

from app.models.future_release_match import FutureReleaseMatch
from app.schemas.future_release_match import FutureReleaseMatchRead
from app.services.future_release_match_engine import FutureReleaseMatchCandidate, generate_future_release_matches


def _match_identity_key(*, series_name: str, issue_number: str) -> tuple[str, str]:
    return (series_name.strip().lower(), issue_number.strip().lower())


def latest_future_release_match_rows(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], FutureReleaseMatch]:
    rows = session.exec(
        select(FutureReleaseMatch)
        .where(FutureReleaseMatch.owner_user_id == owner_user_id)
        .order_by(FutureReleaseMatch.created_at.desc(), FutureReleaseMatch.id.desc())
    ).all()
    latest: dict[tuple[str, str], FutureReleaseMatch] = {}
    for row in rows:
        key = _match_identity_key(series_name=row.series_name, issue_number=row.issue_number)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: FutureReleaseMatch) -> FutureReleaseMatchRead:
    return FutureReleaseMatchRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        series_name=row.series_name,
        issue_number=row.issue_number,
        publisher=row.publisher,
        foc_date=row.foc_date.isoformat() if row.foc_date else None,
        release_date=row.release_date.isoformat() if row.release_date else None,
        release_id=int(row.release_id),
        variant_count=int(row.variant_count),
        confidence=float(row.confidence),
        created_at=row.created_at.isoformat(),
    )


def _snapshot_unchanged(prior: FutureReleaseMatch, candidate: FutureReleaseMatchCandidate) -> bool:
    return (
        prior.release_id == candidate.release_id
        and prior.publisher == candidate.publisher
        and prior.foc_date == candidate.foc_date
        and prior.release_date == candidate.release_date
        and prior.variant_count == candidate.variant_count
        and abs(float(prior.confidence) - float(candidate.confidence)) < 1e-9
    )


def persist_future_release_matches(session: Session, *, owner_user_id: int) -> int:
    candidates = generate_future_release_matches(session, owner_user_id=owner_user_id)
    latest = latest_future_release_match_rows(session, owner_user_id=owner_user_id)
    created = 0
    for candidate in candidates:
        key = _match_identity_key(series_name=candidate.series_name, issue_number=candidate.issue_number)
        prior = latest.get(key)
        if prior is not None and _snapshot_unchanged(prior, candidate):
            continue
        row = FutureReleaseMatch(
            owner_user_id=owner_user_id,
            series_name=candidate.series_name,
            issue_number=candidate.issue_number,
            publisher=candidate.publisher,
            foc_date=candidate.foc_date,
            release_date=candidate.release_date,
            release_id=candidate.release_id,
            variant_count=candidate.variant_count,
            confidence=candidate.confidence,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def list_future_release_matches(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FutureReleaseMatchRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = latest_future_release_match_rows(session, owner_user_id=owner_user_id)
    items = [
        _to_read(row)
        for row in sorted(latest.values(), key=lambda r: (r.series_name.lower(), r.issue_number))
    ]
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_future_release_matches(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FutureReleaseMatchRead], int]:
    from app.services.collected_runs import persist_collected_runs
    from app.services.next_issues import persist_next_issues

    persist_collected_runs(session, owner_user_id=owner_user_id)
    persist_next_issues(session, owner_user_id=owner_user_id)
    persist_future_release_matches(session, owner_user_id=owner_user_id)
    from app.services.spec_automation import trigger_spec_refresh_after_upstream

    trigger_spec_refresh_after_upstream(session, owner_user_id=owner_user_id)
    return list_future_release_matches(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
