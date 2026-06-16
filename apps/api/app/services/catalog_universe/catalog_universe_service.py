"""Text-only comic universe tree from local DB tables (no ComicVine API calls)."""

from __future__ import annotations

from urllib.parse import unquote

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.schemas.catalog_universe import (
    CatalogUniverseIssueListResponse,
    CatalogUniverseIssueNode,
    CatalogUniversePublisherListResponse,
    CatalogUniversePublisherNode,
    CatalogUniverseSearchHit,
    CatalogUniverseSearchResponse,
    CatalogUniverseSummary,
    CatalogUniverseVolumeListResponse,
    CatalogUniverseVolumeNode,
)
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series

CATALOG_STATUS_CATALOGED = "CATALOGED"
CATALOG_STATUS_DISCOVERED = "DISCOVERED"
CATALOG_STATUS_PLACEHOLDER_ELIGIBLE = "PLACEHOLDER_ELIGIBLE"

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _publisher_label(value: str | None) -> str:
    text = (value or "").strip()
    return text or "Unknown"


def _publisher_key(value: str | None) -> str:
    return normalize_series_name(_publisher_label(value))


def _decode_publisher_path(publisher: str) -> str:
    return unquote(publisher).strip()


def _comicvine_id_from_external(external_source_ids: dict | None) -> int | None:
    bucket = (external_source_ids or {}).get("COMICVINE")
    if not isinstance(bucket, dict) or not bucket:
        return None
    for key in bucket:
        if str(key).startswith("_"):
            continue
        try:
            return int(str(key))
        except ValueError:
            continue
    return None


def _clamp_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return DEFAULT_LIMIT
    return min(int(limit), MAX_LIMIT)


def _clamp_offset(offset: int | None) -> int:
    if offset is None or offset < 0:
        return 0
    return int(offset)


def build_volume_to_series_ids(session: Session) -> dict[int, list[int]]:
    mapping: dict[int, list[int]] = {}
    for series in session.exec(select(CatalogSeries)).all():
        if series.id is None:
            continue
        volume_key = comicvine_volume_id_for_series(series)
        if not volume_key:
            continue
        try:
            volume_id = int(volume_key)
        except ValueError:
            continue
        mapping.setdefault(volume_id, []).append(int(series.id))
    return mapping


def _catalog_issue_counts_by_series(session: Session) -> dict[int, int]:
    return {
        int(series_id): int(count)
        for series_id, count in session.exec(
            select(CatalogIssue.series_id, func.count()).group_by(CatalogIssue.series_id)
        ).all()
        if series_id is not None
    }


def _issue_bounds_for_series_ids(
    session: Session, series_ids: list[int]
) -> tuple[str | None, str | None]:
    if not series_ids:
        return None, None
    rows = session.exec(
        select(CatalogIssue.normalized_issue_number)
        .where(CatalogIssue.series_id.in_(series_ids))
        .order_by(CatalogIssue.normalized_issue_number.asc())
    ).all()
    if not rows:
        return None, None
    numbers = [str(n) for n in rows if n is not None]
    if not numbers:
        return None, None
    return numbers[0], numbers[-1]


def get_universe_summary(session: Session) -> CatalogUniverseSummary:
    universe_volume_count = int(
        session.exec(select(func.count()).select_from(ComicVineVolumeUniverse)).one()
    )
    universe_issue_ceiling = int(
        session.exec(
            select(func.coalesce(func.sum(ComicVineVolumeUniverse.count_of_issues), 0))
        ).one()
    )
    cataloged_issues = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())

    pub_keys: set[str] = set()
    for publisher in session.exec(select(ComicVineVolumeUniverse.publisher).distinct()).all():
        pub_keys.add(_publisher_key(publisher))
    for name in session.exec(select(CatalogPublisher.name)).all():
        pub_keys.add(_publisher_key(name))

    # Catalog series not linked to a ComicVine volume id count as extra volumes.
    volume_to_series = build_volume_to_series_ids(session)
    linked_series = {sid for ids in volume_to_series.values() for sid in ids}
    catalog_only_series = session.exec(select(CatalogSeries)).all()
    extra_volumes = sum(
        1 for s in catalog_only_series if s.id is not None and int(s.id) not in linked_series
    )
    total_volumes = universe_volume_count + extra_volumes

    discovered_only = max(int(universe_issue_ceiling) - cataloged_issues, 0)
    return CatalogUniverseSummary(
        total_publishers=len(pub_keys),
        total_volumes=total_volumes,
        total_issues=max(int(universe_issue_ceiling), cataloged_issues),
        cataloged_issues=cataloged_issues,
        discovered_only_issues=discovered_only,
    )


