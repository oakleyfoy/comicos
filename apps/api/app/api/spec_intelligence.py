from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.spec_intelligence import (
    SpecAgentExecutionListResponse,
    SpecRecommendationListResponse,
    SpecRecommendationReviewRequest,
    SpecRecommendationRunResponse,
    SpecScoreListResponse,
    SpecScoringRunResponse,
    WeeklyBuyListListResponse,
    WeeklyBuyListRunResponse,
)
from app.services.spec_dashboard import build_spec_dashboard
from app.services.spec_intelligence import list_executions_for_owner
from app.services.spec_recommendation_agent import list_recommendations_for_owner, run_spec_recommendations
from app.services.spec_review import mark_accepted, mark_dismissed, mark_reviewed
from app.services.spec_scoring_agent import list_scores_for_owner, run_spec_scoring
from app.services.weekly_buy_list_agent import list_weekly_buy_lists_for_owner, run_weekly_buy_list

spec_intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Spec Intelligence API v1 (P50-03)"])


def attach_spec_intelligence_layer(app: FastAPI) -> None:
    app.include_router(spec_intelligence_v1_router)


@spec_intelligence_v1_router.get("/spec-intelligence/scores", response_model=ScanApiV1Envelope)
def v1_spec_scores(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_scores_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = SpecScoreListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.get("/spec-intelligence/recommendations", response_model=ScanApiV1Envelope)
def v1_spec_recommendations(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_recommendations_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = SpecRecommendationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.get("/spec-intelligence/weekly-buy-lists", response_model=ScanApiV1Envelope)
def v1_weekly_buy_lists(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_weekly_buy_lists_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = WeeklyBuyListListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.get("/spec-intelligence/executions", response_model=ScanApiV1Envelope)
def v1_spec_executions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_executions_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    from app.schemas.spec_intelligence import SpecAgentExecutionRead

    body = SpecAgentExecutionListResponse(
        items=[SpecAgentExecutionRead.model_validate(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.get("/spec-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_spec_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_spec_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.post("/spec-intelligence/run/scoring", response_model=ScanApiV1Envelope)
def v1_run_spec_scoring(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    scores, execution = run_spec_scoring(session, owner_user_id=int(current_user.id))
    body = SpecScoringRunResponse(scores=scores, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.post("/spec-intelligence/run/recommendations", response_model=ScanApiV1Envelope)
def v1_run_spec_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    recommendations, execution = run_spec_recommendations(session, owner_user_id=int(current_user.id))
    body = SpecRecommendationRunResponse(recommendations=recommendations, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.post("/spec-intelligence/run/weekly-buy-list", response_model=ScanApiV1Envelope)
def v1_run_weekly_buy_list(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    weekly_buy_list, execution = run_weekly_buy_list(session, owner_user_id=int(current_user.id))
    body = WeeklyBuyListRunResponse(weekly_buy_list=weekly_buy_list, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.post("/spec-intelligence/recommendations/{recommendation_id}/reviewed", response_model=ScanApiV1Envelope)
def v1_spec_reviewed(
    recommendation_id: int,
    payload: SpecRecommendationReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = mark_reviewed(
            session,
            owner_user_id=int(current_user.id),
            recommendation_id=recommendation_id,
            review_notes=payload.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.post("/spec-intelligence/recommendations/{recommendation_id}/accepted", response_model=ScanApiV1Envelope)
def v1_spec_accepted(
    recommendation_id: int,
    payload: SpecRecommendationReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = mark_accepted(
            session,
            owner_user_id=int(current_user.id),
            recommendation_id=recommendation_id,
            review_notes=payload.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_intelligence_v1_router.post("/spec-intelligence/recommendations/{recommendation_id}/dismissed", response_model=ScanApiV1Envelope)
def v1_spec_dismissed(
    recommendation_id: int,
    payload: SpecRecommendationReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = mark_dismissed(
            session,
            owner_user_id=int(current_user.id),
            recommendation_id=recommendation_id,
            review_notes=payload.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))
