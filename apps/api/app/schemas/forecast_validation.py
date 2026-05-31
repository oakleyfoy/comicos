from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ForecastValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    validation_uuid: str
    forecast_id: int
    validation_type: str
    predicted_value: float
    actual_value: float
    variance_value: float
    variance_percent: float
    validated_at: datetime


class ForecastAccuracyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    metric_date: date
    forecast_type: str
    forecast_horizon_days: int
    total_forecasts: int
    average_error: float
    average_accuracy: float
    created_at: datetime


class ForecastDriftEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    event_uuid: str
    forecast_type: str
    drift_type: str
    drift_score: float
    detected_at: datetime


class SignalQualityMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    signal_type: str
    signal_source: str
    quality_score: float
    completeness_score: float
    consistency_score: float
    measured_at: datetime


class ForecastOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    outcome_uuid: str
    recommendation_id: int | None = None
    forecast_id: int | None = None
    outcome_type: str
    outcome_score: float
    created_at: datetime


class ForecastValidationExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime


class ForecastValidationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastValidationRead]
    total_items: int
    limit: int
    offset: int


class ForecastAccuracyMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastAccuracyMetricRead]
    total_items: int
    limit: int
    offset: int


class ForecastDriftEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastDriftEventRead]
    total_items: int
    limit: int
    offset: int


class SignalQualityMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SignalQualityMetricRead]
    total_items: int
    limit: int
    offset: int


class ForecastOutcomeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastOutcomeRead]
    total_items: int
    limit: int
    offset: int


class ForecastValidationExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastValidationExecutionRead]
    total_items: int
    limit: int
    offset: int


class ForecastValidationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ForecastValidationExecutionRead
    validations: list[ForecastValidationRead] = Field(default_factory=list)
    accuracy_metrics: list[ForecastAccuracyMetricRead] = Field(default_factory=list)


class ForecastLearningRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ForecastValidationExecutionRead
    outcomes: list[ForecastOutcomeRead] = Field(default_factory=list)


class ForecastReliabilityRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ForecastValidationExecutionRead
    drift_events: list[ForecastDriftEventRead] = Field(default_factory=list)
    signal_quality: list[SignalQualityMetricRead] = Field(default_factory=list)


class ForecastValidationDashboardSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_validations: int
    average_accuracy: float
    total_drift_events: int
    total_signal_quality_metrics: int
    total_outcomes: int


class ForecastValidationDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: ForecastValidationDashboardSummaryRead
    accuracy: list[ForecastAccuracyMetricRead] = Field(default_factory=list)
    drift: list[ForecastDriftEventRead] = Field(default_factory=list)
    signal_quality: list[SignalQualityMetricRead] = Field(default_factory=list)
    outcomes: list[ForecastOutcomeRead] = Field(default_factory=list)
    agent_activity: list[ForecastValidationExecutionRead] = Field(default_factory=list)
    learning_trends: dict[str, float] = Field(default_factory=dict)
