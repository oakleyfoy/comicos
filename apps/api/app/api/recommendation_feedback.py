"""P73 recommendation feedback API (P73-01 outcomes, P73-02 analytics, P73-03 intelligence)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_analytics import P73RecommendationCategoryListResponse
from app.schemas.recommendation_feedback_intelligence import P73CategoryCalibrationListResponse
from app.schemas.recommendation_feedback import P73RecommendationFeedbackDashboardRead
from app.schemas.recommendation_outcome import (
    P73RecommendationOutcomeCreatePayload,
    P73RecommendationOutcomeDetailRead,
    P73RecommendationOutcomeListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.recommendation_analytics_service import (
    build_recommendation_analytics,
    build_recommendation_categories,
    build_recommendation_performance,
    build_recommendation_performance_dashboard,
    build_recommendation_profitability,
)
from app.services.recommendation_feedback_certification import run_recommendation_feedback_certification
from app.services.recommendation_feedback_engine import (
    build_category_calibration,
    build_recommendation_effectiveness,
    load_grading_context,
    load_market_context,
    run_recommendation_feedback_engine,
)
from app.services.recommendation_analytics_service import (
    _accuracy_metrics,
    _load_owner_data,
    build_category_performance_read,
)
from app.services.recommendation_confidence_service import build_recommendation_confidence
from app.services.recommendation_outcome_service import (
    append_event,
    build_feedback_dashboard,
    create_outcome,
    get_outcome_detail,
    list_outcomes,
)

recommendation_feedback_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Recommendation Feedback API v1 (P73-01)"],
)


def attach_recommendation_feedback_layer(app: FastAPI) -> None:
    app.include_router(recommendation_feedback_v1_router)


@recommendation_feedback_v1_router.get("/recommendation-feedback/outcomes", response_model=ScanApiV1Envelope)
def v1_list_recommendation_outcomes(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_outcomes(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.post("/recommendation-feedback/outcomes", response_model=ScanApiV1Envelope)
def v1_create_recommendation_outcome(
    payload: P73RecommendationOutcomeCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_outcome(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/outcomes/{outcome_id}", response_model=ScanApiV1Envelope)
def v1_get_recommendation_outcome(
    outcome_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_outcome_detail(session, owner_user_id=int(current_user.id), outcome_id=outcome_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.post(
    "/recommendation-feedback/outcomes/{outcome_id}/event",
    response_model=ScanApiV1Envelope,
)
def v1_append_recommendation_event(
    outcome_id: int,
    payload: P73RecommendationEventCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = append_event(
        session,
        owner_user_id=int(current_user.id),
        outcome_id=outcome_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/summary", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_feedback_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/analytics", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_recommendation_analytics(session, owner_user_id=int(current_user.id), persist=True)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/performance", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_recommendation_performance(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/profitability", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_profitability(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_recommendation_profitability(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/categories", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_categories(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = build_recommendation_categories(session, owner_user_id=int(current_user.id))
    body = P73RecommendationCategoryListResponse(items=items, total_items=len(items), limit=100, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get(
    "/recommendation-feedback/performance-dashboard",
    response_model=ScanApiV1Envelope,
)
def v1_recommendation_feedback_performance_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_recommendation_performance_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/confidence", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_confidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    outcomes, _ = _load_owner_data(session, owner_id)
    category_rows = build_category_performance_read(outcomes)
    body = build_recommendation_confidence(
        outcomes=outcomes,
        category_rows=category_rows,
        market=load_market_context(session, owner_user_id=owner_id),
        grading=load_grading_context(session, owner_user_id=owner_id),
    )
    return wrap_object(body, owner_user_id=owner_id)


@recommendation_feedback_v1_router.get("/recommendation-feedback/calibration", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_calibration(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    outcomes, _ = _load_owner_data(session, owner_id)
    items = build_category_calibration(outcomes)
    body = P73CategoryCalibrationListResponse(items=items, total_items=len(items), limit=100, offset=0)
    return wrap_standard_list(body, owner_user_id=owner_id)


@recommendation_feedback_v1_router.get("/recommendation-feedback/effectiveness", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_effectiveness(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    outcomes, events = _load_owner_data(session, owner_id)
    accuracy = _accuracy_metrics(outcomes, events)
    body = build_recommendation_effectiveness(outcomes, accuracy)
    return wrap_object(body, owner_user_id=owner_id)


@recommendation_feedback_v1_router.get("/recommendation-feedback/certification", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_recommendation_feedback_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_feedback_v1_router.get("/recommendation-feedback/dashboard", response_model=ScanApiV1Envelope)
def v1_recommendation_feedback_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_recommendation_feedback_engine(session, owner_user_id=int(current_user.id), persist=True)
    return wrap_object(body, owner_user_id=int(current_user.id))
