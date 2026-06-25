"""Aggregate catalog coverage, ComicVine universe discovery, and collector inventory for Master Universe."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVariant
from app.schemas.master_universe_catalog_dashboard import (
    MasterUniverseCatalogDashboardResponse,
    MasterUniverseCatalogDashboardSummary,
    MasterUniverseCatalogPublisherRow,
    MasterUniverseCatalogSourceCounts,
)
from app.services.catalog_universe.catalog_universe_service import (
    _catalog_issue_counts_by_series,
    _publisher_key,
    _publisher_label,
    get_universe_summary,
)


def _clamp_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return 50
    return min(int(limit), 200)


def _clamp_offset(offset: int | None) -> int:
    if offset is None or offset < 0:
        return 0
    return int(offset)


def _issue_source_key(external_source_ids: dict | None) -> str:
    if not external_source_ids:
        return "unknown"
    primary = external_source_ids.get("_primary_source")
    if primary:
        label = str(primary).strip().upper()
        if label in {"COMICVINE", "GCD"}:
            return label.lower()
        return "other"
    if external_source_ids.get("COMICVINE"):
        return "comicvine"
    if external_source_ids.get("GCD"):
        return "gcd"
    return "other"


def get_master_universe_catalog_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    search: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseCatalogDashboardResponse:
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)

    universe_summary = get_universe_summary(session)

    catalog_series_count = int(session.exec(select(func.count()).select_from(CatalogSeries)).one())
    catalog_issue_count = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())

    ref_publishers = int(session.exec(select(func.count()).select_from(UniversePublisher)).one())
    ref_issues = int(session.exec(select(func.count()).select_from(UniverseIssue)).one())
    ref_variants = int(session.exec(select(func.count()).select_from(UniverseVariant)).one())

    inv_total = int(
        session.exec(
            select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)
        ).one()
    )
    inv_linked = int(
        session.exec(
            select(func.count())
            .select_from(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id, InventoryCopy.catalog_issue_id.isnot(None))
        ).one()
    )

    source_tally_by_pub: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    universe_by_key: dict[str, tuple[str, int, int]] = {}
    for publisher, volume_count, issue_sum in session.exec(
        select(
            ComicVineVolumeUniverse.publisher,
            func.count(),
            func.coalesce(func.sum(ComicVineVolumeUniverse.count_of_issues), 0),
        ).group_by(ComicVineVolumeUniverse.publisher)
    ).all():
        label = _publisher_label(publisher)
        key = _publisher_key(publisher)
        universe_by_key[key] = (label, int(volume_count), int(issue_sum or 0))

    publisher_name_by_id = {
        int(row.id): row.name
        for row in session.exec(select(CatalogPublisher)).all()
        if row.id is not None
    }

    issue_counts_by_series = _catalog_issue_counts_by_series(session)
    series_by_pub_key: dict[str, tuple[str, int, int]] = {}
    for series in session.exec(select(CatalogSeries)).all():
        if series.id is None:
            continue
        pub_name = publisher_name_by_id.get(int(series.publisher_id or 0), "Unknown")
        key = _publisher_key(pub_name)
        label = _publisher_label(pub_name)
        vol_inc, iss_inc = series_by_pub_key.get(key, (label, 0, 0))
        series_by_pub_key[key] = (
            label,
            vol_inc + 1,
            iss_inc + issue_counts_by_series.get(int(series.id), 0),
        )

    source_tally_by_pub: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for pub_id, ext in session.exec(select(CatalogIssue.publisher_id, CatalogIssue.external_source_ids)).all():
        if pub_id is None:
            continue
        pub_name = publisher_name_by_id.get(int(pub_id), "Unknown")
        key = _publisher_key(pub_name)
        source_tally_by_pub[key][_issue_source_key(ext if isinstance(ext, dict) else None)] += 1

    inventory_by_pub_key: dict[str, int] = defaultdict(int)
    for pub_name, cnt in session.exec(
        select(CatalogPublisher.name, func.count(InventoryCopy.id))
        .join(CatalogIssue, CatalogIssue.publisher_id == CatalogPublisher.id)
        .join(InventoryCopy, InventoryCopy.catalog_issue_id == CatalogIssue.id)
        .where(InventoryCopy.user_id == owner_user_id)
        .group_by(CatalogPublisher.name)
    ).all():
        inventory_by_pub_key[_publisher_key(pub_name)] = int(cnt)

    all_keys = set(universe_by_key) | set(series_by_pub_key) | set(inventory_by_pub_key)
    rows: list[MasterUniverseCatalogPublisherRow] = []
    for key in all_keys:
        u_label, u_vol, u_iss = universe_by_key.get(key, (_publisher_label(key), 0, 0))
        c_label, c_series, c_issues = series_by_pub_key.get(key, (u_label, 0, 0))
        label = c_label if c_series or c_issues else u_label
        missing = max(u_iss - c_issues, 0) if u_iss > 0 else 0
        tallies = source_tally_by_pub.get(key, {})
        primary_source = None
        if tallies:
            best = max(tallies.items(), key=lambda item: item[1])
            primary_source = best[0].upper() if best[0] != "unknown" else None
        rows.append(
            MasterUniverseCatalogPublisherRow(
                publisher=label,
                universe_volume_count=u_vol,
                universe_issue_ceiling=u_iss,
                catalog_series_count=c_series,
                catalog_issue_count=c_issues,
                missing_catalog_issues=missing,
                inventory_copy_count=inventory_by_pub_key.get(key, 0),
                primary_catalog_source=primary_source,
            )
        )

    if search and search.strip():
        needle = search.strip().lower()
        rows = [row for row in rows if needle in row.publisher.lower()]

    rows.sort(key=lambda row: (-row.inventory_copy_count, -row.catalog_issue_count, row.publisher.lower()))
    total_count = len(rows)
    page = rows[offset : offset + limit]

    source_counts = MasterUniverseCatalogSourceCounts()
    for tallies in source_tally_by_pub.values():
        for bucket, count in tallies.items():
            if bucket == "comicvine":
                source_counts.comicvine += count
            elif bucket == "gcd":
                source_counts.gcd += count
            elif bucket == "other":
                source_counts.other += count
            else:
                source_counts.unknown += count

    summary = MasterUniverseCatalogDashboardSummary(
        total_publishers=universe_summary.total_publishers,
        universe_volume_count=universe_summary.total_volumes,
        universe_issue_ceiling=universe_summary.total_issues,
        catalog_series_count=catalog_series_count,
        catalog_issue_count=catalog_issue_count,
        missing_catalog_issues=max(universe_summary.total_issues - catalog_issue_count, 0),
        reference_tree_publishers=ref_publishers,
        reference_tree_issues=ref_issues,
        reference_tree_variants=ref_variants,
        inventory_copy_count=inv_total,
        inventory_linked_to_catalog=inv_linked,
        inventory_unlinked=max(inv_total - inv_linked, 0),
        catalog_source_counts=source_counts,
    )

    return MasterUniverseCatalogDashboardResponse(
        summary=summary,
        rows=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