def list_universe_publishers(
    session: Session,
    *,
    search: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> CatalogUniversePublisherListResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)

    merged: dict[str, CatalogUniversePublisherNode] = {}

    universe_rows = session.exec(
        select(
            ComicVineVolumeUniverse.publisher,
            func.count(),
            func.coalesce(func.sum(ComicVineVolumeUniverse.count_of_issues), 0),
        ).group_by(ComicVineVolumeUniverse.publisher)
    ).all()
    for publisher, volume_count, issue_sum in universe_rows:
        label = _publisher_label(publisher)
        key = _publisher_key(publisher)
        merged[key] = CatalogUniversePublisherNode(
            publisher=label,
            volume_count=int(volume_count),
            issue_count=int(issue_sum or 0),
        )

    issue_counts = _catalog_issue_counts_by_series(session)
    publisher_name_by_id = {
        int(row.id): row.name
        for row in session.exec(select(CatalogPublisher)).all()
        if row.id is not None
    }
    catalog_pub_stats: dict[str, tuple[int, int]] = {}
    for series in session.exec(select(CatalogSeries)).all():
        if series.id is None:
            continue
        pub_name = publisher_name_by_id.get(int(series.publisher_id or 0), "Unknown")
        key = _publisher_key(pub_name)
        vol_inc, iss_inc = catalog_pub_stats.get(key, (0, 0))
        catalog_pub_stats[key] = (vol_inc + 1, iss_inc + issue_counts.get(int(series.id), 0))

    for key, (vol_count, iss_count) in catalog_pub_stats.items():
        display_name = next(
            (n for pid, n in publisher_name_by_id.items() if _publisher_key(n) == key),
            key.replace(" ", " ").title(),
        )
        if key in merged:
            node = merged[key]
            merged[key] = CatalogUniversePublisherNode(
                publisher=node.publisher,
                volume_count=max(node.volume_count, vol_count),
                issue_count=max(node.issue_count, iss_count),
            )
        else:
            merged[key] = CatalogUniversePublisherNode(
                publisher=display_name,
                volume_count=vol_count,
                issue_count=iss_count,
            )

    items = sorted(merged.values(), key=lambda row: row.publisher.lower())
    if search and search.strip():
        needle = search.strip().lower()
        items = [row for row in items if needle in row.publisher.lower()]

    total_count = len(items)
    page = items[offset : offset + limit]
    return CatalogUniversePublisherListResponse(
        summary=get_universe_summary(session),
        items=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def list_volumes_for_publisher(
    session: Session,
    *,
    publisher_path: str,
    search: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> CatalogUniverseVolumeListResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    publisher_label = _decode_publisher_path(publisher_path)
    publisher_match_key = _publisher_key(publisher_label)

    issue_counts = _catalog_issue_counts_by_series(session)
    volume_to_series = build_volume_to_series_ids(session)
    publisher_name_by_id = {
        int(row.id): row.name
        for row in session.exec(select(CatalogPublisher)).all()
        if row.id is not None
    }

    volumes: dict[int, CatalogUniverseVolumeNode] = {}

    universe_stmt = select(ComicVineVolumeUniverse)
    if search and search.strip():
        universe_stmt = universe_stmt.where(ComicVineVolumeUniverse.name.ilike(f"%{search.strip()}%"))
    for row in session.exec(universe_stmt).all():
        if _publisher_key(row.publisher) != publisher_match_key:
            continue
        volume_id = int(row.volume_id)
        series_ids = volume_to_series.get(volume_id, [])
        catalog_count = sum(issue_counts.get(sid, 0) for sid in series_ids)
        expected = int(row.count_of_issues or 0)
        missing = max(expected - catalog_count, 0) if expected > 0 else None
        min_num, max_num = _issue_bounds_for_series_ids(session, series_ids)
        volumes[volume_id] = CatalogUniverseVolumeNode(
            volume_id=volume_id,
            title=row.name,
            volume_name=row.name,
            start_year=row.start_year,
            comicvine_volume_id=volume_id,
            issue_count=expected if expected > 0 else catalog_count,
            catalog_issue_count=catalog_count,
            min_issue_number=min_num,
            max_issue_number=max_num,
            missing_issue_count=missing,
            source="universe",
        )

    for series in session.exec(select(CatalogSeries)).all():
        if series.id is None:
            continue
        pub_name = publisher_name_by_id.get(int(series.publisher_id or 0), "Unknown")
        if _publisher_key(pub_name) != publisher_match_key:
            continue
        cv_volume = comicvine_volume_id_for_series(series)
        if cv_volume:
            try:
                if int(cv_volume) in volumes:
                    continue
            except ValueError:
                pass
        if search and search.strip() and search.strip().lower() not in series.name.lower():
            continue
        sid = int(series.id)
        catalog_count = issue_counts.get(sid, 0)
        min_num, max_num = _issue_bounds_for_series_ids(session, [sid])
        synthetic_id = -sid
        volumes[synthetic_id] = CatalogUniverseVolumeNode(
            volume_id=synthetic_id,
            title=series.name,
            volume_name=series.name if series.volume_number is None else f"{series.name} Vol. {series.volume_number}",
            start_year=series.start_year,
            comicvine_volume_id=int(cv_volume) if cv_volume and str(cv_volume).isdigit() else None,
            issue_count=catalog_count,
            catalog_issue_count=catalog_count,
            min_issue_number=min_num,
            max_issue_number=max_num,
            missing_issue_count=None,
            source="catalog",
        )

    items = sorted(volumes.values(), key=lambda row: row.title.lower())
    total_count = len(items)
    page = items[offset : offset + limit]
    return CatalogUniverseVolumeListResponse(
        publisher=publisher_label,
        items=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def _resolve_series_ids_for_volume(session: Session, volume_id: int) -> tuple[list[int], str | None]:
    if volume_id < 0:
        sid = -volume_id
        series = session.get(CatalogSeries, sid)
        if series is None:
            return [], None
        return [sid], series.name
    volume_to_series = build_volume_to_series_ids(session)
    series_ids = volume_to_series.get(volume_id, [])
    universe = session.exec(
        select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == volume_id)
    ).first()
    title = universe.name if universe else None
    return series_ids, title


def list_issues_for_volume(
    session: Session,
    *,
    volume_id: int,
    issue_number: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> CatalogUniverseIssueListResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    series_ids, volume_title = _resolve_series_ids_for_volume(session, volume_id)

    stmt = select(CatalogIssue).where(CatalogIssue.series_id.in_(series_ids) if series_ids else CatalogIssue.id == -1)
    if issue_number and issue_number.strip():
        stmt = stmt.where(
            or_(
                CatalogIssue.issue_number.ilike(f"%{issue_number.strip()}%"),
                CatalogIssue.normalized_issue_number.ilike(f"%{issue_number.strip()}%"),
            )
        )
    stmt = stmt.order_by(CatalogIssue.normalized_issue_number.asc(), CatalogIssue.id.asc())

    all_rows = list(session.exec(stmt).all()) if series_ids else []
    total_count = len(all_rows)
    page_rows = all_rows[offset : offset + limit]

    items: list[CatalogUniverseIssueNode] = []
    for issue in page_rows:
        items.append(
            CatalogUniverseIssueNode(
                issue_number=issue.issue_number,
                issue_title=issue.title,
                release_date=issue.release_date or issue.store_date or issue.cover_date,
                comicvine_issue_id=_comicvine_id_from_external(issue.external_source_ids),
                catalog_issue_id=int(issue.id) if issue.id is not None else None,
                catalog_status=CATALOG_STATUS_CATALOGED,
            )
        )

    expected = 0
    if volume_id > 0:
        universe = session.exec(
            select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == volume_id)
        ).first()
        if universe is not None:
            expected = int(universe.count_of_issues or 0)
    catalog_count = total_count
    discovered_count = max(expected - catalog_count, 0) if expected > 0 else 0

    return CatalogUniverseIssueListResponse(
        volume_id=volume_id,
        volume_title=volume_title,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
        catalog_issue_count=catalog_count,
        discovered_issue_count=discovered_count,
    )


def search_universe(
    session: Session,
    *,
    query: str,
    limit: int | None = None,
    offset: int | None = None,
) -> CatalogUniverseSearchResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    q = query.strip()
    if not q:
        return CatalogUniverseSearchResponse(query=q, hits=[], total_count=0, limit=limit, offset=offset)

    hits: list[CatalogUniverseSearchHit] = []
    needle = q.lower()

    for publisher in session.exec(
        select(ComicVineVolumeUniverse.publisher).distinct().limit(500)
    ).all():
        label = _publisher_label(publisher)
        if needle in label.lower():
            hits.append(CatalogUniverseSearchHit(hit_type="publisher", publisher=label))

    for row in session.exec(
        select(ComicVineVolumeUniverse)
        .where(ComicVineVolumeUniverse.name.ilike(f"%{q}%"))
        .order_by(ComicVineVolumeUniverse.name.asc())
        .limit(100)
    ).all():
        hits.append(
            CatalogUniverseSearchHit(
                hit_type="volume",
                publisher=_publisher_label(row.publisher),
                volume_id=int(row.volume_id),
                volume_title=row.name,
            )
        )

    for issue in session.exec(
        select(CatalogIssue)
        .where(or_(CatalogIssue.title.ilike(f"%{q}%"), CatalogIssue.issue_number.ilike(f"%{q}%")))
        .order_by(CatalogIssue.id.asc())
        .limit(100)
    ).all():
        series = session.get(CatalogSeries, issue.series_id) if issue.series_id else None
        publisher_name = None
        if series and series.publisher_id:
            pub = session.get(CatalogPublisher, series.publisher_id)
            publisher_name = pub.name if pub else None
        hits.append(
            CatalogUniverseSearchHit(
                hit_type="issue",
                publisher=publisher_name,
                volume_title=series.name if series else None,
                catalog_issue_id=int(issue.id) if issue.id is not None else None,
                issue_number=issue.issue_number,
                issue_title=issue.title,
            )
        )

    total_count = len(hits)
    page = hits[offset : offset + limit]
    return CatalogUniverseSearchResponse(
        query=q,
        hits=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
