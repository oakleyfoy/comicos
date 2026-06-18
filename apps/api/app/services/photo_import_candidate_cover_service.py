"""P100-14A candidate cover URLs from external catalog (no local CatalogImage required)."""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogVariant
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.services.acquisition.catalog_browse_service import _covers_for_issue_ids, _covers_for_variant_ids
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.p97_catalog_snapshot_service import primary_comicvine_id


def _external_cover_from_issue(
    issue: ExternalCatalogIssue,
    *,
    variant: ExternalCatalogVariant | None = None,
) -> tuple[str | None, str | None]:
    cover: str | None = None
    thumb: str | None = None
    if variant is not None and variant.image_url and str(variant.image_url).strip():
        cover = str(variant.image_url).strip()
    for url in (
        issue.high_resolution_image_url,
        issue.cover_image_url,
        issue.thumbnail_url,
    ):
        if url and str(url).strip():
            if cover is None:
                cover = str(url).strip()
            break
    if issue.thumbnail_url and str(issue.thumbnail_url).strip():
        thumb = str(issue.thumbnail_url).strip()
    elif cover:
        thumb = cover
    return cover, thumb


def _find_external_issue(
    session: Session,
    *,
    catalog_issue: CatalogIssue,
    series: CatalogSeries | None,
    publisher: CatalogPublisher | None,
) -> ExternalCatalogIssue | None:
    comicvine_id = primary_comicvine_id(catalog_issue.external_source_ids)
    if comicvine_id:
        rows = session.exec(
            select(ExternalCatalogIssue)
            .where(ExternalCatalogIssue.source_issue_id == comicvine_id)
            .order_by(ExternalCatalogIssue.id.desc())
            .limit(3)
        ).all()
        if rows:
            return rows[0]

    issue_num = str(catalog_issue.issue_number)
    norm = normalize_issue_number(issue_num)
    issue_filters = {issue_num, norm} if norm else {issue_num}
    stmt = select(ExternalCatalogIssue).where(
        or_(
            ExternalCatalogIssue.issue_number.in_(list(issue_filters)),  # type: ignore[attr-defined]
            ExternalCatalogIssue.issue_number.ilike(issue_num),
        )
    )
    series_name = (series.name if series else "").strip()
    if series_name:
        norm_series = normalize_series_name(series_name)
        like = f"%{series_name[:80]}%"
        stmt = stmt.where(
            or_(
                ExternalCatalogIssue.series_name.ilike(like),
                func.lower(ExternalCatalogIssue.series_name).contains(norm_series[:80]),
                ExternalCatalogIssue.normalized_title_key.ilike(f"%{norm_series[:80]}%"),
            )
        )
    pub_name = (publisher.name if publisher else "").strip()
    if pub_name:
        stmt = stmt.where(
            or_(
                ExternalCatalogIssue.publisher.ilike(f"%{pub_name[:80]}%"),
                func.lower(ExternalCatalogIssue.publisher).contains(pub_name.lower()[:40]),
            )
        )
    return session.exec(stmt.order_by(ExternalCatalogIssue.id.desc()).limit(1)).first()


def _external_variant_for_catalog_variant(
    session: Session,
    *,
    external_issue_id: int,
    catalog_variant: CatalogVariant | None,
) -> ExternalCatalogVariant | None:
    variants = session.exec(
        select(ExternalCatalogVariant)
        .where(ExternalCatalogVariant.external_issue_id == external_issue_id)
        .order_by(ExternalCatalogVariant.id.asc())
    ).all()
    if not variants:
        return None
    if catalog_variant is None:
        return variants[0]
    name = (catalog_variant.variant_name or "").strip().lower()
    if name:
        for row in variants:
            vname = (row.variant_name or row.cover_label or "").strip().lower()
            if vname and (vname in name or name in vname):
                return row
    return variants[0]


