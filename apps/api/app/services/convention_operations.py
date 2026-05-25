"""P36-05 deterministic convention / show operations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    ConventionEvent,
    ConventionInventoryAssignment,
    ConventionInventoryMovement,
    ConventionPriceSnapshot,
    ConventionSaleSession,
    InventoryCopy,
)
from app.models.convention_operations import utc_now
from app.schemas.convention_operations import (
    ConventionAssignmentCreate,
    ConventionAssignmentListResponse,
    ConventionAssignmentRead,
    ConventionDashboardSummary,
    ConventionEventCreate,
    ConventionEventListResponse,
    ConventionEventPatch,
    ConventionEventRead,
    ConventionMovementCreate,
    ConventionMovementListResponse,
    ConventionMovementRead,
    ConventionPriceSnapshotCreate,
    ConventionPriceSnapshotListResponse,
    ConventionPriceSnapshotRead,
    ConventionSaleSessionCreate,
    ConventionSaleSessionListResponse,
    ConventionSaleSessionRead,
    ConventionSaleSessionStatus,
    ConventionEventStatus,
    ConventionEventType,
    ConventionAssignmentType,
    ConventionMovementType,
    ConventionPricingSource,
)

MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
CONVENTION_EVENT_TYPES = frozenset({"convention", "local_show", "trade_night", "private_event", "popup"})
CONVENTION_EVENT_STATUSES = frozenset({"PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"})
CONVENTION_ASSIGNMENT_TYPES = frozenset({"wall", "showcase", "bin", "featured", "reserve"})
CONVENTION_MOVEMENT_TYPES = frozenset({"ASSIGNED", "MOVED", "REMOVED", "SOLD", "RETURNED", "HOLD"})
CONVENTION_PRICING_SOURCES = frozenset({"default_inventory", "convention_override", "negotiated"})
CONVENTION_SESSION_STATUSES = frozenset({"OPEN", "CLOSED"})


def clamp_convention_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _event_read(row: ConventionEvent) -> ConventionEventRead:
    return ConventionEventRead.model_validate(row, from_attributes=True)


def _assignment_read(row: ConventionInventoryAssignment) -> ConventionAssignmentRead:
    return ConventionAssignmentRead.model_validate(row, from_attributes=True)


def _movement_read(row: ConventionInventoryMovement) -> ConventionMovementRead:
    return ConventionMovementRead.model_validate(row, from_attributes=True)


def _price_read(row: ConventionPriceSnapshot) -> ConventionPriceSnapshotRead:
    return ConventionPriceSnapshotRead.model_validate(row, from_attributes=True)


def _session_read(row: ConventionSaleSession) -> ConventionSaleSessionRead:
    return ConventionSaleSessionRead.model_validate(row, from_attributes=True)


def _inventory_owned(session: Session, *, inventory_item_id: int, owner_user_id: int) -> InventoryCopy:
    row = session.get(InventoryCopy, inventory_item_id)
    if row is None or int(row.user_id or 0) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory copy not found")
    return row


def _event_owned(session: Session, *, convention_event_id: int, owner_user_id: int) -> ConventionEvent:
    row = session.get(ConventionEvent, convention_event_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention event not found")
    return row


def _event_replay_match(session: Session, *, owner_user_id: int, replay_key: str | None) -> ConventionEvent | None:
    if not replay_key:
        return None
    return session.exec(
        select(ConventionEvent).where(
            ConventionEvent.owner_user_id == owner_user_id,
            ConventionEvent.replay_key == replay_key,
        )
    ).first()


def _session_replay_match(session: Session, *, convention_event_id: int, replay_key: str | None) -> ConventionSaleSession | None:
    if not replay_key:
        return None
    return session.exec(
        select(ConventionSaleSession).where(
            ConventionSaleSession.convention_event_id == convention_event_id,
            ConventionSaleSession.replay_key == replay_key,
        )
    ).first()


def _child_replay_match(
    session: Session,
    *,
    model,
    convention_event_id: int,
    replay_key: str | None,
):
    if not replay_key:
        return None
    return session.exec(
        select(model).where(
            model.convention_event_id == convention_event_id,
            model.replay_key == replay_key,
        )
    ).first()


def _ensure_event_filter_values(
    *,
    event_type: str | None,
    status: str | None,
) -> tuple[str | None, str | None]:
    if event_type is not None and event_type not in CONVENTION_EVENT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid convention event type filter")
    if status is not None and status not in CONVENTION_EVENT_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid convention event status filter")
    return event_type, status


def _match_event_ids(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
) -> list[int]:
    event_type, status = _ensure_event_filter_values(event_type=event_type, status=status)
    query = select(ConventionEvent.id)
    if owner_user_id is not None:
        query = query.where(ConventionEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        query = query.where(ConventionEvent.event_type == event_type)
    if status is not None:
        query = query.where(ConventionEvent.status == status)
    if date_from is not None:
        query = query.where(ConventionEvent.start_date >= date_from)
    if date_to is not None:
        query = query.where(ConventionEvent.end_date <= date_to)
    if inventory_item_id is not None:
        assignment_event_ids = select(ConventionInventoryAssignment.convention_event_id).where(
            ConventionInventoryAssignment.inventory_item_id == inventory_item_id
        )
        query = query.where(ConventionEvent.id.in_(assignment_event_ids))
    rows = session.exec(query.order_by(col(ConventionEvent.start_date).desc()).order_by(col(ConventionEvent.id).desc())).all()
    return [int(row) for row in rows]


def _event_order_query(session: Session, *, owner_user_id: int | None, event_type: str | None, status: str | None,
                       date_from: date | None, date_to: date | None, inventory_item_id: int | None):
    event_type, status = _ensure_event_filter_values(event_type=event_type, status=status)
    query = select(ConventionEvent)
    if owner_user_id is not None:
        query = query.where(ConventionEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        query = query.where(ConventionEvent.event_type == event_type)
    if status is not None:
        query = query.where(ConventionEvent.status == status)
    if date_from is not None:
        query = query.where(ConventionEvent.start_date >= date_from)
    if date_to is not None:
        query = query.where(ConventionEvent.end_date <= date_to)
    if inventory_item_id is not None:
        assignment_event_ids = select(ConventionInventoryAssignment.convention_event_id).where(
            ConventionInventoryAssignment.inventory_item_id == inventory_item_id
        )
        query = query.where(ConventionEvent.id.in_(assignment_event_ids))
    return query.order_by(col(ConventionEvent.start_date).desc()).order_by(col(ConventionEvent.updated_at).desc()).order_by(col(ConventionEvent.id).desc())


def _assignment_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
):
    event_ids = _match_event_ids(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    query = select(ConventionInventoryAssignment)
    if event_ids:
        query = query.where(ConventionInventoryAssignment.convention_event_id.in_(event_ids))
    else:
        query = query.where(False)
    if inventory_item_id is not None:
        query = query.where(ConventionInventoryAssignment.inventory_item_id == inventory_item_id)
    return query.order_by(
        col(ConventionInventoryAssignment.convention_event_id).asc(),
        col(ConventionInventoryAssignment.priority_rank).asc(),
        col(ConventionInventoryAssignment.assigned_at).asc(),
        col(ConventionInventoryAssignment.id).asc(),
    )


def _movement_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
):
    event_ids = _match_event_ids(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    query = select(ConventionInventoryMovement)
    if event_ids:
        query = query.where(ConventionInventoryMovement.convention_event_id.in_(event_ids))
    else:
        query = query.where(False)
    if inventory_item_id is not None:
        query = query.where(ConventionInventoryMovement.inventory_item_id == inventory_item_id)
    return query.order_by(
        col(ConventionInventoryMovement.created_at).desc(),
        col(ConventionInventoryMovement.id).desc(),
    )


def _price_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
):
    event_ids = _match_event_ids(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    query = select(ConventionPriceSnapshot)
    if event_ids:
        query = query.where(ConventionPriceSnapshot.convention_event_id.in_(event_ids))
    else:
        query = query.where(False)
    if inventory_item_id is not None:
        query = query.where(ConventionPriceSnapshot.inventory_item_id == inventory_item_id)
    return query.order_by(
        col(ConventionPriceSnapshot.created_at).desc(),
        col(ConventionPriceSnapshot.id).desc(),
    )


def _session_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
):
    event_ids = _match_event_ids(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    query = select(ConventionSaleSession)
    if event_ids:
        query = query.where(ConventionSaleSession.convention_event_id.in_(event_ids))
    else:
        query = query.where(False)
    return query.order_by(
        col(ConventionSaleSession.opened_at).desc(),
        col(ConventionSaleSession.id).desc(),
    )


def _event_lookup_or_404(session: Session, *, owner_user_id: int, convention_event_id: int) -> ConventionEvent:
    event = _event_owned(session, convention_event_id=convention_event_id, owner_user_id=owner_user_id)
    return event


def _validate_event_payload(payload: ConventionEventCreate | ConventionEventPatch) -> None:
    if getattr(payload, "event_type", None) is not None and payload.event_type not in CONVENTION_EVENT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid convention event type")
    if getattr(payload, "start_date", None) is not None and getattr(payload, "end_date", None) is not None:
        if payload.end_date < payload.start_date:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_date must be on or after start_date")


def create_convention_event(
    session: Session,
    *,
    owner_user_id: int,
    payload: ConventionEventCreate | dict,
) -> tuple[ConventionEvent, bool]:
    if not isinstance(payload, ConventionEventCreate):
        payload = ConventionEventCreate.model_validate(payload)
    _validate_event_payload(payload)
    replayed = _event_replay_match(session, owner_user_id=owner_user_id, replay_key=payload.replay_key)
    if replayed is not None:
        return replayed, True
    now_ts = utc_now()
    row = ConventionEvent(
        owner_user_id=owner_user_id,
        replay_key=payload.replay_key,
        name=payload.name.strip(),
        venue=_trim(payload.venue),
        city=_trim(payload.city),
        state=_trim(payload.state),
        country=_trim(payload.country),
        start_date=payload.start_date,
        end_date=payload.end_date,
        event_type=str(payload.event_type),
        status="PLANNED",
        notes=_trim(payload.notes),
        created_at=now_ts,
        updated_at=now_ts,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        replayed = _event_replay_match(session, owner_user_id=owner_user_id, replay_key=payload.replay_key)
        if replayed is not None:
            return replayed, True
        raise
    session.refresh(row)
    return row, False


def patch_convention_event(
    session: Session,
    *,
    owner_user_id: int,
    convention_event_id: int,
    payload: ConventionEventPatch | dict,
) -> ConventionEvent:
    if not isinstance(payload, ConventionEventPatch):
        payload = ConventionEventPatch.model_validate(payload)
    _validate_event_payload(payload)
    row = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.venue is not None:
        row.venue = _trim(payload.venue)
    if payload.city is not None:
        row.city = _trim(payload.city)
    if payload.state is not None:
        row.state = _trim(payload.state)
    if payload.country is not None:
        row.country = _trim(payload.country)
    if payload.start_date is not None:
        row.start_date = payload.start_date
    if payload.end_date is not None:
        row.end_date = payload.end_date
    if payload.event_type is not None:
        row.event_type = str(payload.event_type)
    if payload.notes is not None:
        row.notes = _trim(payload.notes)
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def activate_convention_event(
    session: Session,
    *,
    owner_user_id: int,
    convention_event_id: int,
    replay_key: str | None = None,
) -> ConventionEvent:
    row = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
    if row.status == "ACTIVE":
        return row
    if row.status not in {"PLANNED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="event cannot be activated from current status")
    row.status = "ACTIVE"
    row.activated_at = row.activated_at or utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def complete_convention_event(
    session: Session,
    *,
    owner_user_id: int,
    convention_event_id: int,
    replay_key: str | None = None,
) -> ConventionEvent:
    row = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
    if row.status == "COMPLETED":
        return row
    if row.status not in {"ACTIVE"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="event cannot be completed from current status")
    row.status = "COMPLETED"
    row.completed_at = row.completed_at or utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_convention_events_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionEvent], int]:
    query = _event_order_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_events_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionEvent], int]:
    query = _event_order_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def get_convention_event_owner(session: Session, *, owner_user_id: int, convention_event_id: int) -> ConventionEvent:
    return _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)


def get_convention_event_ops(session: Session, *, convention_event_id: int) -> ConventionEvent:
    row = session.get(ConventionEvent, convention_event_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention event not found")
    return row


def _next_assignment_rank(session: Session, *, convention_event_id: int) -> int:
    ranks = session.exec(
        select(ConventionInventoryAssignment.priority_rank).where(
            ConventionInventoryAssignment.convention_event_id == convention_event_id
        )
    ).all()
    values = [int(rank) for rank in ranks if rank is not None]
    return (max(values) + 1) if values else 1


def _active_assignment(session: Session, *, convention_event_id: int, inventory_item_id: int) -> ConventionInventoryAssignment | None:
    return session.exec(
        select(ConventionInventoryAssignment).where(
            ConventionInventoryAssignment.convention_event_id == convention_event_id,
            ConventionInventoryAssignment.inventory_item_id == inventory_item_id,
            ConventionInventoryAssignment.removed_at.is_(None),
        )
    ).first()


def create_convention_assignment(
    session: Session,
    *,
    owner_user_id: int,
    payload: ConventionAssignmentCreate | dict,
) -> tuple[ConventionInventoryAssignment, bool]:
    if not isinstance(payload, ConventionAssignmentCreate):
        payload = ConventionAssignmentCreate.model_validate(payload)
    if payload.assignment_type not in CONVENTION_ASSIGNMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid assignment type")
    if payload.local_price_currency is not None and payload.local_price_amount is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="local_price_amount is required when local_price_currency is set")
    if payload.local_price_amount is not None and payload.local_price_currency is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="local_price_currency is required when local_price_amount is set")
    event = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=payload.convention_event_id)
    _inventory_owned(session, inventory_item_id=payload.inventory_item_id, owner_user_id=owner_user_id)
    replayed = _child_replay_match(session, model=ConventionInventoryAssignment, convention_event_id=event.id, replay_key=payload.replay_key)
    if replayed is not None:
        return replayed, True
    if _active_assignment(session, convention_event_id=event.id, inventory_item_id=payload.inventory_item_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="inventory item already has an active convention assignment for this event")
    row = ConventionInventoryAssignment(
        convention_event_id=event.id,
        inventory_item_id=payload.inventory_item_id,
        replay_key=payload.replay_key,
        assignment_type=str(payload.assignment_type),
        local_price_amount=_money(payload.local_price_amount) if payload.local_price_amount is not None else None,
        local_price_currency=payload.local_price_currency.upper() if payload.local_price_currency else None,
        display_location=_trim(payload.display_location),
        priority_rank=payload.priority_rank if payload.priority_rank is not None else _next_assignment_rank(session, convention_event_id=event.id),
        assigned_at=utc_now(),
        removed_at=None,
        created_at=utc_now(),
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        replayed = _child_replay_match(session, model=ConventionInventoryAssignment, convention_event_id=event.id, replay_key=payload.replay_key)
        if replayed is not None:
            return replayed, True
        raise
    session.refresh(row)
    return row, False


def _active_assignment_for_update(session: Session, *, convention_event_id: int, inventory_item_id: int) -> ConventionInventoryAssignment | None:
    return _active_assignment(session, convention_event_id=convention_event_id, inventory_item_id=inventory_item_id)


def create_convention_movement(
    session: Session,
    *,
    owner_user_id: int,
    created_by_user_id: int,
    payload: ConventionMovementCreate | dict,
) -> tuple[ConventionInventoryMovement, bool]:
    if not isinstance(payload, ConventionMovementCreate):
        payload = ConventionMovementCreate.model_validate(payload)
    if payload.movement_type not in CONVENTION_MOVEMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid movement type")
    event = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=payload.convention_event_id)
    _inventory_owned(session, inventory_item_id=payload.inventory_item_id, owner_user_id=owner_user_id)
    replayed = _child_replay_match(session, model=ConventionInventoryMovement, convention_event_id=event.id, replay_key=payload.replay_key)
    if replayed is not None:
        return replayed, True
    assignment = _active_assignment_for_update(session, convention_event_id=event.id, inventory_item_id=payload.inventory_item_id)
    now_ts = utc_now()
    if assignment is not None:
        if payload.to_location is not None:
            assignment.display_location = _trim(payload.to_location)
        if payload.movement_type in {"REMOVED", "RETURNED", "SOLD"}:
            assignment.removed_at = assignment.removed_at or now_ts
        session.add(assignment)
    row = ConventionInventoryMovement(
        convention_event_id=event.id,
        inventory_item_id=payload.inventory_item_id,
        replay_key=payload.replay_key,
        movement_type=str(payload.movement_type),
        from_location=_trim(payload.from_location),
        to_location=_trim(payload.to_location),
        notes=_trim(payload.notes),
        created_by_user_id=created_by_user_id,
        created_at=now_ts,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        replayed = _child_replay_match(session, model=ConventionInventoryMovement, convention_event_id=event.id, replay_key=payload.replay_key)
        if replayed is not None:
            return replayed, True
        raise
    session.refresh(row)
    return row, False


def create_convention_price_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    payload: ConventionPriceSnapshotCreate | dict,
) -> tuple[ConventionPriceSnapshot, bool]:
    if not isinstance(payload, ConventionPriceSnapshotCreate):
        payload = ConventionPriceSnapshotCreate.model_validate(payload)
    if payload.pricing_source not in CONVENTION_PRICING_SOURCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid pricing source")
    event = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=payload.convention_event_id)
    _inventory_owned(session, inventory_item_id=payload.inventory_item_id, owner_user_id=owner_user_id)
    replayed = _child_replay_match(session, model=ConventionPriceSnapshot, convention_event_id=event.id, replay_key=payload.replay_key)
    if replayed is not None:
        return replayed, True
    row = ConventionPriceSnapshot(
        convention_event_id=event.id,
        inventory_item_id=payload.inventory_item_id,
        replay_key=payload.replay_key,
        price_amount=_money(payload.price_amount),
        currency=payload.currency.upper(),
        pricing_source=str(payload.pricing_source),
        created_at=utc_now(),
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        replayed = _child_replay_match(session, model=ConventionPriceSnapshot, convention_event_id=event.id, replay_key=payload.replay_key)
        if replayed is not None:
            return replayed, True
        raise
    session.refresh(row)
    return row, False


def resolve_convention_price(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    convention_event_id: int | None = None,
) -> dict[str, Any]:
    _inventory_owned(session, inventory_item_id=inventory_item_id, owner_user_id=owner_user_id)
    query = (
        select(ConventionPriceSnapshot)
        .join(ConventionEvent, ConventionPriceSnapshot.convention_event_id == ConventionEvent.id)
        .where(
            ConventionEvent.owner_user_id == owner_user_id,
            ConventionPriceSnapshot.inventory_item_id == inventory_item_id,
        )
    )
    if convention_event_id is not None:
        query = query.where(ConventionPriceSnapshot.convention_event_id == convention_event_id)
    row = session.exec(query.order_by(col(ConventionPriceSnapshot.created_at).desc(), col(ConventionPriceSnapshot.id).desc())).first()
    if row is not None:
        return {
            "source": row.pricing_source,
            "price_amount": row.price_amount,
            "currency": row.currency,
            "convention_event_id": row.convention_event_id,
            "snapshot_id": row.id,
        }
    inventory_copy = _inventory_owned(session, inventory_item_id=inventory_item_id, owner_user_id=owner_user_id)
    return {
        "source": "default_inventory",
        "price_amount": inventory_copy.current_fmv,
        "currency": "USD",
        "convention_event_id": convention_event_id,
        "snapshot_id": None,
    }


def create_convention_sale_session(
    session: Session,
    *,
    owner_user_id: int,
    payload: ConventionSaleSessionCreate | dict,
) -> tuple[ConventionSaleSession, bool]:
    if not isinstance(payload, ConventionSaleSessionCreate):
        payload = ConventionSaleSessionCreate.model_validate(payload)
    event = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=payload.convention_event_id)
    replayed = _session_replay_match(session, convention_event_id=event.id, replay_key=payload.replay_key)
    if replayed is not None:
        return replayed, True
    open_existing = session.exec(
        select(ConventionSaleSession).where(
            ConventionSaleSession.convention_event_id == event.id,
            ConventionSaleSession.status == "OPEN",
        )
    ).first()
    if open_existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="an open convention sale session already exists for this event")
    row = ConventionSaleSession(
        convention_event_id=event.id,
        owner_user_id=owner_user_id,
        replay_key=payload.replay_key,
        status="OPEN",
        opened_at=utc_now(),
        closed_at=None,
        notes=_trim(payload.notes),
        created_at=utc_now(),
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        replayed = _session_replay_match(session, convention_event_id=event.id, replay_key=payload.replay_key)
        if replayed is not None:
            return replayed, True
        raise
    session.refresh(row)
    return row, False


def close_convention_sale_session(
    session: Session,
    *,
    owner_user_id: int,
    convention_sale_session_id: int,
    replay_key: str | None = None,
) -> ConventionSaleSession:
    row = session.get(ConventionSaleSession, convention_sale_session_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention sale session not found")
    if row.status == "CLOSED":
        return row
    row.status = "CLOSED"
    row.closed_at = row.closed_at or utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_convention_assignments_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionInventoryAssignment], int]:
    if convention_event_id is not None:
        _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
    query = _assignment_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        query = query.where(ConventionInventoryAssignment.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_assignments_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionInventoryAssignment], int]:
    query = _assignment_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        query = query.where(ConventionInventoryAssignment.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_movements_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionInventoryMovement], int]:
    query = _movement_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
        query = query.where(ConventionInventoryMovement.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_movements_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionInventoryMovement], int]:
    query = _movement_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        query = query.where(ConventionInventoryMovement.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_price_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionPriceSnapshot], int]:
    query = _price_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
        query = query.where(ConventionPriceSnapshot.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_price_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionPriceSnapshot], int]:
    query = _price_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        query = query.where(ConventionPriceSnapshot.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_sale_sessions_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionSaleSession], int]:
    query = _session_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=convention_event_id)
        query = query.where(ConventionSaleSession.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def list_convention_sale_sessions_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    inventory_item_id: int | None = None,
    convention_event_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ConventionSaleSession], int]:
    query = _session_query(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
    )
    if convention_event_id is not None:
        query = query.where(ConventionSaleSession.convention_event_id == convention_event_id)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.exec(query.offset(offset).limit(limit)).all()
    return list(rows), total


def get_convention_assignment_owner(session: Session, *, owner_user_id: int, assignment_id: int) -> ConventionInventoryAssignment:
    row = session.get(ConventionInventoryAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention assignment not found")
    event = _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=row.convention_event_id)
    return row


def get_convention_assignment_ops(session: Session, *, assignment_id: int) -> ConventionInventoryAssignment:
    row = session.get(ConventionInventoryAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention assignment not found")
    return row


def get_convention_movement_owner(session: Session, *, owner_user_id: int, movement_id: int) -> ConventionInventoryMovement:
    row = session.get(ConventionInventoryMovement, movement_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention movement not found")
    _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=row.convention_event_id)
    return row


def get_convention_movement_ops(session: Session, *, movement_id: int) -> ConventionInventoryMovement:
    row = session.get(ConventionInventoryMovement, movement_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention movement not found")
    return row


def get_convention_price_owner(session: Session, *, owner_user_id: int, price_snapshot_id: int) -> ConventionPriceSnapshot:
    row = session.get(ConventionPriceSnapshot, price_snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention price snapshot not found")
    _event_lookup_or_404(session, owner_user_id=owner_user_id, convention_event_id=row.convention_event_id)
    return row


def get_convention_price_ops(session: Session, *, price_snapshot_id: int) -> ConventionPriceSnapshot:
    row = session.get(ConventionPriceSnapshot, price_snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention price snapshot not found")
    return row


def get_convention_sale_session_owner(session: Session, *, owner_user_id: int, sale_session_id: int) -> ConventionSaleSession:
    row = session.get(ConventionSaleSession, sale_session_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention sale session not found")
    return row


def get_convention_sale_session_ops(session: Session, *, sale_session_id: int) -> ConventionSaleSession:
    row = session.get(ConventionSaleSession, sale_session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="convention sale session not found")
    return row


def _dashboard_summary(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> ConventionDashboardSummary:
    event_query = select(ConventionEvent)
    if owner_user_id is not None:
        event_query = event_query.where(ConventionEvent.owner_user_id == owner_user_id)
    events = session.exec(
        event_query.order_by(col(ConventionEvent.updated_at).desc(), col(ConventionEvent.id).desc())
    ).all()
    active_events = [row for row in events if row.status == "ACTIVE"]
    assignment_query = select(ConventionInventoryAssignment).join(
        ConventionEvent, ConventionInventoryAssignment.convention_event_id == ConventionEvent.id
    )
    if owner_user_id is not None:
        assignment_query = assignment_query.where(ConventionEvent.owner_user_id == owner_user_id)
    assignment_rows = session.exec(
        assignment_query.where(
            ConventionEvent.status == "ACTIVE",
            ConventionInventoryAssignment.removed_at.is_(None),
        )
        .order_by(
            col(ConventionInventoryAssignment.convention_event_id).asc(),
            col(ConventionInventoryAssignment.priority_rank).asc(),
            col(ConventionInventoryAssignment.id).asc(),
        )
    ).all()
    wall_count = sum(1 for row in assignment_rows if row.assignment_type == "wall")
    showcase_count = sum(1 for row in assignment_rows if row.assignment_type == "showcase")
    active_session_query = select(ConventionSaleSession).join(ConventionEvent, ConventionSaleSession.convention_event_id == ConventionEvent.id).where(
        ConventionSaleSession.status == "OPEN",
        ConventionEvent.status == "ACTIVE",
    )
    if owner_user_id is not None:
        active_session_query = active_session_query.where(ConventionEvent.owner_user_id == owner_user_id)
    active_session_count = int(session.scalar(select(func.count()).select_from(active_session_query.subquery())) or 0)
    active_convention_count = len(active_events)
    assigned_inventory_count = len({row.inventory_item_id for row in assignment_rows})
    recent_events = events[:5]
    return ConventionDashboardSummary(
        active_convention_count=active_convention_count,
        assigned_inventory_count=assigned_inventory_count,
        wall_book_count=wall_count,
        showcase_count=showcase_count,
        active_sale_session_count=active_session_count,
        recent_events=[_event_read(row) for row in recent_events],
    )


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> ConventionDashboardSummary:
    return _dashboard_summary(session, owner_user_id=owner_user_id)


def dashboard_summary_ops(session: Session, *, owner_user_id: int | None = None) -> ConventionDashboardSummary:
    return _dashboard_summary(session, owner_user_id=owner_user_id)

