from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p72_grading_analytics import (
    P72GradingOutcomeListResponse,
)
from app.schemas.p72_grading_operations import (
    P72GradingBatchAssignPayload,
    P72GradingBatchCreatePayload,
    P72GradingBatchListResponse,
    P72GradingBatchRead,
    P72GradingQueueEnqueuePayload,
    P72GradingQueueEnqueueResponse,
    P72GradingQueueListResponse,
    P72GradingQueueStatusPayload,
)
from app.schemas.grading_intelligence import (
    GradePredictionListResponse,
    GradePredictionRunResponse,
    GradingAgentExecutionListResponse,
    GradingAgentExecutionRead,
    GradingDashboardRead,
    GradingIntelligenceRunRequest,
    GradingPrioritiesRunResponse,
    P72GradingCandidatesListResponse,
    GradingRecommendationListResponse,
    GradingRecommendationRead,
    GradingRecommendationsRunResponse,
    GradingReviewRequest,
    GradingReviewResponse,
    GradingRoiListResponse,
    GradingRoiRunResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.grade_prediction_agent import run_grade_prediction_agent
from app.services.grading_dashboard import (
    build_grading_dashboard,
    get_prediction_detail,
    get_recommendation_detail,
    list_predictions_for_owner,
    list_recommendations_for_owner,
    list_roi_for_owner,
)
from app.services.grading_intelligence import list_executions_for_owner
from app.services.grading_recommendation_agent import run_grading_recommendation_agent
from app.services.grading_review import mark_accepted, mark_dismissed, mark_reviewed
from app.services.grading_intelligence_roi import run_grading_roi_agent
from app.services.p72_grading_decision_dashboard import (
    get_p72_decision_for_copy,
    list_p72_decision_candidates,
)
from app.services.grading_queue_service import enqueue_queue_entries, list_queue_entries, update_queue_status
from app.services.grading_submission_batch import assign_entries_to_batch, create_batch, list_batches
from app.services.grading_intelligence_certification import run_grading_intelligence_certification
from app.services.p72_grading_analytics_service import (
    build_analytics_dashboard,
    build_performance_analytics,
    build_roi_analytics,
    list_outcome_reads,
)
from app.services.submission_priority_agent import run_submission_priority_agent

grading_intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Grading Intelligence API v1 (P49-02)"])


def attach_grading_intelligence_layer(app: FastAPI) -> None:
    app.include_router(grading_intelligence_v1_router)


@grading_intelligence_v1_router.get("/grading-intelligence/predictions", response_model=ScanApiV1Envelope)
def v1_grading_predictions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_predictions_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GradePredictionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/predictions/{prediction_id}", response_model=ScanApiV1Envelope)
def v1_grading_prediction_detail(
    prediction_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    detail = get_prediction_detail(session, prediction_id=prediction_id, owner_user_id=int(current_user.id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Grade prediction not found.")
    return wrap_object(detail, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/recommendations", response_model=ScanApiV1Envelope)
def v1_grading_recommendations(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_recommendations_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GradingRecommendationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/recommendations/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_grading_recommendation_detail(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    detail = get_recommendation_detail(session, recommendation_id=recommendation_id, owner_user_id=int(current_user.id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Grading recommendation not found.")
    return wrap_object(detail, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/roi", response_model=ScanApiV1Envelope)
def v1_grading_roi(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_roi_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GradingRoiListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/executions", response_model=ScanApiV1Envelope)
def v1_grading_executions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_executions_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [GradingAgentExecutionRead.model_validate(row) for row in rows]
    body = GradingAgentExecutionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/queue", response_model=ScanApiV1Envelope)
def v1_p72_grading_queue(
    status: str | None = None,
    batch_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_queue_entries(
        session,
        owner_user_id=int(current_user.id),
        status=status,
        batch_id=batch_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/queue/enqueue", response_model=ScanApiV1Envelope)
def v1_p72_grading_queue_enqueue(
    payload: P72GradingQueueEnqueuePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = enqueue_queue_entries(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
        created_by_user_id=int(current_user.id),
    )
    body = P72GradingQueueEnqueueResponse(items=items, count=len(items))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/batches", response_model=ScanApiV1Envelope)
def v1_p72_grading_batches(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_batches(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/batches", response_model=ScanApiV1Envelope)
def v1_p72_create_grading_batch(
    payload: P72GradingBatchCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_batch(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
        created_by_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post(
    "/grading-intelligence/batches/{batch_id}/assign",
    response_model=ScanApiV1Envelope,
)
def v1_p72_assign_batch(
    batch_id: int,
    payload: P72GradingBatchAssignPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = assign_entries_to_batch(
        session,
        owner_user_id=int(current_user.id),
        batch_id=batch_id,
        payload=payload,
        created_by_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post(
    "/grading-intelligence/queue/{queue_entry_id}/status",
    response_model=ScanApiV1Envelope,
)
def v1_p72_queue_status(
    queue_entry_id: int,
    payload: P72GradingQueueStatusPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_queue_status(
        session,
        owner_user_id=int(current_user.id),
        queue_entry_id=queue_entry_id,
        payload=payload,
        created_by_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/analytics", response_model=ScanApiV1Envelope)
def v1_p72_grading_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_analytics_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/performance", response_model=ScanApiV1Envelope)
def v1_p72_grading_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_performance_analytics(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/outcomes", response_model=ScanApiV1Envelope)
def v1_p72_grading_outcomes(
    limit: int = 100,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_outcome_reads(session, owner_user_id=int(current_user.id), limit=limit)
    body = P72GradingOutcomeListResponse(items=items, total_items=len(items), limit=limit)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/roi-analytics", response_model=ScanApiV1Envelope)
def v1_p72_grading_roi_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    """P72 measured ROI (P49 agent ROI list remains at GET /grading-intelligence/roi)."""
    assert current_user.id is not None
    body = build_roi_analytics(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/certification", response_model=ScanApiV1Envelope)
def v1_p72_grading_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_grading_intelligence_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/candidates", response_model=ScanApiV1Envelope)
def v1_p72_grading_candidates(
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_p72_decision_candidates(
        session, owner_user_id=int(current_user.id), limit=limit
    )
    body = P72GradingCandidatesListResponse(items=items, total_items=total, limit=limit)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get("/grading-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_grading_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_grading_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/run/predictions", response_model=ScanApiV1Envelope)
def v1_run_grade_predictions(
    payload: GradingIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.analysis_id is None:
        raise HTTPException(status_code=400, detail="analysis_id is required.")
    detail = run_grade_prediction_agent(session, owner_user_id=int(current_user.id), analysis_id=payload.analysis_id)
    body = GradePredictionRunResponse(prediction=detail)
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/run/recommendations", response_model=ScanApiV1Envelope)
def v1_run_grading_recommendations(
    payload: GradingIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.analysis_id is None:
        raise HTTPException(status_code=400, detail="analysis_id is required.")
    items = run_grading_recommendation_agent(session, owner_user_id=int(current_user.id), analysis_id=payload.analysis_id)
    body = GradingRecommendationsRunResponse(recommendations=items)
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/run/roi", response_model=ScanApiV1Envelope)
def v1_run_grading_roi(
    payload: GradingIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = run_grading_roi_agent(session, owner_user_id=int(current_user.id), analysis_id=payload.analysis_id)
    body = GradingRoiRunResponse(analyses=items)
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/run/priorities", response_model=ScanApiV1Envelope)
def v1_run_grading_priorities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = run_submission_priority_agent(session, owner_user_id=int(current_user.id))
    body = GradingPrioritiesRunResponse(candidates=items)
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/recommendations/{recommendation_id}/reviewed", response_model=ScanApiV1Envelope)
def v1_grading_recommendation_reviewed(
    recommendation_id: int,
    payload: GradingReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_reviewed(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=int(current_user.id),
        review_notes=payload.review_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/recommendations/{recommendation_id}/dismissed", response_model=ScanApiV1Envelope)
def v1_grading_recommendation_dismissed(
    recommendation_id: int,
    payload: GradingReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_dismissed(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=int(current_user.id),
        review_notes=payload.review_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.post("/grading-intelligence/recommendations/{recommendation_id}/accepted", response_model=ScanApiV1Envelope)
def v1_grading_recommendation_accepted(
    recommendation_id: int,
    payload: GradingReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_accepted(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=int(current_user.id),
        review_notes=payload.review_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_intelligence_v1_router.get(
    "/grading-intelligence/{inventory_copy_id}",
    response_model=ScanApiV1Envelope,
)
def v1_p72_grading_decision_detail(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    """P72-01 per-copy advisory decision (numeric inventory_copy_id only)."""
    assert current_user.id is not None
    detail = get_p72_decision_for_copy(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Grading decision not available for this copy.")
    return wrap_object(detail, owner_user_id=int(current_user.id))