def cover_urls_for_photo_import_candidates(
    session: Session,
    *,
    issue_ids: list[int],
    variant_id_by_issue: dict[int, int | None] | None = None,
) -> dict[int, str]:
    """Resolve cover URLs for catalog issues: local CatalogImage first, then external catalog."""
    if not issue_ids:
        return {}
    out = _covers_for_issue_ids(session, issue_ids)
    missing = [iid for iid in issue_ids if iid not in out]
    if not missing:
        return out

    variant_id_by_issue = variant_id_by_issue or {}
    variant_ids = [vid for vid in variant_id_by_issue.values() if vid]
    local_variant_covers = _covers_for_variant_ids(session, variant_ids)

    rows = session.exec(
        select(CatalogIssue, CatalogSeries, CatalogPublisher)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id, isouter=True)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
        .where(CatalogIssue.id.in_(missing))  # type: ignore[attr-defined]
    ).all()

    catalog_variants: dict[int, CatalogVariant] = {}
    if variant_ids:
        for var in session.exec(select(CatalogVariant).where(CatalogVariant.id.in_(variant_ids))).all():  # type: ignore[attr-defined]
            if var.id is not None:
                catalog_variants[int(var.id)] = var

    for issue, series, publisher in rows:
        iid = int(issue.id or 0)
        if iid in out:
            continue
        vid = variant_id_by_issue.get(iid)
        if vid and vid in local_variant_covers:
            out[iid] = local_variant_covers[vid]
            continue

        external = _find_external_issue(session, catalog_issue=issue, series=series, publisher=publisher)
        if external is None or external.id is None:
            continue
        cat_var = catalog_variants.get(int(vid)) if vid else None
        ext_var = _external_variant_for_catalog_variant(
            session,
            external_issue_id=int(external.id),
            catalog_variant=cat_var,
        )
        url = _external_cover_from_issue(external, variant=ext_var)
        if url[0]:
            out[iid] = url[0]

    return out


def cover_and_thumbnail_urls_for_photo_import_candidates(
    session: Session,
    *,
    issue_ids: list[int],
    variant_id_by_issue: dict[int, int | None] | None = None,
) -> dict[int, tuple[str | None, str | None]]:
    """Resolve (cover_image_url, thumbnail_url) for catalog issues."""
    covers = cover_urls_for_photo_import_candidates(
        session,
        issue_ids=issue_ids,
        variant_id_by_issue=variant_id_by_issue,
    )
    result: dict[int, tuple[str | None, str | None]] = {}
    for iid in issue_ids:
        cover = covers.get(iid)
        result[iid] = (cover, cover)
    if not issue_ids:
        return result

    variant_id_by_issue = variant_id_by_issue or {}
    missing = [iid for iid in issue_ids if iid not in covers]
    if not missing:
        return result

    rows = session.exec(
        select(CatalogIssue, CatalogSeries, CatalogPublisher)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id, isouter=True)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
        .where(CatalogIssue.id.in_(missing))  # type: ignore[attr-defined]
    ).all()
    catalog_variants: dict[int, CatalogVariant] = {}
    variant_ids = [vid for vid in variant_id_by_issue.values() if vid]
    if variant_ids:
        for var in session.exec(select(CatalogVariant).where(CatalogVariant.id.in_(variant_ids))).all():  # type: ignore[attr-defined]
            if var.id is not None:
                catalog_variants[int(var.id)] = var

    for issue, series, publisher in rows:
        iid = int(issue.id or 0)
        external = _find_external_issue(session, catalog_issue=issue, series=series, publisher=publisher)
        if external is None:
            continue
        vid = variant_id_by_issue.get(iid)
        cat_var = catalog_variants.get(int(vid)) if vid else None
        ext_var = _external_variant_for_catalog_variant(
            session,
            external_issue_id=int(external.id or 0),
            catalog_variant=cat_var,
        )
        cover, thumb = _external_cover_from_issue(external, variant=ext_var)
        if cover or thumb:
            result[iid] = (cover or thumb, thumb or cover)

    return result
