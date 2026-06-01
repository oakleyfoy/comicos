from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.spec_input import SpecInputListRead
from app.services.spec_inputs import (
    build_spec_input_summary,
    get_latest_spec_inputs_read,
    list_spec_inputs,
    refresh_latest_spec_inputs,
)

spec_inputs_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Spec Inputs API v1 (P60-01)"],
)


def attach_spec_inputs_layer(app: FastAPI) -> None:
    app.include_router(spec_inputs_v1_router)


@spec_inputs_v1_router.get("/spec-inputs", response_model=ScanApiV1Envelope)
def v1_list_spec_inputs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_spec_inputs(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = SpecInputListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_inputs_v1_router.get("/spec-inputs/latest", response_model=ScanApiV1Envelope)
def v1_latest_spec_inputs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_spec_inputs_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_inputs_v1_router.post("/spec-inputs/refresh", response_model=ScanApiV1Envelope)
def v1_refresh_spec_inputs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = refresh_latest_spec_inputs(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_inputs_v1_router.get("/spec-inputs/summary", response_model=ScanApiV1Envelope)
def v1_spec_input_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_spec_input_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
