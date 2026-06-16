"""P98-03/04 universe issue + variant shells."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogSeries
from app.models.universe import (
    DEFAULT_VARIANT_TYPE,
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UNIVERSE_VARIANT_STATUS_CATALOGED,
    UNIVERSE_VARIANT_STATUS_DISCOVERED,
    UniverseIssue,
    UniverseVariant,
    UniverseVolume,
)
from app.schemas.master_universe import (
    MasterUniverseIssueListResponse,
    MasterUniverseIssueNode,
    MasterUniverseVariantListResponse,
    MasterUniverseVariantNode,
)
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series
from app.services.universe.universe_common import clamp_limit, clamp_offset


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_default_variant(session: Session, issue: UniverseIssue) -> UniverseVariant:
    row = session.exec(
        select(UniverseVariant).where(
            UniverseVariant.issue_id == int(issue.id or 0),
            UniverseVariant.variant_type == DEFAULT_VARIANT_TYPE,
            UniverseVariant.variant_name == "",
        )
    ).first()
    if row is not None:
        return row
    row = UniverseVariant(
        issue_id=int(issue.id or 0),
        variant_type=DEFAULT_VARIANT_TYPE,
        variant_name="",
        status=UNIVERSE_VARIANT_STATUS_DISCOVERED,
    )
    session.add(row)
    session.flush()
    return row


def upsert_issue_shell(
    session: Session,
    *,
    volume: UniverseVolume,
    issue_number: str,
    issue_title: str | None = None,
    cover_date=None,
    comicvine_issue_id: int | None = None,
    catalog_issue_id: int | None = None,
) -> UniverseIssue:
    norm = normalize_issue_number(issue_number)
    if not norm:
        raise ValueError("issue_number required")
    row = session.exec(
        select(UniverseIssue).where(
            UniverseIssue.volume_id == int(volume.id or 0),
            UniverseIssue.normalized_issue_number == norm,
        )
    ).first()
    status = UNIVERSE_ISSUE_STATUS_CATALOGED if catalog_issue_id else UNIVERSE_ISSUE_STATUS_DISCOVERED
    if row is None:
        row = UniverseIssue(
            volume_id=int(volume.id or 0),
            issue_number=issue_number.strip(),
            normalized_issue_number=norm,
            issue_title=issue_title,
            cover_date=cover_date,
            comicvine_issue_id=comicvine_issue_id,
            status=status,
        )
        session.add(row)
        session.flush()
    else:
        if issue_title:
            row.issue_title = issue_title
        if cover_date:
            row.cover_date = cover_date
        if comicvine_issue_id:
            row.comicvine_issue_id = comicvine_issue_id
        if catalog_issue_id:
            row.status = UNIVERSE_ISSUE_STATUS_CATALOGED
        row.updated_at = _utc_now()
        session.add(row)
        session.flush()

    variant = ensure_default_variant(session, row)
    if catalog_issue_id:
        variant.catalog_issue_id = catalog_issue_id
        variant.status = UNIVERSE_VARIANT_STATUS_CATALOGED
        variant.updated_at = _utc_now()
        session.add(variant)
    return row


def build_issue_shells_from_catalog(session: Session) -> dict[str, int]:
    """Create issue shells for catalog issues mapped to universe volumes."""
    stats = {"issues_created": 0, "issues_updated": 0, "variants_linked": 0}
    volume_by_cv: dict[int, UniverseVolume] = {
        int(v.comicvine_volume_id): v
        for v in session.exec(select(UniverseVolume)).all()
    }
    for series in session.exec(select(CatalogSeries)).all():
        cv_key = comicvine_volume_id_for_series(series)
        if not cv_key or not str(cv_key).isdigit():
            continue
        volume = volume_by_cv.get(int(cv_key))
        if volume is None:
            continue
        issues = session.exec(select(CatalogIssue).where(CatalogIssue.series_id == int(series.id or 0))).all()
        for issue in issues:
            cv_issue_id = None
            bucket = (issue.external_source_ids or {}).get("COMICVINE")
            if isinstance(bucket, dict) and bucket:
                try:
                    cv_issue_id = int(next(iter(bucket.keys())))
                except (StopIteration, TypeError, ValueError):
                    cv_issue_id = None
            existing = session.exec(
                select(UniverseIssue).where(
                    UniverseIssue.volume_id == int(volume.id or 0),
                    UniverseIssue.normalized_issue_number == issue.normalized_issue_number,
                )
            ).first()
            shell = upsert_issue_shell(
                session,
                volume=volume,
                issue_number=issue.issue_number,
                issue_title=issue.title,
                cover_date=issue.cover_date or issue.store_date or issue.release_date,
                comicvine_issue_id=cv_issue_id,
                catalog_issue_id=int(issue.id or 0) if issue.id else None,
            )
            if existing is None:
                stats["issues_created"] += 1
            else:
                stats["issues_updated"] += 1
            if issue.id:
                stats["variants_linked"] += 1
            ensure_default_variant(session, shell)
    session.commit()
    return stats


def list_issues_for_volume(
    session: Session,
    *,
    volume_id: int,
    issue_number: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseIssueListResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    volume = session.get(UniverseVolume, volume_id)
    if volume is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volume not found")

    stmt = select(UniverseIssue).where(UniverseIssue.volume_id == volume_id)
    if issue_number and issue_number.strip():
        needle = issue_number.strip()
        stmt = stmt.where(
            (UniverseIssue.issue_number.ilike(f"%{needle}%"))
            | (UniverseIssue.normalized_issue_number.ilike(f"%{needle}%"))
        )
    rows = list(session.exec(stmt.order_by(UniverseIssue.normalized_issue_number.asc())).all())
    var_counts = {
        int(iid): int(cnt)
        for iid, cnt in session.exec(
            select(UniverseVariant.issue_id, func.count(UniverseVariant.id)).group_by(UniverseVariant.issue_id)
        ).all()
    }
    total_count = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MasterUniverseIssueNode(
            id=int(row.id or 0),
            issue_number=row.issue_number,
            normalized_issue_number=row.normalized_issue_number,
            issue_title=row.issue_title,
            cover_date=row.cover_date,
            comicvine_issue_id=row.comicvine_issue_id,
            status=row.status,
            variant_count=var_counts.get(int(row.id or 0), 0),
        )
        for row in page
    ]
    return MasterUniverseIssueListResponse(
        volume_id=volume_id,
        volume_name=volume.name,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def list_variants_for_issue(
    session: Session,
    *,
    issue_id: int,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseVariantListResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    issue = session.get(UniverseIssue, issue_id)
    if issue is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    ensure_default_variant(session, issue)
    session.flush()

    rows = list(
        session.exec(
            select(UniverseVariant)
            .where(UniverseVariant.issue_id == issue_id)
            .order_by(UniverseVariant.id.asc())
        ).all()
    )
    total_count = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MasterUniverseVariantNode(
            id=int(row.id or 0),
            variant_type=row.variant_type,
            variant_name=row.variant_name,
            status=row.status,
            catalog_issue_id=row.catalog_issue_id,
            comicvine_variant_id=row.comicvine_variant_id,
            is_unknown_shell=row.variant_type == DEFAULT_VARIANT_TYPE and not row.variant_name,
        )
        for row in page
    ]
    return MasterUniverseVariantListResponse(
        issue_id=issue_id,
        issue_number=issue.issue_number,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
