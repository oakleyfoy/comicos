"""P98-06/07/08/09 catalog browse services (publisher -> series -> issue grid -> variants).

Net-new browse layer against `catalog_master`. Read-only; powers the tap-first
add-books flow. Owned/added indicators are scoped to the current user and the
active acquisition.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries, CatalogVariant
from app.models import InventoryCopy
from app.schemas.acquisition import (
    IssueGridResponse,
    IssueGridTile,
    PublisherCard,
    PublisherListResponse,
    SeriesCard,
    SeriesListResponse,
    VariantOption,
    VariantPickerResult,
)

POPULAR_SERIES_LIMIT = 12
RECENT_LIMIT = 12


def _cover_url(image: CatalogImage | None) -> str | None:
    if image is None:
        return None
    if image.source_url and str(image.source_url).strip():
        return str(image.source_url).strip()
    if image.local_path and str(image.local_path).strip():
        return str(image.local_path).strip()
    return None


def _covers_for_variant_ids(session: Session, variant_ids: list[int]) -> dict[int, str]:
    if not variant_ids:
        return {}
    rows = session.exec(
        select(CatalogImage)
        .where(CatalogImage.variant_id.in_(variant_ids), CatalogImage.image_type == "cover")
        .order_by(CatalogImage.variant_id.asc(), CatalogImage.id.asc())
    ).all()
    out: dict[int, str] = {}
    for image in rows:
        if image.variant_id is None or image.variant_id in out:
            continue
        url = _cover_url(image)
        if url:
            out[int(image.variant_id)] = url
    return out


def _covers_for_issue_ids(session: Session, issue_ids: list[int]) -> dict[int, str]:
    """First cover image url per catalog_issue id (lowest image id wins)."""
    if not issue_ids:
        return {}
    rows = session.exec(
        select(CatalogImage)
        .where(CatalogImage.issue_id.in_(issue_ids), CatalogImage.image_type == "cover")
        .order_by(CatalogImage.issue_id.asc(), CatalogImage.id.asc())
    ).all()
    out: dict[int, str] = {}
    for image in rows:
        if image.issue_id is None or image.issue_id in out:
            continue
        url = _cover_url(image)
        if url:
            out[int(image.issue_id)] = url
    return out


def _owned_publisher_ids(session: Session, owner_user_id: int) -> set[int]:
    rows = session.exec(
        select(func.coalesce(CatalogIssue.publisher_id, CatalogSeries.publisher_id))
        .select_from(InventoryCopy)
        .join(CatalogIssue, InventoryCopy.catalog_issue_id == CatalogIssue.id)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id, isouter=True)
        .where(InventoryCopy.user_id == owner_user_id, InventoryCopy.catalog_issue_id.is_not(None))
        .distinct()
    ).all()
    return {int(pid) for pid in rows if pid is not None}


def _owned_series_ids(session: Session, owner_user_id: int) -> set[int]:
    rows = session.exec(
        select(CatalogIssue.series_id)
        .select_from(InventoryCopy)
        .join(CatalogIssue, InventoryCopy.catalog_issue_id == CatalogIssue.id)
        .where(InventoryCopy.user_id == owner_user_id, InventoryCopy.catalog_issue_id.is_not(None))
        .distinct()
    ).all()
    return {int(sid) for sid in rows if sid is not None}


def list_publishers(session: Session, *, owner_user_id: int, search: str | None = None) -> PublisherListResponse:
    series_count_rows = session.exec(
        select(CatalogSeries.publisher_id, func.count(CatalogSeries.id))
        .where(CatalogSeries.publisher_id.is_not(None))
        .group_by(CatalogSeries.publisher_id)
    ).all()
    series_counts = {int(pid): int(cnt) for pid, cnt in series_count_rows if pid is not None}

    owned_ids = _owned_publisher_ids(session, owner_user_id)

    stmt = select(CatalogPublisher)
    if search:
        stmt = stmt.where(CatalogPublisher.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(CatalogPublisher.name.asc())
    publishers = list(session.exec(stmt).all())

    cards = [
        PublisherCard(
            id=int(p.id or 0),
            name=p.name,
            series_count=series_counts.get(int(p.id or 0), 0),
            owned=int(p.id or 0) in owned_ids,
            recently_used=int(p.id or 0) in owned_ids,
        )
        for p in publishers
    ]
    cards.sort(key=lambda c: (not c.owned, -c.series_count, c.name.lower()))
    return PublisherListResponse(publishers=cards)


def _series_cards(
    session: Session,
    series_rows: list[CatalogSeries],
    *,
    publisher_name_map: dict[int, str],
    issue_counts: dict[int, int],
    owned_ids: set[int],
) -> list[SeriesCard]:
    if not series_rows:
        return []
    # sample cover per series: first cover of first issue
    series_ids = [int(s.id) for s in series_rows if s.id is not None]
    first_issue_rows = session.exec(
        select(CatalogIssue.series_id, func.min(CatalogIssue.id))
        .where(CatalogIssue.series_id.in_(series_ids))
        .group_by(CatalogIssue.series_id)
    ).all()
    first_issue_by_series = {int(sid): int(iid) for sid, iid in first_issue_rows if iid is not None}
    covers = _covers_for_issue_ids(session, list(first_issue_by_series.values()))

    cards: list[SeriesCard] = []
    for series in series_rows:
        sid = int(series.id or 0)
        first_issue_id = first_issue_by_series.get(sid)
        sample = covers.get(first_issue_id) if first_issue_id else None
        cards.append(
            SeriesCard(
                id=sid,
                name=series.name,
                start_year=series.start_year,
                issue_count=issue_counts.get(sid, 0),
                publisher_id=series.publisher_id,
                publisher_name=publisher_name_map.get(int(series.publisher_id)) if series.publisher_id else None,
                sample_cover_url=sample,
                owned=sid in owned_ids,
                recently_used=sid in owned_ids,
            )
        )
    return cards


def list_series_for_publisher(session: Session, *, owner_user_id: int, publisher_id: int) -> SeriesListResponse:
    publisher = session.get(CatalogPublisher, publisher_id)
    publisher_name_map = {publisher_id: publisher.name} if publisher else {}

    series_rows = list(
        session.exec(
            select(CatalogSeries)
            .where(CatalogSeries.publisher_id == publisher_id)
            .order_by(CatalogSeries.name.asc())
        ).all()
    )
    series_ids = [int(s.id) for s in series_rows if s.id is not None]

    issue_counts: dict[int, int] = {}
    if series_ids:
        count_rows = session.exec(
            select(CatalogIssue.series_id, func.count(CatalogIssue.id))
            .where(CatalogIssue.series_id.in_(series_ids))
            .group_by(CatalogIssue.series_id)
        ).all()
        issue_counts = {int(sid): int(cnt) for sid, cnt in count_rows}

    owned_ids = _owned_series_ids(session, owner_user_id) & set(series_ids)

    alphabetical = _series_cards(
        session,
        series_rows,
        publisher_name_map=publisher_name_map,
        issue_counts=issue_counts,
        owned_ids=owned_ids,
    )
    by_id = {c.id: c for c in alphabetical}
    popular = sorted(alphabetical, key=lambda c: (-c.issue_count, c.name.lower()))[:POPULAR_SERIES_LIMIT]
    user_owned = [by_id[sid] for sid in owned_ids if sid in by_id]
    user_owned.sort(key=lambda c: c.name.lower())
    return SeriesListResponse(
        popular=popular,
        recently_used=user_owned[:RECENT_LIMIT],
        user_owned=user_owned,
        alphabetical=alphabetical,
    )


def list_series_issue_grid(
    session: Session,
    *,
    owner_user_id: int,
    series_id: int,
    acquisition_id: int | None = None,
) -> IssueGridResponse:
    series = session.get(CatalogSeries, series_id)
    if series is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    publisher = session.get(CatalogPublisher, series.publisher_id) if series.publisher_id else None

    issues = list(
        session.exec(
            select(CatalogIssue)
            .where(CatalogIssue.series_id == series_id)
            .order_by(CatalogIssue.id.asc())
        ).all()
    )
    issue_ids = [int(i.id) for i in issues if i.id is not None]

    # group by normalized issue number
    groups: dict[str, list[CatalogIssue]] = {}
    for issue in issues:
        groups.setdefault(issue.normalized_issue_number, []).append(issue)

    variant_counts: dict[int, int] = {}
    if issue_ids:
        vrows = session.exec(
            select(CatalogVariant.issue_id, func.count(CatalogVariant.id))
            .where(CatalogVariant.issue_id.in_(issue_ids))
            .group_by(CatalogVariant.issue_id)
        ).all()
        variant_counts = {int(iid): int(cnt) for iid, cnt in vrows}

    owned_issue_ids: set[int] = set()
    added_issue_ids: set[int] = set()
    if issue_ids:
        owned_rows = session.exec(
            select(InventoryCopy.catalog_issue_id)
            .where(
                InventoryCopy.user_id == owner_user_id,
                InventoryCopy.catalog_issue_id.in_(issue_ids),
            )
            .distinct()
        ).all()
        owned_issue_ids = {int(x) for x in owned_rows if x is not None}
        if acquisition_id is not None:
            added_rows = session.exec(
                select(InventoryCopy.catalog_issue_id)
                .where(
                    InventoryCopy.acquisition_id == acquisition_id,
                    InventoryCopy.catalog_issue_id.in_(issue_ids),
                )
                .distinct()
            ).all()
            added_issue_ids = {int(x) for x in added_rows if x is not None}

    covers = _covers_for_issue_ids(session, issue_ids)

    tiles: list[IssueGridTile] = []
    for normalized, group in groups.items():
        group.sort(key=lambda i: int(i.id or 0))
        representative = group[0]
        rep_id = int(representative.id or 0)
        total_variants = sum(variant_counts.get(int(i.id or 0), 0) for i in group)
        cover_count = len(group) + total_variants
        has_variants = len(group) > 1 or total_variants > 0
        group_issue_ids = {int(i.id or 0) for i in group}
        tiles.append(
            IssueGridTile(
                issue_number=representative.issue_number,
                normalized_issue_number=normalized,
                catalog_issue_id=None if has_variants else rep_id,
                cover_image_url=covers.get(rep_id),
                cover_count=cover_count,
                has_variants=has_variants,
                owned=bool(group_issue_ids & owned_issue_ids),
                added=bool(group_issue_ids & added_issue_ids),
            )
        )

    tiles.sort(key=_issue_sort_key)
    return IssueGridResponse(
        series_id=series_id,
        series_name=series.name,
        publisher_name=publisher.name if publisher else None,
        tiles=tiles,
    )


def _issue_sort_key(tile: IssueGridTile):
    raw = tile.normalized_issue_number
    try:
        return (0, float(raw), raw)
    except (TypeError, ValueError):
        return (1, 0.0, raw)


def _variant_sort_rank(issue: CatalogIssue) -> int:
    """Cover A/main first, regular next, foils, ratio/incentive last (P98-09)."""
    label = " ".join(filter(None, [issue.title or "", issue.issue_number or ""])).lower()
    if any(token in label for token in ("ratio", "incentive", "1:")):
        return 3
    if any(token in label for token in ("foil", "virgin", "glow", "metal", "holo")):
        return 2
    if any(token in label for token in ("variant", "cover b", "cover c", "cvr b", "cvr c")):
        return 1
    return 0


def list_issue_variants(
    session: Session,
    *,
    owner_user_id: int,
    series_id: int,
    normalized_issue_number: str,
    acquisition_id: int | None = None,
) -> VariantPickerResult:
    series = session.get(CatalogSeries, series_id)
    publisher = session.get(CatalogPublisher, series.publisher_id) if series and series.publisher_id else None
    issues = list(
        session.exec(
            select(CatalogIssue)
            .where(
                CatalogIssue.series_id == series_id,
                CatalogIssue.normalized_issue_number == normalized_issue_number,
            )
            .order_by(CatalogIssue.id.asc())
        ).all()
    )
    issue_ids = [int(i.id) for i in issues if i.id is not None]
    covers = _covers_for_issue_ids(session, issue_ids)

    owned_issue_ids: set[int] = set()
    added_issue_ids: set[int] = set()
    if issue_ids:
        owned_rows = session.exec(
            select(InventoryCopy.catalog_issue_id)
            .where(InventoryCopy.user_id == owner_user_id, InventoryCopy.catalog_issue_id.in_(issue_ids))
            .distinct()
        ).all()
        owned_issue_ids = {int(x) for x in owned_rows if x is not None}
        if acquisition_id is not None:
            added_rows = session.exec(
                select(InventoryCopy.catalog_issue_id)
                .where(
                    InventoryCopy.acquisition_id == acquisition_id,
                    InventoryCopy.catalog_issue_id.in_(issue_ids),
                )
                .distinct()
            ).all()
            added_issue_ids = {int(x) for x in added_rows if x is not None}

    options: list[VariantOption] = []
    for issue in issues:
        iid = int(issue.id or 0)
        options.append(
            VariantOption(
                catalog_issue_id=iid,
                series=series.name if series else "Unknown",
                issue_number=issue.issue_number,
                title=issue.title,
                variant_label=issue.title,
                cover_date=issue.cover_date,
                publisher=publisher.name if publisher else None,
                cover_image_url=covers.get(iid),
                variant_type=None,
                sort_rank=_variant_sort_rank(issue),
                owned=iid in owned_issue_ids,
                added=iid in added_issue_ids,
            )
        )

    if issue_ids:
        variant_rows = list(
            session.exec(select(CatalogVariant).where(CatalogVariant.issue_id.in_(issue_ids)).order_by(CatalogVariant.id.asc())).all()
        )
        variant_ids = [int(v.id) for v in variant_rows if v.id is not None]
        variant_covers = _covers_for_variant_ids(session, variant_ids)
        issue_by_id = {int(i.id or 0): i for i in issues if i.id is not None}
        for variant in variant_rows:
            vid = int(variant.id or 0)
            iid = int(variant.issue_id)
            parent = issue_by_id.get(iid)
            if parent is None:
                continue
            label = (variant.variant_name or variant.ratio or variant.printing or "Variant").strip()
            options.append(
                VariantOption(
                    catalog_issue_id=iid,
                    series=series.name if series else "Unknown",
                    issue_number=parent.issue_number,
                    title=parent.title,
                    variant_label=label,
                    cover_date=parent.cover_date,
                    publisher=publisher.name if publisher else None,
                    cover_image_url=variant_covers.get(vid) or covers.get(iid),
                    variant_type=variant.ratio,
                    sort_rank=_variant_sort_rank(parent) + 1,
                    owned=iid in owned_issue_ids,
                    added=iid in added_issue_ids,
                )
            )

    options.sort(key=lambda o: (o.sort_rank, o.catalog_issue_id))
    return VariantPickerResult(
        series_id=series_id,
        issue_number=issues[0].issue_number if issues else normalized_issue_number,
        options=options,
    )
