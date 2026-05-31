from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.pull_list import (
    PullListCreate,
    PullListDetailRead,
    PullListIssueAttachRequest,
    PullListListResponse,
    PullListUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.pull_list import (
    attach_release_to_pull_list,
    create_pull_list,
    get_pull_list,
    list_pull_lists,
    update_pull_list,
)

pull_list_v1_router = APIRouter(prefix="/api/v1", tags=["Pull Lists API v1 (P52-01)"])


def attach_pull_list_layer(app: FastAPI) -> None:
    app.include_router(pull_list_v1_router)


@pull_list_v1_router.get("/pull-lists", response_model=ScanApiV1Envelope)
def v1_list_pull_lists(
    status: str | None = None,
    publisher: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_pull_lists(
        session,
        owner_user_id=int(current_user.id),
        status=status,
        publisher=publisher,
        search=search,
        limit=limit,
        offset=offset,
    )
    body = PullListListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@pull_list_v1_router.post("/pull-lists", response_model=ScanApiV1Envelope)
def v1_create_pull_list(
    payload: PullListCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_pull_list(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@pull_list_v1_router.get("/pull-lists/{pull_list_id}", response_model=ScanApiV1Envelope)
def v1_get_pull_list(
    pull_list_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_pull_list(session, owner_user_id=int(current_user.id), pull_list_id=pull_list_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@pull_list_v1_router.patch("/pull-lists/{pull_list_id}", response_model=ScanApiV1Envelope)
def v1_update_pull_list(
    pull_list_id: int,
    payload: PullListUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = update_pull_list(
            session,
            owner_user_id=int(current_user.id),
            pull_list_id=pull_list_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@pull_list_v1_router.post("/pull-lists/{pull_list_id}/issues", response_model=ScanApiV1Envelope)
def v1_attach_pull_list_issue(
    pull_list_id: int,
    payload: PullListIssueAttachRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = attach_release_to_pull_list(
            session,
            owner_user_id=int(current_user.id),
            pull_list_id=pull_list_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))
