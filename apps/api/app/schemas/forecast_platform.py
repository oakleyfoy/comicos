from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dealer_copilot import DealerRecommendationRead
from app.schemas.forecast_validation import (
    ForecastAccuracyMetricRead,
    ForecastDriftEventRead,
    ForecastOutcomeRead,
    SignalQualityMetricRead,
)
from app.schemas.market_forecast import MarketForecastRead, MarketRiskAssessmentRead


class ForecastPlatformValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object]


class ForecastPlatformValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    platform_certified: bool
    checks: list[ForecastPlatformValidationCheckRead]


class ForecastPlatformHealthComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_code: str
    title: str
    health_status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class ForecastPlatformHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    components: list[ForecastPlatformHealthComponentRead]


class ForecastPlatformSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_score: float
    forecast_count: int
    risk_count: int
    recommendation_count: int
    forecast_accuracy: float
    top_bullish_forecasts: list[MarketForecastRead] = Field(default_factory=list)
    top_bearish_forecasts: list[MarketForecastRead] = Field(default_factory=list)
    top_risks: list[MarketRiskAssessmentRead] = Field(default_factory=list)
    top_buy_recommendations: list[DealerRecommendationRead] = Field(default_factory=list)
    top_sell_recommendations: list[DealerRecommendationRead] = Field(default_factory=list)
    top_grade_candidates: list[DealerRecommendationRead] = Field(default_factory=list)
    accuracy_summary: list[ForecastAccuracyMetricRead] = Field(default_factory=list)
    signal_quality_summary: list[SignalQualityMetricRead] = Field(default_factory=list)
    recent_outcomes: list[ForecastOutcomeRead] = Field(default_factory=list)


class ForecastPlatformCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_certified: bool
    validation_status: str
    health_status: str
    summary: str
    certification_notes: list[str] = Field(default_factory=list)


class ForecastPlatformDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: ForecastPlatformSummaryRead
    health: ForecastPlatformHealthRead
    validation: ForecastPlatformValidationRead
    certification: ForecastPlatformCertificationRead
