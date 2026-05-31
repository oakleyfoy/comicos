from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.want_list import (
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DEFAULT_WANT_LIST_NAME,
    WANT_LIST_PRIORITIES,
    WANT_LIST_STATUSES,
    WantList,
    WantListItem,
    utc_now,
)
from app.schemas.want_list import (
    WantListCreate,
    WantListItemCreate,
    WantListItemRead,
    WantListItemUpdate,
    WantListListRead,
    WantListRead,
    WantListSummaryRead,
    WantListUpdate,
)


class WantListNotFoundError(LookupError):
    pass


class WantListItemNotFoundError(LookupError):
    pass


def _validate_priority(value: str) -> str:
    upper = value.strip().upper()
    if upper not in WANT_LIST_PRIORITIES:
        raise ValueError(f"Invalid priority: {value}")
    return upper


def _validate_status(value: str) -> str:
    upper = value.strip().upper()
    if upper not in WANT_LIST_STATUSES:
        raise ValueError(f"Invalid status: {value}")
    return upper


def _item_to_read(row: WantListItem) -> WantListItemRead:
    return WantListItemRead(
        id=int(row.id or 0),
        want_list_id=int(row.want_list_id),
        owner_id=int(row.owner_user_id),
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        variant_description=row.variant_description,
        priority=row.priority,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        notes=row.notes,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _list_to_read(row: WantList, *, items: list[WantListItemRead] | None = None) -> WantListRead:
    return WantListRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        name=row.name,
        description=row.description,
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        items=items or [],
    )


def _summary_to_read(row: WantList, *, item_count: int) -> WantListSummaryRead:
    return WantListSummaryRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        name=row.name,
        description=row.description,
        is_active=bool(row.is_active),
        item_count=item_count,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _get_list_row(session: Session, *, owner_user_id: int, want_list_id: int) -> WantList:
    row = session.exec(
        select(WantList).where(WantList.id == want_list_id, WantList.owner_user_id == owner_user_id)
    ).first()
    if row is None:
        raise WantListNotFoundError(f"Want list {want_list_id} not found.")
    return row


def _get_item_row(session: Session, *, owner_user_id: int, item_id: int) -> WantListItem:
    row = session.exec(
        select(WantListItem).where(WantListItem.id == item_id, WantListItem.owner_user_id == owner_user_id)
    ).first()
    if row is None:
        raise WantListItemNotFoundError(f"Want list item {item_id} not found.")
    return row


def ensure_default_want_list(session: Session, *, owner_user_id: int) -> WantList:
    row = session.exec(
        select(WantList).where(
            WantList.owner_user_id == owner_user_id,
            WantList.name == DEFAULT_WANT_LIST_NAME,
            WantList.is_active == True,  # noqa: E712
        )
    ).first()
    if row is not None:
        return row
    row = WantList(
        owner_user_id=owner_user_id,
        name=DEFAULT_WANT_LIST_NAME,
        description="Default want list for comics you wish to acquire.",
        is_active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def create_want_list(session: Session, *, owner_user_id: int, payload: WantListCreate) -> WantListRead:
    row = WantList(
        owner_user_id=owner_user_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        is_active=payload.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _list_to_read(row, items=[])


def update_want_list(
    session: Session,
    *,
    owner_user_id: int,
    want_list_id: int,
    payload: WantListUpdate,
) -> WantListRead:
    row = _get_list_row(session, owner_user_id=owner_user_id, want_list_id=want_list_id)
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.is_active is not None:
        row.is_active = payload.is_active
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    items = list(
        session.exec(
            select(WantListItem)
            .where(WantListItem.want_list_id == want_list_id, WantListItem.owner_user_id == owner_user_id)
            .order_by(WantListItem.id)
        ).all()
    )
    return _list_to_read(row, items=[_item_to_read(i) for i in items])


def get_want_lists(session: Session, *, owner_user_id: int) -> WantListListRead:
    ensure_default_want_list(session, owner_user_id=owner_user_id)
    lists = list(
        session.exec(
            select(WantList).where(WantList.owner_user_id == owner_user_id).order_by(WantList.id)
        ).all()
    )
    counts: dict[int, int] = {}
    if lists:
        list_ids = [int(wl.id or 0) for wl in lists]
        count_rows = session.exec(
            select(WantListItem.want_list_id, func.count())
            .where(WantListItem.want_list_id.in_(list_ids), WantListItem.owner_user_id == owner_user_id)
            .group_by(WantListItem.want_list_id)
        ).all()
        counts = {int(wid): int(cnt) for wid, cnt in count_rows}
    summaries = [_summary_to_read(wl, item_count=counts.get(int(wl.id or 0), 0)) for wl in lists]
    return WantListListRead(items=summaries)


def get_want_list(session: Session, *, owner_user_id: int, want_list_id: int) -> WantListRead:
    row = _get_list_row(session, owner_user_id=owner_user_id, want_list_id=want_list_id)
    items = list(
        session.exec(
            select(WantListItem)
            .where(WantListItem.want_list_id == want_list_id, WantListItem.owner_user_id == owner_user_id)
            .order_by(WantListItem.id)
        ).all()
    )
    return _list_to_read(row, items=[_item_to_read(i) for i in items])


def add_want_item(
    session: Session,
    *,
    owner_user_id: int,
    want_list_id: int,
    payload: WantListItemCreate,
) -> WantListItemRead:
    _get_list_row(session, owner_user_id=owner_user_id, want_list_id=want_list_id)
    priority = _validate_priority(payload.priority) if payload.priority else DEFAULT_PRIORITY
    status = _validate_status(payload.status) if payload.status else DEFAULT_STATUS
    row = WantListItem(
        want_list_id=want_list_id,
        owner_user_id=owner_user_id,
        publisher=payload.publisher.strip(),
        series_name=payload.series_name.strip(),
        issue_number=payload.issue_number.strip(),
        variant_description=payload.variant_description.strip(),
        priority=priority,
        status=status,
        notes=payload.notes.strip(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _item_to_read(row)


def update_want_item(
    session: Session,
    *,
    owner_user_id: int,
    item_id: int,
    payload: WantListItemUpdate,
) -> WantListItemRead:
    row = _get_item_row(session, owner_user_id=owner_user_id, item_id=item_id)
    if payload.publisher is not None:
        row.publisher = payload.publisher.strip()
    if payload.series_name is not None:
        row.series_name = payload.series_name.strip()
    if payload.issue_number is not None:
        row.issue_number = payload.issue_number.strip()
    if payload.variant_description is not None:
        row.variant_description = payload.variant_description.strip()
    if payload.priority is not None:
        row.priority = _validate_priority(payload.priority)
    if payload.status is not None:
        row.status = _validate_status(payload.status)
    if payload.notes is not None:
        row.notes = payload.notes.strip()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _item_to_read(row)


def remove_want_item(session: Session, *, owner_user_id: int, item_id: int) -> None:
    row = _get_item_row(session, owner_user_id=owner_user_id, item_id=item_id)
    session.delete(row)
    session.commit()
