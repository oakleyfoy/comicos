"""P98-01 universe publisher build + list."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVolume
from app.schemas.master_universe import (
    MasterUniversePublisherListResponse,
    MasterUniversePublisherNode,
    MasterUniverseSummary,
)
from app.services.universe.universe_common import (
    clamp_limit,
    clamp_offset,
    normalize_publisher_name,
    publisher_priority_rank,
    synthetic_publisher_id,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_publisher(
    session: Session,
    *,
    name: str,
    comicvine_publisher_id: int | None = None,
    country: str | None = None,
) -> UniversePublisher:
    label = (name or "").strip() or "Unknown"
    normalized = normalize_publisher_name(label)
    row = session.exec(
        select(UniversePublisher).where(UniversePublisher.normalized_name == normalized)
    ).first()
    cv_id = comicvine_publisher_id if comicvine_publisher_id and comicvine_publisher_id > 0 else synthetic_publisher_id(normalized)
    if row is None:
        row = UniversePublisher(
            name=label,
            normalized_name=normalized,
            comicvine_publisher_id=cv_id,
            country=country,
            active=True,
        )
        session.add(row)
        session.flush()
        return row
    row.name = label
    row.updated_at = _utc_now()
    if comicvine_publisher_id and comicvine_publisher_id > 0:
        row.comicvine_publisher_id = comicvine_publisher_id
    elif row.comicvine_publisher_id is None:
        row.comicvine_publisher_id = cv_id
    if country:
        row.country = country
    session.add(row)
    session.flush()
    return row


def build_publishers_from_discovered_volumes(session: Session) -> dict[str, int]:
    """Import every publisher name seen in comicvine_volume_universe."""
    stats = {"created": 0, "updated": 0, "publishers": 0}
    names = session.exec(select(ComicVineVolumeUniverse.publisher).distinct()).all()
    for raw in names:
        label = (raw or "").strip() or "Unknown"
        normalized = normalize_publisher_name(label)
        existing = session.exec(
            select(UniversePublisher).where(UniversePublisher.normalized_name == normalized)
        ).first()
        upsert_publisher(session, name=label)
        if existing is None:
            stats["created"] += 1
        else:
            stats["updated"] += 1
    session.commit()
    stats["publishers"] = int(
        session.exec(select(func.count()).select_from(UniversePublisher)).one()
    )
    return stats


def _summary(session: Session) -> MasterUniverseSummary:
    pub = int(session.exec(select(func.count()).select_from(UniversePublisher)).one())
    vol = int(session.exec(select(func.count()).select_from(UniverseVolume)).one())
    iss = int(session.exec(select(func.count()).select_from(UniverseIssue)).one())
    from app.models.universe import UniverseVariant

    var = int(session.exec(select(func.count()).select_from(UniverseVariant)).one())
    return MasterUniverseSummary(
        publisher_count=pub,
        volume_count=vol,
        issue_count=iss,
        variant_count=var,
    )


def list_publishers(
    session: Session,
    *,
    search: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniversePublisherListResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    stmt = select(UniversePublisher).where(UniversePublisher.active.is_(True))
    if search and search.strip():
        needle = f"%{search.strip()}%"
        stmt = stmt.where(UniversePublisher.name.ilike(needle))
    rows = list(session.exec(stmt.order_by(UniversePublisher.name.asc())).all())

    vol_counts = {
        int(pid): int(cnt)
        for pid, cnt in session.exec(
            select(UniverseVolume.publisher_id, func.count(UniverseVolume.id)).group_by(UniverseVolume.publisher_id)
        ).all()
    }
    issue_counts: dict[int, int] = {}
    for pub_id, cnt in session.exec(
        select(UniverseVolume.publisher_id, func.count(UniverseIssue.id))
        .join(UniverseIssue, UniverseIssue.volume_id == UniverseVolume.id)
        .group_by(UniverseVolume.publisher_id)
    ).all():
        issue_counts[int(pub_id)] = int(cnt)

    def sort_key(row: UniversePublisher) -> tuple:
        rank = publisher_priority_rank(row.normalized_name)
        return (rank if rank is not None else 999, row.name.lower())

    rows.sort(key=sort_key)
    total_count = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MasterUniversePublisherNode(
            id=int(row.id or 0),
            name=row.name,
            comicvine_publisher_id=row.comicvine_publisher_id,
            volume_count=vol_counts.get(int(row.id or 0), 0),
            issue_count=issue_counts.get(int(row.id or 0), 0),
        )
        for row in page
    ]
    return MasterUniversePublisherListResponse(
        summary=_summary(session),
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
