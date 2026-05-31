from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketForecastRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    forecast_uuid: str
    forecast_type: str
    asset_type: str
    asset_id: int | None = None
    forecast_horizon_days: int
    forecast_value: float
    confidence_score: float
    created_at: datetime


class MarketForecastPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    forecast_id: int
    forecast_date: date
    projected_value: float
    confidence_score: float
    created_at: datetime


class MarketForecastConfidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    forecast_id: int
    confidence_score: float
    confidence_band: str
    explanation: str
    created_at: datetime


class MarketForecastDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast: MarketForecastRead
    points: list[MarketForecastPointRead] = Field(default_factory=list)
    confidence: MarketForecastConfidenceRead | None = None


class MarketRiskAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    assessment_uuid: str
    asset_type: str
    asset_id: int | None = None
    risk_type: str
    risk_score: float
    confidence_score: float
    created_at: datetime


class ForecastAgentExecutionRead(BaseModel):
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


class MarketForecastListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketForecastRead]
    total_items: int
    limit: int
    offset: int


class MarketForecastConfidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketForecastConfidenceRead]
    total_items: int
    limit: int
    offset: int


class MarketRiskAssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketRiskAssessmentRead]
    total_items: int
    limit: int
    offset: int


class ForecastAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastAgentExecutionRead]
    total_items: int
    limit: int
    offset: int


class MarketForecastRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ForecastAgentExecutionRead
    created_count: int
    forecasts: list[MarketForecastRead] = Field(default_factory=list)


class MarketRiskRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ForecastAgentExecutionRead
    created_count: int
    risks: list[MarketRiskAssessmentRead] = Field(default_factory=list)


class ForecastDashboardSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_forecasts: int
    average_confidence_score: float
    total_risk_assessments: int
    bullish_forecast_count: int
    bearish_forecast_count: int


class ForecastDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: ForecastDashboardSummaryRead
    forecast_confidence: list[MarketForecastConfidenceRead] = Field(default_factory=list)
    top_bullish_forecasts: list[MarketForecastRead] = Field(default_factory=list)
    top_bearish_forecasts: list[MarketForecastRead] = Field(default_factory=list)
    highest_risk_assets: list[MarketRiskAssessmentRead] = Field(default_factory=list)
    agent_activity: list[ForecastAgentExecutionRead] = Field(default_factory=list)
