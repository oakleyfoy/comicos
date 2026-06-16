"""P98-05 master universe tree search."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.universe import UniverseIssue, UniversePublisher, UniverseVariant, UniverseVolume
from app.schemas.master_universe import MasterUniverseSearchHit, MasterUniverseSearchResponse
from app.services.universe.universe_common import clamp_limit, clamp_offset


def search_master_universe(
    session: Session,
    *,
    query: str,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseSearchResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    q = query.strip()
    if not q:
        return MasterUniverseSearchResponse(query=q, hits=[], total_count=0, limit=limit, offset=offset)

    hits: list[MasterUniverseSearchHit] = []
    needle = q.lower()

    for pub in session.exec(select(UniversePublisher).limit(500)).all():
        if needle in pub.name.lower():
            hits.append(
                MasterUniverseSearchHit(
                    hit_type="publisher",
                    publisher_id=int(pub.id or 0),
                    publisher_name=pub.name,
                    status="active" if pub.active else "inactive",
                )
            )

    for vol in session.exec(
        select(UniverseVolume).where(UniverseVolume.name.ilike(f"%{q}%")).limit(200)
    ).all():
        pub = session.get(UniversePublisher, vol.publisher_id)
        hits.append(
            MasterUniverseSearchHit(
                hit_type="volume",
                publisher_id=int(pub.id or 0) if pub else None,
                publisher_name=pub.name if pub else None,
                volume_id=int(vol.id or 0),
                volume_name=vol.name,
            )
        )

    for issue in session.exec(
        select(UniverseIssue)
        .where(
            (UniverseIssue.issue_number.ilike(f"%{q}%"))
            | (UniverseIssue.issue_title.ilike(f"%{q}%"))
        )
        .limit(200)
    ).all():
        vol = session.get(UniverseVolume, issue.volume_id)
        pub = session.get(UniversePublisher, vol.publisher_id) if vol else None
        hits.append(
            MasterUniverseSearchHit(
                hit_type="issue",
                publisher_name=pub.name if pub else None,
                volume_id=int(vol.id or 0) if vol else None,
                volume_name=vol.name if vol else None,
                issue_id=int(issue.id or 0),
                issue_number=issue.issue_number,
                status=issue.status,
            )
        )

    for variant in session.exec(
        select(UniverseVariant).where(UniverseVariant.variant_name.ilike(f"%{q}%")).limit(200)
    ).all():
        issue = session.get(UniverseIssue, variant.issue_id)
        vol = session.get(UniverseVolume, issue.volume_id) if issue else None
        hits.append(
            MasterUniverseSearchHit(
                hit_type="variant",
                volume_name=vol.name if vol else None,
                issue_id=int(issue.id or 0) if issue else None,
                issue_number=issue.issue_number if issue else None,
                variant_id=int(variant.id or 0),
                variant_label=variant.variant_name or variant.variant_type,
                status=variant.status,
            )
        )

    total_count = len(hits)
    page = hits[offset : offset + limit]
    return MasterUniverseSearchResponse(
        query=q,
        hits=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
