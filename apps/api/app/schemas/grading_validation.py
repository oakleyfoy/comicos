from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class GradeValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    validation_uuid: str
    prediction_id: int
    actual_grade: str
    predicted_grade: str
    variance: float
    validated_at: datetime


class GradeCalibrationMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_date: date
    grading_scale: str
    total_predictions: int
    average_variance: float
    accuracy_score: float
    created_at: datetime


class GradePredictionOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    outcome_uuid: str
    recommendation_id: int | None
    prediction_id: int | None
    outcome_type: str
    outcome_score: float
    created_at: datetime


class GradingDriftEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_uuid: str
    drift_type: str
    drift_score: float
    detected_at: datetime


class GradingReliabilityMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_uuid: str
    reliability_type: str
    metric_score: float
    measured_at: datetime


class GradingValidationExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class ActualGradeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction_id: int
    actual_grade: str


class GradingValidationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_grades: list[ActualGradeInput] = Field(default_factory=list)


class GradeValidationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradeValidationRead]
    total_items: int
    limit: int
    offset: int


class GradeCalibrationMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradeCalibrationMetricRead]
    total_items: int
    limit: int
    offset: int


class GradingDriftEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingDriftEventRead]
    total_items: int
    limit: int
    offset: int


class GradingReliabilityMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingReliabilityMetricRead]
    total_items: int
    limit: int
    offset: int


class GradePredictionOutcomeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradePredictionOutcomeRead]
    total_items: int
    limit: int
    offset: int


class GradingValidationExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingValidationExecutionRead]
    total_items: int
    limit: int
    offset: int


class PredictionAccuracySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_count: int
    average_variance: float
    accuracy_score: float


class DriftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_count: int
    average_drift_score: float
    latest_drift_type: str | None


class GradingValidationDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction_accuracy: PredictionAccuracySummary
    calibration_metrics: list[GradeCalibrationMetricRead]
    drift_summary: DriftSummary
    reliability_metrics: list[GradingReliabilityMetricRead]
    recommendation_outcomes: list[GradePredictionOutcomeRead]
    agent_activity: list[GradingValidationExecutionRead]


class GradeValidationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validations: list[GradeValidationRead]
    calibration_metric: GradeCalibrationMetricRead | None
    execution: GradingValidationExecutionRead


class GradeCalibrationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[GradeCalibrationMetricRead]
    execution: GradingValidationExecutionRead


class GradingReliabilityRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drift_events: list[GradingDriftEventRead]
    reliability_metrics: list[GradingReliabilityMetricRead]
    execution: GradingValidationExecutionRead


class GradingOutcomesRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcomes: list[GradePredictionOutcomeRead]
    execution: GradingValidationExecutionRead
