"""Resolve active user data collection (P108)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import User
from app.models.p108_collection import (
    COLLECTION_TYPE_REAL,
    DEFAULT_REAL_COLLECTION_NAME,
    UserDataCollection,
    utc_now,
)


class CollectionAccessError(HTTPException):
    def __init__(self, detail: str, *, status_code: int = status.HTTP_403_FORBIDDEN) -> None:
        super().__init__(status_code=status_code, detail=detail)


def get_collection_for_user(
    session: Session,
    *,
    user_id: int,
    collection_id: int,
) -> UserDataCollection:
    row = session.get(UserDataCollection, int(collection_id))
    if row is None or row.deleted_at is not None or int(row.owner_user_id) != int(user_id):
        raise CollectionAccessError("Collection not found or access denied.", status_code=status.HTTP_404_NOT_FOUND)
    return row


def ensure_default_real_collection(session: Session, *, user_id: int) -> UserDataCollection:
    existing = session.scalars(
        select(UserDataCollection)
        .where(UserDataCollection.owner_user_id == user_id)
        .where(UserDataCollection.deleted_at.is_(None))
        .where(UserDataCollection.is_default.is_(True))
        .order_by(UserDataCollection.id.asc())
    ).first()
    if existing is not None:
        return existing
    now = utc_now()
    row = UserDataCollection(
        owner_user_id=user_id,
        name=DEFAULT_REAL_COLLECTION_NAME,
        collection_type=COLLECTION_TYPE_REAL,
        is_default=True,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    user = session.get(User, user_id)
    if user is not None:
        user.active_collection_id = int(row.id or 0)
        session.add(user)
    return row


def resolve_active_collection(session: Session, user: User) -> UserDataCollection:
    assert user.id is not None
    if user.active_collection_id is not None:
        row = session.get(UserDataCollection, int(user.active_collection_id))
        if row is not None and row.deleted_at is None and int(row.owner_user_id) == int(user.id):
            return row
    default_row = ensure_default_real_collection(session, user_id=int(user.id))
    user.active_collection_id = int(default_row.id or 0)
    session.add(user)
    session.flush()
    return default_row


def require_active_collection_id(session: Session, user: User) -> int:
    row = resolve_active_collection(session, user)
    assert row.id is not None
    return int(row.id)


def require_active_collection_id_for_user(session: Session, user_id: int) -> int:
    user = session.get(User, user_id)
    if user is None:
        raise CollectionAccessError("User not found.", status_code=status.HTTP_404_NOT_FOUND)
    return require_active_collection_id(session, user)


def assert_resource_in_active_collection(
    session: Session,
    *,
    user: User,
    collection_id: int | None,
) -> None:
    active_id = require_active_collection_id(session, user)
    if collection_id is None or int(collection_id) != active_id:
        raise CollectionAccessError("Resource is not in the active collection.")
