"""P98-02 universe volume build + list."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVolume
from app.schemas.master_universe import MasterUniverseVolumeListResponse, MasterUniverseVolumeNode
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.universe.universe_common import clamp_limit, clamp_offset
from app.services.universe.universe_publisher_service import upsert_publisher


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_volume(
    session: Session,
    *,
    publisher: UniversePublisher,
    comicvine_volume_id: int,
    name: str,
    start_year: int | None,
    count_of_issues: int | None,
) -> UniverseVolume:
    row = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == comicvine_volume_id)
    ).first()
    normalized = normalize_series_name(name)
    if row is None:
        row = UniverseVolume(
            comicvine_volume_id=comicvine_volume_id,
            publisher_id=int(publisher.id or 0),
            name=name,
            normalized_name=normalized,
            start_year=start_year,
            count_of_issues=count_of_issues,
            volume_status="active",
        )
        session.add(row)
        session.flush()
        return row
    row.publisher_id = int(publisher.id or 0)
    row.name = name
    row.normalized_name = normalized
    row.start_year = start_year
    row.count_of_issues = count_of_issues
    row.updated_at = _utc_now()
    session.add(row)
    session.flush()
    return row


def build_volumes_from_discovered_universe(session: Session) -> dict[str, int]:
    stats = {"created": 0, "updated": 0, "volumes": 0}
    for universe in session.exec(select(ComicVineVolumeUniverse).order_by(ComicVineVolumeUniverse.volume_id.asc())).all():
        pub = upsert_publisher(session, name=universe.publisher or "Unknown")
        existing = session.exec(
            select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == int(universe.volume_id))
        ).first()
        upsert_volume(
            session,
            publisher=pub,
            comicvine_volume_id=int(universe.volume_id),
            name=universe.name,
            start_year=universe.start_year,
            count_of_issues=universe.count_of_issues,
        )
        if existing is None:
            stats["created"] += 1
        else:
            stats["updated"] += 1
    session.commit()
    stats["volumes"] = int(session.exec(select(func.count()).select_from(UniverseVolume)).one())
    return stats


def list_volumes_for_publisher(
    session: Session,
    *,
    publisher_id: int,
    search: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseVolumeListResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    publisher = session.get(UniversePublisher, publisher_id)
    if publisher is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")

    stmt = select(UniverseVolume).where(UniverseVolume.publisher_id == publisher_id)
    if search and search.strip():
        stmt = stmt.where(UniverseVolume.name.ilike(f"%{search.strip()}%"))
    rows = list(session.exec(stmt.order_by(UniverseVolume.name.asc())).all())
    shell_counts = {
        int(vid): int(cnt)
        for vid, cnt in session.exec(
            select(UniverseIssue.volume_id, func.count(UniverseIssue.id)).group_by(UniverseIssue.volume_id)
        ).all()
    }
    total_count = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MasterUniverseVolumeNode(
            id=int(row.id or 0),
            comicvine_volume_id=int(row.comicvine_volume_id),
            publisher_id=int(row.publisher_id),
            name=row.name,
            start_year=row.start_year,
            count_of_issues=row.count_of_issues,
            issue_shell_count=shell_counts.get(int(row.id or 0), 0),
            volume_status=row.volume_status,
        )
        for row in page
    ]
    return MasterUniverseVolumeListResponse(
        publisher_id=publisher_id,
        publisher_name=publisher.name,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
