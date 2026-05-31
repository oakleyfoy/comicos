from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.schemas.want_list import (
    WantListCreate,
    WantListItemCreate,
    WantListItemDeleteResponse,
    WantListItemUpdate,
    WantListUpdate,
)
from app.services.want_lists import (
    WantListItemNotFoundError,
    WantListNotFoundError,
    add_want_item,
    create_want_list,
    get_want_list,
    get_want_lists,
    remove_want_item,
    update_want_item,
    update_want_list,
)

want_list_v1_router = APIRouter(prefix="/api/v1", tags=["Want Lists API v1 (P55-01)"])


def attach_want_list_layer(app: FastAPI) -> None:
    app.include_router(want_list_v1_router)


@want_list_v1_router.get("/want-lists", response_model=ScanApiV1Envelope)
def v1_get_want_lists(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_want_lists(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@want_list_v1_router.post("/want-lists", response_model=ScanApiV1Envelope)
def v1_create_want_list(
    payload: WantListCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_want_list(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@want_list_v1_router.get("/want-lists/{want_list_id}", response_model=ScanApiV1Envelope)
def v1_get_want_list(
    want_list_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_want_list(session, owner_user_id=int(current_user.id), want_list_id=want_list_id)
    except WantListNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@want_list_v1_router.patch("/want-lists/{want_list_id}", response_model=ScanApiV1Envelope)
def v1_patch_want_list(
    want_list_id: int,
    payload: WantListUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = update_want_list(
            session,
            owner_user_id=int(current_user.id),
            want_list_id=want_list_id,
            payload=payload,
        )
    except WantListNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@want_list_v1_router.post("/want-lists/{want_list_id}/items", response_model=ScanApiV1Envelope)
def v1_add_want_item(
    want_list_id: int,
    payload: WantListItemCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = add_want_item(
            session,
            owner_user_id=int(current_user.id),
            want_list_id=want_list_id,
            payload=payload,
        )
    except WantListNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@want_list_v1_router.patch("/want-list-items/{item_id}", response_model=ScanApiV1Envelope)
def v1_patch_want_item(
    item_id: int,
    payload: WantListItemUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = update_want_item(
            session,
            owner_user_id=int(current_user.id),
            item_id=item_id,
            payload=payload,
        )
    except WantListItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@want_list_v1_router.delete("/want-list-items/{item_id}", response_model=ScanApiV1Envelope)
def v1_delete_want_item(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        remove_want_item(session, owner_user_id=int(current_user.id), item_id=item_id)
    except WantListItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(
        WantListItemDeleteResponse(deleted=True, id=item_id),
        owner_user_id=int(current_user.id),
    )
