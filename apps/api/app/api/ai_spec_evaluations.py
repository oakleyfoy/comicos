from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.ai_spec_evaluation import AISpecEvaluationListRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ai_spec_evaluations import (
    build_ai_spec_evaluation_summary,
    list_ai_spec_evaluations,
    refresh_latest_ai_spec_evaluations,
)

ai_spec_evaluations_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["AI Spec Evaluations API v1 (P60-03)"],
)


def attach_ai_spec_evaluations_layer(app: FastAPI) -> None:
    app.include_router(ai_spec_evaluations_v1_router)


@ai_spec_evaluations_v1_router.get("/ai-spec-evaluations", response_model=ScanApiV1Envelope)
def v1_list_ai_spec_evaluations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_ai_spec_evaluations(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = AISpecEvaluationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@ai_spec_evaluations_v1_router.get("/ai-spec-evaluations/latest", response_model=ScanApiV1Envelope)
def v1_latest_ai_spec_evaluations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = refresh_latest_ai_spec_evaluations(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@ai_spec_evaluations_v1_router.get("/ai-spec-evaluations/summary", response_model=ScanApiV1Envelope)
def v1_ai_spec_evaluation_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_ai_spec_evaluation_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
