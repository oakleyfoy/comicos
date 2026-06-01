from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.spec_baseline_score import SpecBaselineScoreListRead
from app.services.spec_baseline_scores import (
    build_spec_baseline_summary,
    get_latest_spec_baseline_scores_read,
    list_spec_baseline_scores,
    refresh_latest_spec_baseline_scores,
)

spec_baseline_scores_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Spec Baseline Scores API v1 (P60-02)"],
)


def attach_spec_baseline_scores_layer(app: FastAPI) -> None:
    app.include_router(spec_baseline_scores_v1_router)


@spec_baseline_scores_v1_router.get("/spec-baseline-scores", response_model=ScanApiV1Envelope)
def v1_list_spec_baseline_scores(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_spec_baseline_scores(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = SpecBaselineScoreListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_baseline_scores_v1_router.get("/spec-baseline-scores/latest", response_model=ScanApiV1Envelope)
def v1_latest_spec_baseline_scores(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_spec_baseline_scores_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_baseline_scores_v1_router.post("/spec-baseline-scores/refresh", response_model=ScanApiV1Envelope)
def v1_refresh_spec_baseline_scores(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = refresh_latest_spec_baseline_scores(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_baseline_scores_v1_router.get("/spec-baseline-scores/summary", response_model=ScanApiV1Envelope)
def v1_spec_baseline_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_spec_baseline_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
