"""Placeholder match queue and catalog linking (local DB only)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models.acquisition import (
    CATALOG_STATUS_LINKED,
    CATALOG_STATUS_PLACEHOLDER,
    Acquisition,
    AcquisitionPlaceholderIssue,
)
from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.schemas.catalog_universe_placeholders import (
    LinkPlaceholderResponse,
    PlaceholderMatchCandidate,
    PlaceholderMatchCandidatesResponse,
    PlaceholderQueueItem,
    PlaceholderQueueResponse,
)
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.acquisition.acquisition_inventory_service import VARIANT_STATUS_RESOLVED


def list_unresolved_placeholders(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> PlaceholderQueueResponse:
    stmt = (
        select(AcquisitionPlaceholderIssue, Acquisition)
        .join(Acquisition, Acquisition.id == AcquisitionPlaceholderIssue.acquisition_id)
        .where(
            AcquisitionPlaceholderIssue.user_id == owner_user_id,
            AcquisitionPlaceholderIssue.catalog_issue_id.is_(None),
            AcquisitionPlaceholderIssue.catalog_status == CATALOG_STATUS_PLACEHOLDER,
        )
        .order_by(AcquisitionPlaceholderIssue.created_at.desc())
    )
    if search and search.strip():
        needle = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                AcquisitionPlaceholderIssue.title.ilike(needle),
                AcquisitionPlaceholderIssue.publisher.ilike(needle),
                AcquisitionPlaceholderIssue.issue_number.ilike(needle),
            )
        )
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    count_stmt = (
        select(func.count())
        .select_from(AcquisitionPlaceholderIssue)
        .join(Acquisition, Acquisition.id == AcquisitionPlaceholderIssue.acquisition_id)
        .where(
            AcquisitionPlaceholderIssue.user_id == owner_user_id,
            AcquisitionPlaceholderIssue.catalog_issue_id.is_(None),
            AcquisitionPlaceholderIssue.catalog_status == CATALOG_STATUS_PLACEHOLDER,
        )
    )
    if search and search.strip():
        needle = f"%{search.strip()}%"
        count_stmt = count_stmt.where(
            or_(
                AcquisitionPlaceholderIssue.title.ilike(needle),
                AcquisitionPlaceholderIssue.publisher.ilike(needle),
                AcquisitionPlaceholderIssue.issue_number.ilike(needle),
            )
        )
    total = int(session.exec(count_stmt).one())
    items = [
        PlaceholderQueueItem(
            placeholder_issue_id=int(ph.id or 0),
            acquisition_id=int(ph.acquisition_id),
            acquisition_type=acq.acquisition_type,
            seller_name=acq.seller_name,
            publisher=ph.publisher,
            title=ph.title,
            issue_number=ph.issue_number or None,
            quantity=int(ph.quantity),
            catalog_status=ph.catalog_status,
            tree_linked=bool(ph.tree_linked),
            variant_label=ph.variant_label,
            raw_variant_notes=ph.raw_variant_notes,
            created_at=ph.created_at,
            comicvine_volume_id=ph.comicvine_volume_id,
        )
        for ph, acq in rows
    ]
    return PlaceholderQueueResponse(items=items, total_count=total, limit=limit, offset=offset)


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "High"
    if score >= 0.6:
        return "Medium"
    return "Low"


def match_candidates_for_placeholder(
    session: Session,
    *,
    owner_user_id: int,
    placeholder_id: int,
    manual_search: str | None = None,
    limit: int = 25,
) -> PlaceholderMatchCandidatesResponse:
    ph = session.get(AcquisitionPlaceholderIssue, placeholder_id)
    if ph is None or int(ph.user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placeholder not found")

    label = " / ".join(
        part
        for part in [ph.publisher or "Unknown", ph.title, f"#{ph.issue_number}" if ph.issue_number else None]
        if part
    )
    norm_issue = normalize_series_name(ph.issue_number or "")
    norm_title = normalize_series_name(ph.title)
    norm_pub = normalize_series_name(ph.publisher or "")

    stmt = select(CatalogIssue, CatalogSeries, CatalogPublisher).join(
        CatalogSeries, CatalogIssue.series_id == CatalogSeries.id
    ).join(CatalogPublisher, CatalogIssue.publisher_id == CatalogPublisher.id, isouter=True)

    if manual_search and manual_search.strip():
        needle = f"%{manual_search.strip()}%"
        stmt = stmt.where(
            or_(
                CatalogIssue.title.ilike(needle),
                CatalogIssue.issue_number.ilike(needle),
                CatalogSeries.name.ilike(needle),
                CatalogPublisher.name.ilike(needle),
            )
        )
    elif ph.issue_number:
        stmt = stmt.where(CatalogIssue.normalized_issue_number == norm_issue)
    else:
        stmt = stmt.where(CatalogSeries.normalized_name.ilike(f"%{norm_title[:32]}%"))

    scored: list[tuple[float, CatalogIssue, CatalogSeries, CatalogPublisher | None]] = []
    for issue, series, publisher in session.exec(stmt.limit(200)).all():
        score = 0.0
        if ph.issue_number and issue.normalized_issue_number == norm_issue:
            score += 0.45
        if normalize_series_name(series.name) == norm_title or norm_title in normalize_series_name(series.name):
            score += 0.35
        if publisher and normalize_series_name(publisher.name) == norm_pub:
            score += 0.15
        if ph.comicvine_volume_id and series.external_source_ids:
            cv = series.external_source_ids.get("COMICVINE", {})
            if isinstance(cv, dict) and str(ph.comicvine_volume_id) in cv:
                score += 0.25
        if issue.release_date and ph.comicvine_volume_id:
            score += 0.05
        if score <= 0 and not manual_search:
            continue
        scored.append((score, issue, series, publisher))

    scored.sort(key=lambda row: (-row[0], row[1].id or 0))
    candidates: list[PlaceholderMatchCandidate] = []
    for score, issue, series, publisher in scored[:limit]:
        candidates.append(
            PlaceholderMatchCandidate(
                catalog_issue_id=int(issue.id or 0),
                series=series.name,
                issue_number=issue.issue_number,
                publisher=publisher.name if publisher else None,
                release_date=issue.release_date,
                catalog_status="CATALOGED",
                confidence=_confidence_label(score),
                score=round(score, 3),
            )
        )

    return PlaceholderMatchCandidatesResponse(
        placeholder_issue_id=placeholder_id,
        placeholder_label=label,
        candidates=candidates,
    )


def link_placeholder_to_catalog(
    session: Session,
    *,
    owner_user_id: int,
    placeholder_id: int,
    catalog_issue_id: int,
) -> LinkPlaceholderResponse:
    ph = session.get(AcquisitionPlaceholderIssue, placeholder_id)
    if ph is None or int(ph.user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placeholder not found")
    if ph.catalog_issue_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Placeholder already linked")

    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog issue not found")

    copies = list(
        session.exec(
            select(InventoryCopy).where(
                InventoryCopy.placeholder_issue_id == placeholder_id,
                InventoryCopy.user_id == owner_user_id,
            )
        ).all()
    )

    ph.catalog_issue_id = catalog_issue_id
    ph.catalog_status = CATALOG_STATUS_LINKED
    session.add(ph)

    updated = 0
    for copy in copies:
        cost_before = copy.acquisition_cost
        copy.catalog_issue_id = catalog_issue_id
        copy.variant_status = VARIANT_STATUS_RESOLVED
        copy.acquisition_cost = cost_before
        session.add(copy)
        updated += 1

    session.commit()

    return LinkPlaceholderResponse(
        placeholder_issue_id=placeholder_id,
        catalog_issue_id=catalog_issue_id,
        catalog_status=CATALOG_STATUS_LINKED,
        inventory_copies_updated=updated,
    )
