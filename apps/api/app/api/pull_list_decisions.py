from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.pull_list_decision import PullListDecisionListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.pull_list_decisions import (
    get_pull_list_decision,
    list_pull_list_decisions,
    list_upcoming_pull_list_decisions,
)

pull_list_decisions_v1_router = APIRouter(prefix="/api/v1", tags=["Pull List Decisions API v1 (P52-02)"])


def attach_pull_list_decisions_layer(app: FastAPI) -> None:
    app.include_router(pull_list_decisions_v1_router)


@pull_list_decisions_v1_router.get("/pull-list-decisions", response_model=ScanApiV1Envelope)
def v1_list_pull_list_decisions(
    decision_type: str | None = None,
    tier: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_pull_list_decisions(
        session,
        owner_user_id=int(current_user.id),
        decision_type=decision_type,
        tier=tier,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = PullListDecisionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@pull_list_decisions_v1_router.get("/pull-list-decisions/upcoming", response_model=ScanApiV1Envelope)
def v1_upcoming_pull_list_decisions(
    decision_type: str | None = None,
    tier: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_upcoming_pull_list_decisions(
        session,
        owner_user_id=int(current_user.id),
        decision_type=decision_type,
        tier=tier,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = PullListDecisionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@pull_list_decisions_v1_router.get("/pull-list-decisions/{decision_id}", response_model=ScanApiV1Envelope)
def v1_get_pull_list_decision(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_pull_list_decision(session, owner_user_id=int(current_user.id), decision_id=decision_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))
