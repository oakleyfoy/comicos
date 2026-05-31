from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceExecution
from app.schemas.marketplace import (
    MarketplaceExecutionDetail,
    MarketplaceExecutionListResponse,
    MarketplaceExecutionRead,
)
from app.services.marketplace_accounts import get_account
from app.services.marketplace_registry import get_marketplace

EXECUTION_STATUS_STARTED = "STARTED"
EXECUTION_STATUS_COMPLETED = "COMPLETED"
EXECUTION_STATUS_FAILED = "FAILED"
EXECUTION_STATUS_EVENT = "EVENT"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _execution_read(row: MarketplaceExecution) -> MarketplaceExecutionRead:
    return MarketplaceExecutionRead(
        id=int(row.id or 0),
        marketplace_id=row.marketplace_id,
        account_id=row.account_id,
        execution_uuid=row.execution_uuid,
        execution_type=row.execution_type,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=row.duration_ms,
        created_at=row.created_at,
    )


def _execution_or_404(session: Session, *, execution_id: int) -> MarketplaceExecution:
    row = session.get(MarketplaceExecution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace execution not found.")
    return row


def start_execution(
    session: Session,
    *,
    marketplace_id: int,
    account_id: int | None,
    execution_type: str,
    execution_uuid: str | None = None,
) -> MarketplaceExecutionRead:
    now = utc_now()
    row = MarketplaceExecution(
        marketplace_id=marketplace_id,
        account_id=account_id,
        execution_uuid=execution_uuid or str(uuid4()),
        execution_type=execution_type.strip(),
        status=EXECUTION_STATUS_STARTED,
        started_at=now,
        completed_at=None,
        duration_ms=None,
        created_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _execution_read(row)


def complete_execution(session: Session, *, execution_id: int) -> MarketplaceExecutionRead:
    row = _execution_or_404(session, execution_id=execution_id)
    completed_at = utc_now()
    row.status = EXECUTION_STATUS_COMPLETED
    row.completed_at = completed_at
    row.duration_ms = max(int((completed_at - _as_utc(row.started_at)).total_seconds() * 1000), 0)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _execution_read(row)


def fail_execution(session: Session, *, execution_id: int) -> MarketplaceExecutionRead:
    row = _execution_or_404(session, execution_id=execution_id)
    completed_at = utc_now()
    row.status = EXECUTION_STATUS_FAILED
    row.completed_at = completed_at
    row.duration_ms = max(int((completed_at - _as_utc(row.started_at)).total_seconds() * 1000), 0)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _execution_read(row)


def log_execution_event(
    session: Session,
    *,
    marketplace_id: int,
    account_id: int | None,
    execution_uuid: str,
    event_type: str,
) -> MarketplaceExecutionRead:
    now = utc_now()
    row = MarketplaceExecution(
        marketplace_id=marketplace_id,
        account_id=account_id,
        execution_uuid=f"{execution_uuid}:{event_type}:{uuid4()}",
        execution_type=event_type.strip(),
        status=EXECUTION_STATUS_EVENT,
        started_at=now,
        completed_at=now,
        duration_ms=0,
        created_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _execution_read(row)


def list_executions(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceExecutionListResponse:
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceExecution)
        .join(MarketplaceAccount, isouter=True)
        .where((MarketplaceExecution.account_id.is_(None)) | (MarketplaceAccount.owner_id == owner_id))
        .order_by(MarketplaceExecution.created_at.desc(), MarketplaceExecution.id.desc())
    ).all()
    items = [_execution_read(row) for row in rows]
    return MarketplaceExecutionListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_execution(session: Session, *, owner_id: int, execution_id: int) -> MarketplaceExecutionDetail:
    row = _execution_or_404(session, execution_id=execution_id)
    if row.account_id is not None:
        account = get_account(session, owner_id=owner_id, account_id=row.account_id)
    else:
        account = None
    return MarketplaceExecutionDetail(
        execution=_execution_read(row),
        marketplace=get_marketplace(session, marketplace_id=row.marketplace_id),
        account=account,
    )
