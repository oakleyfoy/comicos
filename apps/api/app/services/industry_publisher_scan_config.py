from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.industry_publisher import INDUSTRY_PUBLISHER_INCLUSION_STATUSES, IndustryPublisher
from app.models.asset_ledger import utc_now
from app.schemas.industry_publisher import IndustryPublisherRead, IndustryPublisherUpdate
from app.services.industry_publisher_seed import ensure_industry_publishers_for_owner


def _to_read(row: IndustryPublisher) -> IndustryPublisherRead:
    return IndustryPublisherRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        publisher_code=row.publisher_code,
        publisher_name=row.publisher_name,
        scan_enabled=bool(row.scan_enabled),
        inclusion_status=row.inclusion_status,
        scan_priority=int(row.scan_priority),
        classification_mode=row.classification_mode,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def apply_scan_configuration(
    row: IndustryPublisher,
    *,
    update: IndustryPublisherUpdate,
) -> None:
    if update.scan_enabled is not None:
        row.scan_enabled = update.scan_enabled
    if update.inclusion_status is not None:
        status = update.inclusion_status.strip().upper()
        if status not in INDUSTRY_PUBLISHER_INCLUSION_STATUSES:
            raise HTTPException(status_code=422, detail="inclusion_status must be INCLUDED or EXCLUDED")
        row.inclusion_status = status
        if status == "EXCLUDED":
            row.scan_enabled = False
        elif update.scan_enabled is None and status == "INCLUDED":
            row.scan_enabled = True
    if update.scan_priority is not None:
        row.scan_priority = int(update.scan_priority)
    if update.classification_mode is not None:
        row.classification_mode = update.classification_mode.strip().upper() or "STANDARD"
    row.updated_at = utc_now()


def list_industry_publishers(session: Session, *, owner_user_id: int) -> list[IndustryPublisherRead]:
    ensure_industry_publishers_for_owner(session, owner_user_id=owner_user_id)
    rows = session.exec(
        select(IndustryPublisher)
        .where(IndustryPublisher.owner_user_id == owner_user_id)
        .order_by(IndustryPublisher.scan_priority.asc(), IndustryPublisher.publisher_name.asc())
    ).all()
    return [_to_read(row) for row in rows]


def update_industry_publisher(
    session: Session,
    *,
    owner_user_id: int,
    publisher_id: int,
    update: IndustryPublisherUpdate,
) -> IndustryPublisherRead:
    ensure_industry_publishers_for_owner(session, owner_user_id=owner_user_id)
    row = session.exec(
        select(IndustryPublisher)
        .where(IndustryPublisher.id == publisher_id)
        .where(IndustryPublisher.owner_user_id == owner_user_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Industry publisher not found")
    apply_scan_configuration(row, update=update)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(row)


def included_publishers_for_scan(session: Session, *, owner_user_id: int) -> list[IndustryPublisherRead]:
    items = list_industry_publishers(session, owner_user_id=owner_user_id)
    return [
        item
        for item in items
        if item.scan_enabled and item.inclusion_status == "INCLUDED"
    ]
