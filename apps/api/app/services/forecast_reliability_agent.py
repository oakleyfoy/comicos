from __future__ import annotations

from collections import defaultdict
from math import sqrt

from sqlmodel import Session, select

from app.models.forecast_validation import (
    ForecastDriftEvent,
    ForecastValidation,
    ForecastValidationExecution,
    SignalQualityMetric,
    utc_now,
)
from app.models.market_forecast import MarketForecast
from app.models.market_intelligence import MarketSignal
from app.schemas.forecast_validation import (
    ForecastDriftEventRead,
    ForecastReliabilityRunResponse,
    ForecastValidationExecutionRead,
    SignalQualityMetricRead,
)

AGENT_CODE = "forecast_reliability_agent"


def _execution_read(row: ForecastValidationExecution) -> ForecastValidationExecutionRead:
    return ForecastValidationExecutionRead.model_validate(row)


def _drift_read(row: ForecastDriftEvent) -> ForecastDriftEventRead:
    return ForecastDriftEventRead.model_validate(row)


def _signal_quality_read(row: SignalQualityMetric) -> SignalQualityMetricRead:
    return SignalQualityMetricRead.model_validate(row)


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


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    return sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def detect_forecast_drift(session: Session, *, owner_user_id: int) -> list[ForecastDriftEvent]:
    forecasts = session.exec(
        select(MarketForecast)
        .where(MarketForecast.owner_user_id == owner_user_id)
        .where(MarketForecast.asset_id.is_not(None))
        .order_by(MarketForecast.created_at.asc(), MarketForecast.id.asc())
    ).all()
    by_asset_horizon: dict[tuple[str, int, int], list[MarketForecast]] = defaultdict(list)
    for forecast in forecasts:
        if forecast.asset_id is None:
            continue
        by_asset_horizon[(forecast.forecast_type, int(forecast.asset_id), forecast.forecast_horizon_days)].append(forecast)
    created: list[ForecastDriftEvent] = []
    for (forecast_type, _asset_id, _horizon), rows in by_asset_horizon.items():
        if len(rows) < 2:
            continue
        values = [float(row.forecast_value) for row in rows[-3:]]
        latest_delta = abs(values[-1] - values[-2])
        drift_score = round(min(latest_delta / max(abs(values[-2]), 1.0), 1.0), 4)
        if drift_score < 0.2:
            continue
        row = ForecastDriftEvent(
            owner_user_id=owner_user_id,
            forecast_type=forecast_type,
            drift_type="FORECAST_DRIFT",
            drift_score=drift_score,
            detected_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def detect_signal_instability(session: Session, *, owner_user_id: int) -> list[ForecastDriftEvent]:
    signals = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .where(MarketSignal.asset_id.is_not(None))
        .order_by(MarketSignal.observed_at.asc(), MarketSignal.id.asc())
    ).all()
    by_type: dict[str, list[float]] = defaultdict(list)
    for signal in signals:
        by_type[signal.signal_type].append(float(signal.signal_value))
    created: list[ForecastDriftEvent] = []
    for signal_type, values in sorted(by_type.items()):
        drift_score = round(min(_stddev(values) / max(abs(sum(values) / len(values)), 1.0), 1.0), 4) if values else 0.0
        if drift_score < 0.25:
            continue
        row = ForecastDriftEvent(
            owner_user_id=owner_user_id,
            forecast_type=signal_type,
            drift_type="SIGNAL_INSTABILITY",
            drift_score=drift_score,
            detected_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def detect_confidence_failures(session: Session, *, owner_user_id: int) -> list[ForecastDriftEvent]:
    validations = session.exec(
        select(ForecastValidation)
        .where(ForecastValidation.owner_user_id == owner_user_id)
        .order_by(ForecastValidation.validated_at.desc(), ForecastValidation.id.desc())
    ).all()
    forecasts = {int(row.id or 0): row for row in session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all()}
    created: list[ForecastDriftEvent] = []
    for validation in validations:
        forecast = forecasts.get(validation.forecast_id)
        if forecast is None:
            continue
        if float(forecast.confidence_score) < 0.75 or abs(float(validation.variance_percent)) < 20.0:
            continue
        row = ForecastDriftEvent(
            owner_user_id=owner_user_id,
            forecast_type=forecast.forecast_type,
            drift_type="CONFIDENCE_FAILURE",
            drift_score=round(min(abs(float(validation.variance_percent)) / 100.0, 1.0), 4),
            detected_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def measure_signal_quality(session: Session, *, owner_user_id: int) -> list[SignalQualityMetric]:
    signals = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .order_by(MarketSignal.observed_at.desc(), MarketSignal.id.desc())
    ).all()
    grouped: dict[tuple[str, str], list[MarketSignal]] = defaultdict(list)
    for signal in signals:
        grouped[(signal.signal_type, signal.signal_source)].append(signal)

    created: list[SignalQualityMetric] = []
    for (signal_type, signal_source), rows in sorted(grouped.items()):
        completeness_score = round(sum(1.0 for row in rows if row.asset_type and row.asset_id is not None) / len(rows), 4)
        values = [float(row.signal_value) for row in rows]
        consistency_score = round(max(0.0, 1.0 - min(_stddev(values) / max(abs(sum(values) / len(values)), 1.0), 1.0)), 4) if values else 0.0
        quality_score = round((completeness_score * 0.4) + (consistency_score * 0.4) + (sum(float(row.confidence_score) for row in rows) / len(rows) * 0.2), 4)
        row = SignalQualityMetric(
            owner_user_id=owner_user_id,
            signal_type=signal_type,
            signal_source=signal_source,
            quality_score=quality_score,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            measured_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def run_forecast_reliability_agent(session: Session, *, owner_user_id: int) -> ForecastReliabilityRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        drift_events = [
            *detect_forecast_drift(session, owner_user_id=owner_user_id),
            *detect_signal_instability(session, owner_user_id=owner_user_id),
            *detect_confidence_failures(session, owner_user_id=owner_user_id),
        ]
        signal_quality = measure_signal_quality(session, owner_user_id=owner_user_id)
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return ForecastReliabilityRunResponse(
            execution=_execution_read(execution),
            drift_events=[_drift_read(row) for row in drift_events],
            signal_quality=[_signal_quality_read(row) for row in signal_quality],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
