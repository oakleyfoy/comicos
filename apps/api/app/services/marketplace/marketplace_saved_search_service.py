"""P88-03 saved marketplace search CRUD."""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.p88_marketplace_monitoring import MarketplaceMonitoringRun, MarketplaceSavedSearch, utc_now
from app.schemas.p88_marketplace_monitoring import (
    MarketplaceMonitoringRunListResponse,
    MarketplaceMonitoringRunRead,
    MarketplaceSavedSearchCreatePayload,
    MarketplaceSavedSearchListResponse,
    MarketplaceSavedSearchRead,
    MarketplaceSavedSearchRunResponse,
    MarketplaceSavedSearchUpdatePayload,
)
from app.services.marketplace.marketplace_monitoring_service import run_saved_search


def _to_read(row: MarketplaceSavedSearch) -> MarketplaceSavedSearchRead:
    return MarketplaceSavedSearchRead(
        id=int(row.id or 0),
        name=row.name,
        marketplace=row.marketplace,
        query=row.query,
        series=row.series,
        issue_number=row.issue_number,
        publisher=row.publisher,
        variant=row.variant,
        max_price=row.max_price,
        min_discount_to_fmv=row.min_discount_to_fmv,
        condition_filter=row.condition_filter,
        is_active=bool(row.is_active),
        last_run_at=row.last_run_at,
        last_success_at=row.last_success_at,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_saved_searches(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> MarketplaceSavedSearchListResponse:
    rows = list(
        session.exec(
            select(MarketplaceSavedSearch)
            .where(MarketplaceSavedSearch.owner_user_id == owner_user_id)
            .order_by(MarketplaceSavedSearch.updated_at.desc())
        ).all()
    )
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    page = [_to_read(r) for r in rows[off : off + lim]]
    return MarketplaceSavedSearchListResponse(items=page, total_items=len(rows), limit=lim, offset=off)


def create_saved_search(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketplaceSavedSearchCreatePayload,
) -> MarketplaceSavedSearchRead:
    if not (payload.query.strip() or (payload.series.strip() and payload.issue_number.strip())):
        raise HTTPException(status_code=422, detail="Provide query or series and issue.")
    now = utc_now()
    row = MarketplaceSavedSearch(
        owner_user_id=owner_user_id,
        name=payload.name.strip(),
        marketplace=(payload.marketplace or "EBAY").strip().upper(),
        query=payload.query.strip(),
        series=payload.series.strip(),
        issue_number=payload.issue_number.strip(),
        publisher=payload.publisher.strip(),
        variant=payload.variant.strip(),
        max_price=payload.max_price,
        min_discount_to_fmv=payload.min_discount_to_fmv,
        condition_filter=payload.condition_filter.strip(),
        is_active=payload.is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _to_read(row)


def update_saved_search(
    session: Session,
    *,
    owner_user_id: int,
    saved_search_id: int,
    payload: MarketplaceSavedSearchUpdatePayload,
) -> MarketplaceSavedSearchRead:
    row = session.get(MarketplaceSavedSearch, saved_search_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "marketplace" and isinstance(value, str):
            setattr(row, key, value.strip().upper())
        elif isinstance(value, str):
            setattr(row, key, value.strip())
        else:
            setattr(row, key, value)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return _to_read(row)


def delete_saved_search(session: Session, *, owner_user_id: int, saved_search_id: int) -> None:
    row = session.get(MarketplaceSavedSearch, saved_search_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    session.delete(row)


def _run_to_read(row: MarketplaceMonitoringRun) -> MarketplaceMonitoringRunRead:
    return MarketplaceMonitoringRunRead(
        id=int(row.id or 0),
        saved_search_id=row.saved_search_id,
        searches_run=row.searches_run,
        listings_found=row.listings_found,
        new_listings=row.new_listings,
        price_drops=row.price_drops,
        below_fmv_alerts=row.below_fmv_alerts,
        watchlist_matches=row.watchlist_matches,
        errors=list(row.errors_json or []),
        created_at=row.created_at,
    )


def run_saved_search_by_id(
    session: Session,
    *,
    owner_user_id: int,
    saved_search_id: int,
    dry_run: bool = False,
) -> MarketplaceSavedSearchRunResponse:
    row = session.get(MarketplaceSavedSearch, saved_search_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    summary = run_saved_search(session, saved=row, dry_run=dry_run)
    session.refresh(row)
    if dry_run:
        run_read = MarketplaceMonitoringRunRead(
            id=0,
            saved_search_id=saved_search_id,
            searches_run=summary.searches_run,
            listings_found=summary.listings_found,
            new_listings=summary.new_listings,
            price_drops=summary.price_drops,
            below_fmv_alerts=summary.below_fmv_alerts,
            watchlist_matches=summary.watchlist_matches,
            errors=summary.errors,
            created_at=utc_now(),
        )
        return MarketplaceSavedSearchRunResponse(saved_search=_to_read(row), run=run_read, dry_run=True)
    latest = session.exec(
        select(MarketplaceMonitoringRun)
        .where(MarketplaceMonitoringRun.saved_search_id == saved_search_id)
        .order_by(MarketplaceMonitoringRun.id.desc())
        .limit(1)
    ).first()
    if latest is None:
        raise HTTPException(status_code=500, detail="Monitoring run did not persist.")
    return MarketplaceSavedSearchRunResponse(
        saved_search=_to_read(row),
        run=_run_to_read(latest),
        dry_run=False,
    )


def list_monitoring_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> MarketplaceMonitoringRunListResponse:
    rows = list(
        session.exec(
            select(MarketplaceMonitoringRun)
            .where(MarketplaceMonitoringRun.owner_user_id == owner_user_id)
            .order_by(MarketplaceMonitoringRun.id.desc())
        ).all()
    )
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    page = [_run_to_read(r) for r in rows[off : off + lim]]
    return MarketplaceMonitoringRunListResponse(items=page, total_items=len(rows), limit=lim, offset=off)
