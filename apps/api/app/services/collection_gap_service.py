"""Collection gap builder from local universe + inventory (no ComicVine API)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from app.models.acquisition import AcquisitionPlaceholderIssue
from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.collection_gap_target import (
    DEFAULT_GAP_TARGET_PRIORITY,
    DEFAULT_GAP_TARGET_SOURCE,
    DEFAULT_GAP_TARGET_STATUS,
    CollectionGapTarget,
)
from app.models.want_list import DEFAULT_PRIORITY, DEFAULT_STATUS, WantListItem
from app.schemas.collection_gap_builder import (
    CollectionGapIssueRow,
    CollectionGapIssuesResponse,
    CollectionGapPublisherRow,
    CollectionGapPublishersResponse,
    CollectionGapVolumeRow,
    CollectionGapVolumesResponse,
    CollectionGapYearRow,
    CollectionGapYearsResponse,
    WantListTargetCreatePayload,
    WantListTargetCreateResponse,
)
from app.services.catalog_universe.catalog_universe_service import (
    _decode_publisher_path,
    _publisher_key,
    _publisher_label,
    _resolve_series_ids_for_volume,
    build_volume_to_series_ids,
)
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.want_lists import ensure_default_want_list

DEFAULT_START_YEAR = 2025
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

SOLD_HOLD_STATUSES = frozenset({"sold", "sold_internal"})

PUBLISHER_PRIORITY_ORDER = [
    "Marvel",
    "DC Comics",
    "Image",
    "Dark Horse Comics",
    "Boom",
    "BOOM! Studios",
    "IDW",
    "Dynamite",
    "Valiant",
    "Archie Comics",
]


def _clamp_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return DEFAULT_LIMIT
    return min(int(limit), MAX_LIMIT)


def _clamp_offset(offset: int | None) -> int:
    if offset is None or offset < 0:
        return 0
    return int(offset)


def _issue_year(issue: CatalogIssue) -> int | None:
    d: date | None = issue.release_date or issue.store_date or issue.cover_date
    return int(d.year) if d else None


def _completion_percent(owned: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(min(100.0, (owned / total) * 100.0), 2)


def _priority_rank(publisher: str) -> int | None:
    label = _publisher_label(publisher)
    for index, name in enumerate(PUBLISHER_PRIORITY_ORDER):
        if _publisher_key(name) == _publisher_key(label):
            return index
    return None


def _sort_publishers(rows: list[CollectionGapPublisherRow]) -> list[CollectionGapPublisherRow]:
    def sort_key(row: CollectionGapPublisherRow) -> tuple:
        rank = row.priority_rank if row.priority_rank is not None else 999
        return (rank, -row.total_issues, row.publisher.lower())

    return sorted(rows, key=sort_key)


@dataclass
class _OwnershipIndex:
    catalog_active: set[int]
    catalog_sold: set[int]
    placeholder_active: dict[tuple[int, str], int]
    placeholder_ids: dict[tuple[int, str], int]


def _build_ownership_index(session: Session, *, owner_user_id: int) -> _OwnershipIndex:
    catalog_active: set[int] = set()
    catalog_sold: set[int] = set()
    placeholder_active: dict[tuple[int, str], int] = {}
    placeholder_ids: dict[tuple[int, str], int] = {}

    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    for copy in copies:
        sold = (copy.hold_status or "") in SOLD_HOLD_STATUSES
        if copy.catalog_issue_id is not None:
            cid = int(copy.catalog_issue_id)
            if sold:
                catalog_sold.add(cid)
            else:
                catalog_active.add(cid)
        if copy.placeholder_issue_id is not None and not sold:
            ph = session.get(AcquisitionPlaceholderIssue, int(copy.placeholder_issue_id))
            if ph is None or int(ph.user_id) != owner_user_id:
                continue
            if not ph.tree_linked or ph.source_volume_id is None or not ph.issue_number:
                continue
            key = (int(ph.source_volume_id), normalize_issue_number(ph.issue_number))
            placeholder_active[key] = int(ph.id or 0)
            placeholder_ids[key] = int(ph.id or 0)

    return _OwnershipIndex(
        catalog_active=catalog_active,
        catalog_sold=catalog_sold,
        placeholder_active=placeholder_active,
        placeholder_ids=placeholder_ids,
    )


def _catalog_issues_by_year(session: Session) -> dict[int, list[CatalogIssue]]:
    by_year: dict[int, list[CatalogIssue]] = defaultdict(list)
    for issue in session.exec(select(CatalogIssue)).all():
        year = _issue_year(issue)
        if year is None:
            continue
        by_year[year].append(issue)
    return by_year


def _owned_for_issue(
    *,
    ownership: _OwnershipIndex,
    volume_id: int,
    issue: CatalogIssue,
) -> tuple[bool, bool, str]:
    cid = int(issue.id or 0)
    norm = normalize_issue_number(issue.issue_number)
    key = (volume_id, norm)
    if cid in ownership.catalog_active:
        return True, False, "OWNED"
    if key in ownership.placeholder_active:
        return False, True, "PLACEHOLDER_OWNED"
    if cid in ownership.catalog_sold:
        return False, False, "SOLD_HISTORY"
    return False, False, "MISSING"


def _count_owned_in_issues(
    ownership: _OwnershipIndex,
    *,
    volume_id: int,
    issues: list[CatalogIssue],
) -> int:
    owned = 0
    seen: set[tuple[int, str]] = set()
    for issue in issues:
        cid = int(issue.id or 0)
        norm = normalize_issue_number(issue.issue_number)
        token = (volume_id, norm)
        if token in seen:
            continue
        seen.add(token)
        if cid in ownership.catalog_active:
            owned += 1
            continue
        if token in ownership.placeholder_active:
            owned += 1
    return owned


def list_gap_years(session: Session, *, owner_user_id: int) -> CollectionGapYearsResponse:
    ownership = _build_ownership_index(session, owner_user_id=owner_user_id)
    by_year = _catalog_issues_by_year(session)

    catalog_id_to_year = {
        int(issue.id or 0): year for year, issues in by_year.items() for issue in issues if issue.id is not None
    }

    owned_by_year: dict[int, int] = defaultdict(int)
    for cid in ownership.catalog_active:
        year = catalog_id_to_year.get(cid)
        if year is not None:
            owned_by_year[year] += 1

    volume_to_series = build_volume_to_series_ids(session)
    for (vol_id, norm), _ph_id in ownership.placeholder_active.items():
        for year, issues in by_year.items():
            for issue in issues:
                if normalize_issue_number(issue.issue_number) != norm:
                    continue
                if vol_id > 0 and int(issue.series_id) not in volume_to_series.get(vol_id, []):
                    continue
                if int(issue.id or 0) in ownership.catalog_active:
                    continue
                owned_by_year[year] += 1
                break

    rows: list[CollectionGapYearRow] = []
    for year in sorted(by_year.keys(), reverse=True):
        if year > DEFAULT_START_YEAR:
            continue
        total = len(by_year[year])
        owned = min(owned_by_year.get(year, 0), total)
        missing = max(total - owned, 0)
        rows.append(
            CollectionGapYearRow(
                year=year,
                total_issues=total,
                owned_issues=owned,
                missing_issues=missing,
                completion_percent=_completion_percent(owned, total),
            )
        )

    if not any(r.year == DEFAULT_START_YEAR for r in rows):
        rows.insert(
            0,
            CollectionGapYearRow(
                year=DEFAULT_START_YEAR,
                total_issues=len(by_year.get(DEFAULT_START_YEAR, [])),
                owned_issues=min(owned_by_year.get(DEFAULT_START_YEAR, 0), len(by_year.get(DEFAULT_START_YEAR, []))),
                missing_issues=max(
                    len(by_year.get(DEFAULT_START_YEAR, [])) - owned_by_year.get(DEFAULT_START_YEAR, 0),
                    0,
                ),
                completion_percent=_completion_percent(
                    owned_by_year.get(DEFAULT_START_YEAR, 0),
                    len(by_year.get(DEFAULT_START_YEAR, [])),
                ),
            ),
        )
    rows.sort(key=lambda r: -r.year)

    return CollectionGapYearsResponse(default_year=DEFAULT_START_YEAR, items=rows)


def list_gap_publishers_for_year(
    session: Session,
    *,
    owner_user_id: int,
    year: int,
    limit: int | None = None,
    offset: int | None = None,
    priority_only: bool = False,
) -> CollectionGapPublishersResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    ownership = _build_ownership_index(session, owner_user_id=owner_user_id)
    by_year = _catalog_issues_by_year(session)
    issues = by_year.get(year, [])

    publisher_name_by_id = {
        int(row.id): row.name for row in session.exec(select(CatalogPublisher)).all() if row.id is not None
    }
    volume_to_series = build_volume_to_series_ids(session)
    series_to_volume: dict[int, int] = {}
    for vol_id, sids in volume_to_series.items():
        for sid in sids:
            series_to_volume[sid] = vol_id

    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "owned": 0})
    for issue in issues:
        pub = publisher_name_by_id.get(int(issue.publisher_id or 0), "Unknown")
        label = _publisher_label(pub)
        stats[label]["total"] += 1
        vol_id = series_to_volume.get(int(issue.series_id), -int(issue.series_id))
        owned_flag = _owned_for_issue(ownership=ownership, volume_id=vol_id, issue=issue)
        if owned_flag[0] or owned_flag[1]:
            stats[label]["owned"] += 1

    rows: list[CollectionGapPublisherRow] = []
    for publisher, counts in stats.items():
        rank = _priority_rank(publisher)
        if priority_only and rank is None:
            continue
        total = counts["total"]
        owned = counts["owned"]
        rows.append(
            CollectionGapPublisherRow(
                publisher=publisher,
                total_issues=total,
                owned_issues=owned,
                missing_issues=max(total - owned, 0),
                completion_percent=_completion_percent(owned, total),
                priority_rank=rank,
            )
        )

    rows = _sort_publishers(rows)
    total_count = len(rows)
    page = rows[offset : offset + limit]
    return CollectionGapPublishersResponse(
        year=year,
        items=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def list_gap_volumes_for_publisher_year(
    session: Session,
    *,
    owner_user_id: int,
    publisher_path: str,
    year: int,
    limit: int | None = None,
    offset: int | None = None,
    incomplete_only: bool = False,
) -> CollectionGapVolumesResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    publisher_label = _decode_publisher_path(publisher_path)
    publisher_match = _publisher_key(publisher_label)
    ownership = _build_ownership_index(session, owner_user_id=owner_user_id)
    by_year = _catalog_issues_by_year(session)
    year_issues = by_year.get(year, [])

    volume_to_series = build_volume_to_series_ids(session)
    series_to_volume: dict[int, int] = {}
    for vol_id, sids in volume_to_series.items():
        for sid in sids:
            series_to_volume[sid] = vol_id

    publisher_name_by_id = {
        int(row.id): row.name for row in session.exec(select(CatalogPublisher)).all() if row.id is not None
    }

    issues_by_volume: dict[int, list[CatalogIssue]] = defaultdict(list)
    for issue in year_issues:
        pub = publisher_name_by_id.get(int(issue.publisher_id or 0), "Unknown")
        if _publisher_key(pub) != publisher_match:
            continue
        vol_id = series_to_volume.get(int(issue.series_id))
        if vol_id is None:
            vol_id = -int(issue.series_id)
        issues_by_volume[vol_id].append(issue)

    volume_meta: dict[int, tuple[str, int | None]] = {}
    for row in session.exec(select(ComicVineVolumeUniverse)).all():
        if _publisher_key(row.publisher) == publisher_match:
            volume_meta[int(row.volume_id)] = (row.name, row.start_year)
    for series in session.exec(select(CatalogSeries)).all():
        if series.id is None:
            continue
        pub = publisher_name_by_id.get(int(series.publisher_id or 0), "Unknown")
        if _publisher_key(pub) != publisher_match:
            continue
        synthetic = -int(series.id)
        if synthetic not in volume_meta:
            volume_meta[synthetic] = (series.name, series.start_year)

    rows: list[CollectionGapVolumeRow] = []
    for volume_id, vol_issues in issues_by_volume.items():
        title, start_year = volume_meta.get(volume_id, (f"Volume {volume_id}", None))
        total = len(vol_issues)
        owned = _count_owned_in_issues(ownership, volume_id=volume_id, issues=vol_issues)
        completion = _completion_percent(owned, total)
        if incomplete_only and completion >= 100.0:
            continue
        rows.append(
            CollectionGapVolumeRow(
                volume_id=volume_id,
                title=title,
                start_year=start_year,
                issue_count_in_year=total,
                owned_count=owned,
                missing_count=max(total - owned, 0),
                completion_percent=completion,
            )
        )

    rows.sort(key=lambda r: r.title.lower())
    total_count = len(rows)
    page = rows[offset : offset + limit]
    return CollectionGapVolumesResponse(
        publisher=publisher_label,
        year=year,
        items=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def list_gap_issues_for_volume_year(
    session: Session,
    *,
    owner_user_id: int,
    volume_id: int,
    year: int,
    limit: int | None = None,
    offset: int | None = None,
    gap_status_filter: str | None = None,
) -> CollectionGapIssuesResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)
    ownership = _build_ownership_index(session, owner_user_id=owner_user_id)
    series_ids, volume_title = _resolve_series_ids_for_volume(session, volume_id)
    by_year = _catalog_issues_by_year(session)
    year_issues = [issue for issue in by_year.get(year, []) if int(issue.series_id) in series_ids]
    year_issues.sort(key=lambda i: (i.normalized_issue_number, i.id or 0))

    rows: list[CollectionGapIssueRow] = []
    for issue in year_issues:
        owned, ph_owned, status = _owned_for_issue(
            ownership=ownership,
            volume_id=volume_id,
            issue=issue,
        )
        norm = normalize_issue_number(issue.issue_number)
        ph_id = ownership.placeholder_ids.get((volume_id, norm))
        if gap_status_filter:
            want = gap_status_filter.strip().upper()
            if want == "MISSING" and status != "MISSING":
                continue
            if want == "OWNED" and not owned:
                continue
            if want == "PLACEHOLDER_OWNED" and not ph_owned:
                continue
        rows.append(
            CollectionGapIssueRow(
                issue_number=issue.issue_number,
                issue_title=issue.title,
                release_date=issue.release_date or issue.store_date or issue.cover_date,
                owned=owned,
                placeholder_owned=ph_owned,
                catalog_issue_id=int(issue.id) if issue.id is not None else None,
                placeholder_issue_id=ph_id,
                gap_status=status,  # type: ignore[arg-type]
            )
        )

    total_count = len(rows)
    page = rows[offset : offset + limit]
    return CollectionGapIssuesResponse(
        volume_id=volume_id,
        year=year,
        volume_title=volume_title,
        items=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def create_wantlist_targets(
    session: Session,
    *,
    owner_user_id: int,
    payload: WantListTargetCreatePayload,
) -> WantListTargetCreateResponse:
    created_ids: list[int] = []
    skipped = 0
    default_list = ensure_default_want_list(session, owner_user_id=owner_user_id)
    want_list_id = int(default_list.id or 0)

    for item in payload.targets:
        norm = normalize_issue_number(item.issue_number)
        existing = session.exec(
            select(CollectionGapTarget).where(
                CollectionGapTarget.user_id == owner_user_id,
                CollectionGapTarget.volume_id == item.volume_id,
                CollectionGapTarget.normalized_issue_number == norm,
                CollectionGapTarget.catalog_issue_id == item.catalog_issue_id,
                CollectionGapTarget.target_status == DEFAULT_GAP_TARGET_STATUS,
            )
        ).first()
        if existing is not None:
            skipped += 1
            continue

        row = CollectionGapTarget(
            user_id=owner_user_id,
            publisher=item.publisher.strip(),
            series_title=item.series_title.strip(),
            volume_id=item.volume_id,
            issue_number=item.issue_number.strip(),
            normalized_issue_number=norm,
            catalog_issue_id=item.catalog_issue_id,
            placeholder_issue_id=item.placeholder_issue_id,
            target_status=DEFAULT_GAP_TARGET_STATUS,
            source=DEFAULT_GAP_TARGET_SOURCE,
            priority=payload.priority or DEFAULT_GAP_TARGET_PRIORITY,
        )
        session.add(row)
        session.flush()
        created_ids.append(int(row.id or 0))

        session.add(
            WantListItem(
                want_list_id=want_list_id,
                owner_user_id=owner_user_id,
                publisher=item.publisher.strip(),
                series_name=item.series_title.strip(),
                issue_number=item.issue_number.strip(),
                priority=payload.priority or DEFAULT_GAP_TARGET_PRIORITY or DEFAULT_PRIORITY,
                status=DEFAULT_STATUS,
                notes="Added from Collection Gap Builder",
            )
        )

    session.commit()
    return WantListTargetCreateResponse(
        created_count=len(created_ids),
        skipped_duplicates=skipped,
        target_ids=created_ids,
    )
