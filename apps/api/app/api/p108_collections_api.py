"""P108 collection clone + reset API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings
from app.db.session import get_session
from app.models import User
from app.models.p108_collection import UserDataCollection
from app.schemas.p108_collection import (
    CollectionActiveRequest,
    CollectionCloneRequest,
    CollectionCreateRequest,
    CollectionListResponse,
    CollectionRead,
    CollectionResetRequest,
    CollectionStats,
)
from app.services.collection_context import resolve_active_collection
from app.services.ops_access import is_ops_admin_user
from app.services.p108_collection_service import (
    clone_collection,
    collection_stats,
    create_collection,
    list_collections_for_user,
    reset_collection,
    set_active_collection,
    set_default_collection,
    soft_delete_collection,
)

logger = logging.getLogger(__name__)

p108_collections_router = APIRouter(prefix="/api/collections", tags=["collections"])


def _read(session: Session, row: UserDataCollection) -> CollectionRead:
    stats_row = collection_stats(session, collection_id=int(row.id or 0))
    return CollectionRead(
        id=int(row.id or 0),
        name=row.name,
        collection_type=row.collection_type,
        is_default=row.is_default,
        source_collection_id=row.source_collection_id,
        source_snapshot_at=row.source_snapshot_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        stats=CollectionStats(**stats_row),
    )


@p108_collections_router.get("", response_model=CollectionListResponse)
def list_collections(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionListResponse:
    assert current_user.id is not None
    try:
        resolve_active_collection(session, current_user)
        session.commit()
        session.refresh(current_user)
        rows = list_collections_for_user(session, user_id=int(current_user.id))
    except (OperationalError, ProgrammingError) as exc:
        logger.exception("collections list failed user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Collections are not available yet. Run database migrations (P108) and try again.",
        ) from exc
    return CollectionListResponse(
        active_collection_id=current_user.active_collection_id,
        items=[_read(session, row) for row in rows],
    )


@p108_collections_router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def post_collection(
    body: CollectionCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    assert current_user.id is not None
    row = create_collection(
        session,
        user_id=int(current_user.id),
        name=body.name,
        collection_type=body.collection_type,
    )
    session.commit()
    session.refresh(row)
    return _read(session, row)


@p108_collections_router.post("/{collection_id}/clone", response_model=CollectionRead)
def post_clone_collection(
    collection_id: int,
    body: CollectionCloneRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    assert current_user.id is not None
    row = clone_collection(
        session,
        user_id=int(current_user.id),
        source_collection_id=collection_id,
        name=body.name,
        collection_type=body.collection_type,
    )
    session.commit()
    session.refresh(row)
    return _read(session, row)


@p108_collections_router.post("/{collection_id}/set-default", response_model=CollectionRead)
def post_set_default_collection(
    collection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    assert current_user.id is not None
    row = set_default_collection(session, user_id=int(current_user.id), collection_id=collection_id)
    session.commit()
    session.refresh(row)
    return _read(session, row)


@p108_collections_router.post("/active", response_model=CollectionRead)
def post_set_active_collection(
    body: CollectionActiveRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    row = set_active_collection(session, user=current_user, collection_id=body.collection_id)
    session.commit()
    session.refresh(row)
    session.refresh(current_user)
    return _read(session, row)


@p108_collections_router.post("/{collection_id}/reset", response_model=CollectionRead)
def post_reset_collection(
    collection_id: int,
    body: CollectionResetRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    assert current_user.id is not None
    allow_real = body.admin_override and is_ops_admin_user(current_user, Settings())
    row = reset_collection(
        session,
        user_id=int(current_user.id),
        collection_id=collection_id,
        allow_real=allow_real,
    )
    session.commit()
    session.refresh(row)
    return _read(session, row)


@p108_collections_router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    assert current_user.id is not None
    soft_delete_collection(session, user_id=int(current_user.id), collection_id=collection_id)
    session.commit()


def attach_p108_collections_layer(app) -> None:
    app.include_router(p108_collections_router)
