from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.collection_gap import CollectionGapListRead, CollectionGapSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.collection_gaps import (
    build_collection_gap_summary,
    list_collection_gaps,
    refresh_and_list_latest_collection_gaps,
)

collection_gap_v1_router = APIRouter(prefix="/api/v1", tags=["Collection Gaps API v1 (P55-02)"])


def attach_collection_gap_layer(app: FastAPI) -> None:
    app.include_router(collection_gap_v1_router)


@collection_gap_v1_router.get("/collection-gaps", response_model=ScanApiV1Envelope)
def v1_list_collection_gaps(
    priority: str | None = None,
    gap_type: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_collection_gaps(
        session,
        owner_user_id=int(current_user.id),
        priority=priority,
        gap_type=gap_type,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = CollectionGapListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@collection_gap_v1_router.get("/collection-gaps/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_collection_gaps(
    priority: str | None = None,
    gap_type: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_collection_gaps(
        session,
        owner_user_id=int(current_user.id),
        priority=priority,
        gap_type=gap_type,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = CollectionGapListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@collection_gap_v1_router.get("/collection-gaps/summary", response_model=ScanApiV1Envelope)
def v1_collection_gap_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_collection_gap_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
