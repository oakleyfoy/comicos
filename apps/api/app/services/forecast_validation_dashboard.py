from __future__ import annotations

from sqlmodel import Session, select

from app.models.forecast_validation import (
    ForecastAccuracyMetric,
    ForecastDriftEvent,
    ForecastOutcome,
    ForecastValidation,
    ForecastValidationExecution,
    SignalQualityMetric,
)
from app.schemas.forecast_validation import (
    ForecastAccuracyMetricListResponse,
    ForecastAccuracyMetricRead,
    ForecastDriftEventListResponse,
    ForecastDriftEventRead,
    ForecastOutcomeListResponse,
    ForecastOutcomeRead,
    ForecastValidationDashboardRead,
    ForecastValidationDashboardSummaryRead,
    ForecastValidationExecutionListResponse,
    ForecastValidationExecutionRead,
    SignalQualityMetricListResponse,
    SignalQualityMetricRead,
)


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _accuracy_read(row: ForecastAccuracyMetric) -> ForecastAccuracyMetricRead:
    return ForecastAccuracyMetricRead.model_validate(row)


def _drift_read(row: ForecastDriftEvent) -> ForecastDriftEventRead:
    return ForecastDriftEventRead.model_validate(row)


def _signal_quality_read(row: SignalQualityMetric) -> SignalQualityMetricRead:
    return SignalQualityMetricRead.model_validate(row)


def _outcome_read(row: ForecastOutcome) -> ForecastOutcomeRead:
    return ForecastOutcomeRead.model_validate(row)


def _execution_read(row: ForecastValidationExecution) -> ForecastValidationExecutionRead:
    return ForecastValidationExecutionRead.model_validate(row)


def list_accuracy_metrics(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> ForecastAccuracyMetricListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ForecastAccuracyMetric)
        .where(ForecastAccuracyMetric.owner_user_id == owner_user_id)
        .order_by(ForecastAccuracyMetric.metric_date.desc(), ForecastAccuracyMetric.created_at.desc(), ForecastAccuracyMetric.id.desc())
    ).all()
    items = [_accuracy_read(row) for row in rows[offset : offset + limit]]
    return ForecastAccuracyMetricListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_drift_events(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> ForecastDriftEventListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ForecastDriftEvent)
        .where(ForecastDriftEvent.owner_user_id == owner_user_id)
        .order_by(ForecastDriftEvent.detected_at.desc(), ForecastDriftEvent.id.desc())
    ).all()
    items = [_drift_read(row) for row in rows[offset : offset + limit]]
    return ForecastDriftEventListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_signal_quality_metrics(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> SignalQualityMetricListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(SignalQualityMetric)
        .where(SignalQualityMetric.owner_user_id == owner_user_id)
        .order_by(SignalQualityMetric.measured_at.desc(), SignalQualityMetric.id.desc())
    ).all()
    items = [_signal_quality_read(row) for row in rows[offset : offset + limit]]
    return SignalQualityMetricListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_outcomes(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> ForecastOutcomeListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ForecastOutcome)
        .where(ForecastOutcome.owner_user_id == owner_user_id)
        .order_by(ForecastOutcome.created_at.desc(), ForecastOutcome.id.desc())
    ).all()
    items = [_outcome_read(row) for row in rows[offset : offset + limit]]
    return ForecastOutcomeListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_validation_executions(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> ForecastValidationExecutionListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ForecastValidationExecution)
        .where(ForecastValidationExecution.owner_user_id == owner_user_id)
        .order_by(ForecastValidationExecution.created_at.desc(), ForecastValidationExecution.id.desc())
    ).all()
    items = [_execution_read(row) for row in rows[offset : offset + limit]]
    return ForecastValidationExecutionListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def build_learning_trends(session: Session, *, owner_user_id: int) -> dict[str, float]:
    outcomes = session.exec(select(ForecastOutcome).where(ForecastOutcome.owner_user_id == owner_user_id)).all()
    forecast_scores = [float(row.outcome_score) for row in outcomes if row.forecast_id is not None]
    recommendation_scores = [float(row.outcome_score) for row in outcomes if row.recommendation_id is not None]
    return {
        "forecast_outcome_average": round(sum(forecast_scores) / len(forecast_scores), 4) if forecast_scores else 0.0,
        "recommendation_outcome_average": round(sum(recommendation_scores) / len(recommendation_scores), 4) if recommendation_scores else 0.0,
    }


def build_validation_summary(session: Session, *, owner_user_id: int) -> ForecastValidationDashboardSummaryRead:
    validations = session.exec(select(ForecastValidation).where(ForecastValidation.owner_user_id == owner_user_id)).all()
    accuracy = session.exec(select(ForecastAccuracyMetric).where(ForecastAccuracyMetric.owner_user_id == owner_user_id)).all()
    drift = session.exec(select(ForecastDriftEvent).where(ForecastDriftEvent.owner_user_id == owner_user_id)).all()
    signal_quality = session.exec(select(SignalQualityMetric).where(SignalQualityMetric.owner_user_id == owner_user_id)).all()
    outcomes = session.exec(select(ForecastOutcome).where(ForecastOutcome.owner_user_id == owner_user_id)).all()
    average_accuracy = round(sum(float(row.average_accuracy) for row in accuracy) / len(accuracy), 4) if accuracy else 0.0
    return ForecastValidationDashboardSummaryRead(
        total_validations=len(validations),
        average_accuracy=average_accuracy,
        total_drift_events=len(drift),
        total_signal_quality_metrics=len(signal_quality),
        total_outcomes=len(outcomes),
    )


def build_forecast_validation_dashboard(session: Session, *, owner_user_id: int) -> ForecastValidationDashboardRead:
    accuracy = list_accuracy_metrics(session, owner_user_id=owner_user_id, limit=10, offset=0)
    drift = list_drift_events(session, owner_user_id=owner_user_id, limit=10, offset=0)
    signal_quality = list_signal_quality_metrics(session, owner_user_id=owner_user_id, limit=10, offset=0)
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=10, offset=0)
    executions = list_validation_executions(session, owner_user_id=owner_user_id, limit=10, offset=0)
    return ForecastValidationDashboardRead(
        summary=build_validation_summary(session, owner_user_id=owner_user_id),
        accuracy=accuracy.items,
        drift=drift.items,
        signal_quality=signal_quality.items,
        outcomes=outcomes.items,
        agent_activity=executions.items,
        learning_trends=build_learning_trends(session, owner_user_id=owner_user_id),
    )
