from __future__ import annotations

from sqlmodel import Session, select

from app.models.collected_run import CollectedRun
from app.schemas.collected_run import CollectedRunRead, CollectedRunSummaryRead
from app.services.collected_run_engine import CollectedRunCandidate, generate_collected_runs


def _run_identity_key(*, publisher: str, series_name: str) -> tuple[str, str]:
    return (
        publisher.strip().lower(),
        series_name.strip().lower(),
    )


def latest_collected_run_rows(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], CollectedRun]:
    rows = session.exec(
        select(CollectedRun)
        .where(CollectedRun.owner_user_id == owner_user_id)
        .order_by(CollectedRun.created_at.desc(), CollectedRun.id.desc())
    ).all()
    latest: dict[tuple[str, str], CollectedRun] = {}
    for row in rows:
        key = _run_identity_key(publisher=row.publisher, series_name=row.series_name)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: CollectedRun) -> CollectedRunRead:
    return CollectedRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        publisher=row.publisher,
        series_name=row.series_name,
        latest_owned_issue=row.latest_owned_issue,
        total_owned_issues=int(row.total_owned_issues),
        run_status=row.run_status,  # type: ignore[arg-type]
        created_at=row.created_at.isoformat(),
    )


def _snapshot_unchanged(prior: CollectedRun, candidate: CollectedRunCandidate) -> bool:
    return (
        prior.latest_owned_issue == candidate.latest_owned_issue
        and prior.total_owned_issues == candidate.total_owned_issues
        and prior.run_status == candidate.run_status
    )


def persist_collected_runs(session: Session, *, owner_user_id: int) -> int:
    candidates = generate_collected_runs(session, owner_user_id=owner_user_id)
    latest = latest_collected_run_rows(session, owner_user_id=owner_user_id)
    created = 0
    for candidate in candidates:
        key = _run_identity_key(publisher=candidate.publisher, series_name=candidate.series_name)
        prior = latest.get(key)
        if prior is not None and _snapshot_unchanged(prior, candidate):
            continue
        row = CollectedRun(
            owner_user_id=owner_user_id,
            publisher=candidate.publisher,
            series_name=candidate.series_name,
            latest_owned_issue=candidate.latest_owned_issue,
            total_owned_issues=candidate.total_owned_issues,
            run_status=candidate.run_status,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def list_collected_runs(
    session: Session,
    *,
    owner_user_id: int,
    run_status: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CollectedRunRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = latest_collected_run_rows(session, owner_user_id=owner_user_id)
    items: list[CollectedRunRead] = []
    for row in latest.values():
        if run_status and row.run_status.upper() != run_status.strip().upper():
            continue
        if publisher and publisher.strip().lower() not in row.publisher.lower():
            continue
        items.append(_to_read(row))
    items.sort(key=lambda item: (item.publisher.lower(), item.series_name.lower()))
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_collected_runs(
    session: Session,
    *,
    owner_user_id: int,
    run_status: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CollectedRunRead], int]:
    persist_collected_runs(session, owner_user_id=owner_user_id)
    return list_collected_runs(
        session,
        owner_user_id=owner_user_id,
        run_status=run_status,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_collected_run_summary(session: Session, *, owner_user_id: int) -> CollectedRunSummaryRead:
    latest = latest_collected_run_rows(session, owner_user_id=owner_user_id)
    summary = CollectedRunSummaryRead()
    summary.total_runs = len(latest)
    last_refreshed: str | None = None
    for row in latest.values():
        if row.run_status == "ACTIVE":
            summary.active_runs += 1
        elif row.run_status == "INACTIVE":
            summary.inactive_runs += 1
        elif row.run_status == "COMPLETE":
            summary.complete_runs += 1
        else:
            summary.unknown_runs += 1
        stamp = row.created_at.isoformat()
        if last_refreshed is None or stamp > last_refreshed:
            last_refreshed = stamp
    summary.last_refreshed_at = last_refreshed
    return summary
