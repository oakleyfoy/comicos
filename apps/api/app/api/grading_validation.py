from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.grading_validation import (
    GradeCalibrationMetricListResponse,
    GradeCalibrationRunResponse,
    GradePredictionOutcomeListResponse,
    GradingDriftEventListResponse,
    GradingOutcomesRunResponse,
    GradingReliabilityMetricListResponse,
    GradingReliabilityRunResponse,
    GradingValidationDashboardRead,
    GradingValidationExecutionListResponse,
    GradingValidationExecutionRead,
    GradingValidationRunRequest,
    GradeValidationRunResponse,
    GradeValidationListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.grade_validation_agent import list_validations_for_owner, validate_predictions
from app.services.grading_calibration_agent import calculate_calibration_metrics, list_calibration_metrics_for_owner
from app.services.grading_outcomes_agent import list_outcomes_for_owner, run_outcome_tracking
from app.services.grading_reliability_agent import (
    list_drift_events_for_owner,
    list_reliability_metrics_for_owner,
    run_reliability_monitoring,
)
from app.services.grading_validation import list_executions_for_owner
from app.services.grading_validation_dashboard import build_grading_validation_dashboard

grading_validation_v1_router = APIRouter(prefix="/api/v1", tags=["Grading Validation API v1 (P49-03)"])


def attach_grading_validation_layer(app: FastAPI) -> None:
    app.include_router(grading_validation_v1_router)


@grading_validation_v1_router.get("/grading-validation/dashboard", response_model=ScanApiV1Envelope)
def v1_grading_validation_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_grading_validation_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.get("/grading-validation/validations", response_model=ScanApiV1Envelope)
def v1_list_grade_validations(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_validations_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GradeValidationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.get("/grading-validation/calibration", response_model=ScanApiV1Envelope)
def v1_list_grade_calibration(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_calibration_metrics_for_owner(
        session, owner_user_id=int(current_user.id), limit=limit, offset=offset
    )
    body = GradeCalibrationMetricListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.get("/grading-validation/drift", response_model=ScanApiV1Envelope)
def v1_list_grading_drift(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_drift_events_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GradingDriftEventListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.get("/grading-validation/reliability", response_model=ScanApiV1Envelope)
def v1_list_grading_reliability(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_reliability_metrics_for_owner(
        session, owner_user_id=int(current_user.id), limit=limit, offset=offset
    )
    body = GradingReliabilityMetricListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.get("/grading-validation/outcomes", response_model=ScanApiV1Envelope)
def v1_list_grading_outcomes(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_outcomes_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GradePredictionOutcomeListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.get("/grading-validation/executions", response_model=ScanApiV1Envelope)
def v1_list_grading_validation_executions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_executions_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [GradingValidationExecutionRead.model_validate(row) for row in rows]
    body = GradingValidationExecutionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.post("/grading-validation/run/validation", response_model=ScanApiV1Envelope)
def v1_run_grade_validation(
    payload: GradingValidationRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    actual_grades = [(entry.prediction_id, entry.actual_grade) for entry in payload.actual_grades]
    validations, calibration, execution = validate_predictions(
        session, owner_user_id=int(current_user.id), actual_grades=actual_grades
    )
    body = GradeValidationRunResponse(validations=validations, calibration_metric=calibration, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.post("/grading-validation/run/calibration", response_model=ScanApiV1Envelope)
def v1_run_grading_calibration(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    metrics, execution = calculate_calibration_metrics(session, owner_user_id=int(current_user.id))
    body = GradeCalibrationRunResponse(metrics=metrics, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.post("/grading-validation/run/reliability", response_model=ScanApiV1Envelope)
def v1_run_grading_reliability(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    drift_events, reliability_metrics, execution = run_reliability_monitoring(
        session, owner_user_id=int(current_user.id)
    )
    body = GradingReliabilityRunResponse(
        drift_events=drift_events, reliability_metrics=reliability_metrics, execution=execution
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_validation_v1_router.post("/grading-validation/run/outcomes", response_model=ScanApiV1Envelope)
def v1_run_grading_outcomes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    outcomes, execution = run_outcome_tracking(session, owner_user_id=int(current_user.id))
    body = GradingOutcomesRunResponse(outcomes=outcomes, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))
