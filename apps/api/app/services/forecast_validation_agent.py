from __future__ import annotations

from collections import defaultdict
from datetime import timezone

from sqlmodel import Session, select

from app.models.forecast_validation import ForecastAccuracyMetric, ForecastValidation, ForecastValidationExecution, utc_now
from app.models.market_forecast import MarketForecast
from app.models.market_intelligence import MarketSignal
from app.schemas.forecast_validation import (
    ForecastAccuracyMetricRead,
    ForecastValidationExecutionRead,
    ForecastValidationRead,
    ForecastValidationRunResponse,
)

AGENT_CODE = "forecast_validation_agent"


def _execution_read(row: ForecastValidationExecution) -> ForecastValidationExecutionRead:
    return ForecastValidationExecutionRead.model_validate(row)


def _validation_read(row: ForecastValidation) -> ForecastValidationRead:
    return ForecastValidationRead.model_validate(row)


def _accuracy_read(row: ForecastAccuracyMetric) -> ForecastAccuracyMetricRead:
    return ForecastAccuracyMetricRead.model_validate(row)


def _start_execution(session: Session, *, owner_user_id: int) -> ForecastValidationExecution:
    row = ForecastValidationExecution(
        owner_user_id=owner_user_id,
        agent_code=AGENT_CODE,
        status="RUNNING",
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _finish_execution(session: Session, *, execution: ForecastValidationExecution, status: str) -> None:
    completed_at = utc_now()
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = max(int((completed_at - execution.started_at).total_seconds() * 1000), 0)
    session.add(execution)
    session.flush()


def calculate_variance(*, predicted_value: float, actual_value: float) -> tuple[float, float]:
    variance_value = round(actual_value - predicted_value, 4)
    baseline = abs(predicted_value) if abs(predicted_value) >= 0.0001 else 1.0
    variance_percent = round((variance_value / baseline) * 100.0, 4)
    return variance_value, variance_percent


def _accuracy_from_percent(variance_percent: float) -> float:
    return round(max(0.0, 1.0 - min(abs(variance_percent) / 100.0, 1.0)), 4)


def validate_forecasts(session: Session, *, owner_user_id: int) -> list[ForecastValidation]:
    forecasts = session.exec(
        select(MarketForecast)
        .where(MarketForecast.owner_user_id == owner_user_id)
        .where(MarketForecast.asset_id.is_not(None))
        .order_by(MarketForecast.created_at.asc(), MarketForecast.id.asc())
    ).all()
    created: list[ForecastValidation] = []
    for forecast in forecasts:
        if forecast.asset_id is None:
            continue
        signal = session.exec(
            select(MarketSignal)
            .where(MarketSignal.owner_user_id == owner_user_id)
            .where(MarketSignal.asset_type == forecast.asset_type)
            .where(MarketSignal.asset_id == forecast.asset_id)
            .where(MarketSignal.observed_at >= forecast.created_at.astimezone(timezone.utc))
            .order_by(MarketSignal.observed_at.desc(), MarketSignal.id.desc())
        ).first()
        if signal is None:
            continue
        variance_value, variance_percent = calculate_variance(
            predicted_value=float(forecast.forecast_value),
            actual_value=float(signal.signal_value),
        )
        row = ForecastValidation(
            owner_user_id=owner_user_id,
            forecast_id=int(forecast.id or 0),
            validation_type="ACTUAL_SIGNAL_COMPARISON",
            predicted_value=float(forecast.forecast_value),
            actual_value=float(signal.signal_value),
            variance_value=variance_value,
            variance_percent=variance_percent,
            validated_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def calculate_forecast_accuracy(session: Session, *, owner_user_id: int) -> list[ForecastAccuracyMetric]:
    validations = session.exec(
        select(ForecastValidation)
        .where(ForecastValidation.owner_user_id == owner_user_id)
        .order_by(ForecastValidation.validated_at.desc(), ForecastValidation.id.desc())
    ).all()
    if not validations:
        return []
    forecasts = {int(row.id or 0): row for row in session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all()}
    grouped: dict[tuple[str, int], list[ForecastValidation]] = defaultdict(list)
    for validation in validations:
        forecast = forecasts.get(validation.forecast_id)
        if forecast is None:
            continue
        grouped[(forecast.forecast_type, forecast.forecast_horizon_days)].append(validation)

    created: list[ForecastAccuracyMetric] = []
    metric_date = utc_now().date()
    for (forecast_type, horizon), rows in sorted(grouped.items()):
        average_error = round(sum(abs(float(row.variance_value)) for row in rows) / len(rows), 4)
        average_accuracy = round(sum(_accuracy_from_percent(float(row.variance_percent)) for row in rows) / len(rows), 4)
        metric = ForecastAccuracyMetric(
            owner_user_id=owner_user_id,
            metric_date=metric_date,
            forecast_type=forecast_type,
            forecast_horizon_days=horizon,
            total_forecasts=len(rows),
            average_error=average_error,
            average_accuracy=average_accuracy,
            created_at=utc_now(),
        )
        session.add(metric)
        created.append(metric)
    session.flush()
    return created


def calculate_accuracy_metrics(session: Session, *, owner_user_id: int) -> list[ForecastAccuracyMetric]:
    return calculate_forecast_accuracy(session, owner_user_id=owner_user_id)


def run_forecast_validation_agent(session: Session, *, owner_user_id: int) -> ForecastValidationRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        validations = validate_forecasts(session, owner_user_id=owner_user_id)
        accuracy_metrics = calculate_accuracy_metrics(session, owner_user_id=owner_user_id)
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return ForecastValidationRunResponse(
            execution=_execution_read(execution),
            validations=[_validation_read(row) for row in validations],
            accuracy_metrics=[_accuracy_read(row) for row in accuracy_metrics],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
