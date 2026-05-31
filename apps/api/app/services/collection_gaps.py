from __future__ import annotations

from sqlmodel import Session, select

from app.models.collection_gap import CollectionGap
from app.schemas.collection_gap import CollectionGapRead, CollectionGapSummaryRead
from app.services.collection_gap_engine import generate_collection_gaps


def _gap_identity_key(*, publisher: str, series_name: str, issue_number: str) -> tuple[str, str, str]:
    return (
        publisher.strip().lower(),
        series_name.strip().lower(),
        issue_number.strip().lower(),
    )


def latest_collection_gap_rows(session: Session, *, owner_user_id: int) -> dict[tuple[str, str, str], CollectionGap]:
    rows = session.exec(
        select(CollectionGap)
        .where(CollectionGap.owner_user_id == owner_user_id)
        .order_by(CollectionGap.created_at.desc(), CollectionGap.id.desc())
    ).all()
    latest: dict[tuple[str, str, str], CollectionGap] = {}
    for row in rows:
        key = _gap_identity_key(
            publisher=row.publisher,
            series_name=row.series_name,
            issue_number=row.issue_number,
        )
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: CollectionGap) -> CollectionGapRead:
    return CollectionGapRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        gap_type=row.gap_type,  # type: ignore[arg-type]
        completion_percent=float(row.completion_percent),
        priority=row.priority,  # type: ignore[arg-type]
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
    )


def persist_collection_gaps(session: Session, *, owner_user_id: int) -> int:
    candidates = generate_collection_gaps(session, owner_user_id=owner_user_id)
    latest = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    created = 0
    for candidate in candidates:
        key = _gap_identity_key(
            publisher=candidate.publisher,
            series_name=candidate.series_name,
            issue_number=candidate.issue_number,
        )
        prior = latest.get(key)
        if prior is not None:
            if (
                prior.priority == candidate.priority
                and prior.rationale == candidate.rationale
            ):
                continue
        row = CollectionGap(
            owner_user_id=owner_user_id,
            publisher=candidate.publisher,
            series_name=candidate.series_name,
            issue_number=candidate.issue_number,
            gap_type=candidate.gap_type,
            completion_percent=candidate.completion_percent,
            priority=candidate.priority,
            rationale=candidate.rationale,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def list_collection_gaps(
    session: Session,
    *,
    owner_user_id: int,
    priority: str | None = None,
    gap_type: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CollectionGapRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    items: list[CollectionGapRead] = []
    for row in latest.values():
        if priority and row.priority != priority.strip().upper():
            continue
        if gap_type and row.gap_type != gap_type.strip().upper():
            continue
        if publisher and publisher.strip().lower() not in row.publisher.lower():
            continue
        items.append(_to_read(row))
    items.sort(
        key=lambda r: (
            -{"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(r.priority, 0),
            r.publisher.lower(),
            r.series_name.lower(),
            r.issue_number,
        )
    )
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_collection_gaps(
    session: Session,
    *,
    owner_user_id: int,
    priority: str | None = None,
    gap_type: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CollectionGapRead], int]:
    persist_collection_gaps(session, owner_user_id=owner_user_id)
    return list_collection_gaps(
        session,
        owner_user_id=owner_user_id,
        priority=priority,
        gap_type=gap_type,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_collection_gap_summary(session: Session, *, owner_user_id: int) -> CollectionGapSummaryRead:
    latest = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    by_priority: dict[str, int] = {}
    by_gap_type: dict[str, int] = {}
    completion_sum = 0.0
    for row in latest.values():
        by_priority[row.priority] = by_priority.get(row.priority, 0) + 1
        by_gap_type[row.gap_type] = by_gap_type.get(row.gap_type, 0) + 1
        completion_sum += float(row.completion_percent)
    count = len(latest)
    return CollectionGapSummaryRead(
        total_gaps=count,
        by_priority=by_priority,
        by_gap_type=by_gap_type,
        average_completion_percent=round(completion_sum / count, 1) if count else 0.0,
    )
