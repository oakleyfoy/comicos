from __future__ import annotations

from sqlmodel import Session

from app.schemas.grading_validation import (
    DriftSummary,
    GradeCalibrationMetricRead,
    GradePredictionOutcomeRead,
    GradingReliabilityMetricRead,
    GradingValidationDashboardRead,
    GradingValidationExecutionRead,
    PredictionAccuracySummary,
)
from app.services.grade_validation_agent import calculate_prediction_accuracy, list_validations_for_owner
from app.services.grading_calibration_agent import list_calibration_metrics_for_owner
from app.services.grading_outcomes_agent import list_outcomes_for_owner
from app.services.grading_reliability_agent import list_drift_events_for_owner, list_reliability_metrics_for_owner
from app.services.grading_validation import list_executions_for_owner


def build_grading_validation_dashboard(session: Session, *, owner_user_id: int) -> GradingValidationDashboardRead:
    validations, validation_count = list_validations_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    variances = [v.variance for v in validations]
    calibration, _ = list_calibration_metrics_for_owner(session, owner_user_id=owner_user_id, limit=10, offset=0)
    drift_events, drift_count = list_drift_events_for_owner(session, owner_user_id=owner_user_id, limit=50, offset=0)
    reliability, _ = list_reliability_metrics_for_owner(session, owner_user_id=owner_user_id, limit=10, offset=0)
    outcomes, _ = list_outcomes_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    exec_rows, _ = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)

    rec_outcomes = [o for o in outcomes if o.recommendation_id is not None][:10]

    drift_summary = DriftSummary(
        event_count=drift_count,
        average_drift_score=round(sum(e.drift_score for e in drift_events) / len(drift_events), 3)
        if drift_events
        else 0.0,
        latest_drift_type=drift_events[0].drift_type if drift_events else None,
    )

    return GradingValidationDashboardRead(
        prediction_accuracy=PredictionAccuracySummary(
            validation_count=validation_count,
            average_variance=round(sum(variances) / len(variances), 3) if variances else 0.0,
            accuracy_score=calculate_prediction_accuracy(variances=variances),
        ),
        calibration_metrics=calibration,
        drift_summary=drift_summary,
        reliability_metrics=reliability,
        recommendation_outcomes=rec_outcomes if rec_outcomes else outcomes[:10],
        agent_activity=[GradingValidationExecutionRead.model_validate(row) for row in exec_rows],
    )
