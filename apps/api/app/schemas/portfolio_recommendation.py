"""P38-04 deterministic portfolio recommendation API shapes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


PortfolioRecommendationAction = Literal[
    "HOLD",
    "SELL",
    "REDUCE_EXPOSURE",
    "GRADE_THEN_SELL",
    "CONSOLIDATE",
    "WATCH",
]
PortfolioRecommendationStrength = Literal["WEAK", "MODERATE", "STRONG", "ELITE"]
PortfolioRecommendationConfidence = Literal["LOW", "MEDIUM", "HIGH"]
PortfolioRecommendationRisk = Literal["LOW", "MEDIUM", "HIGH"]
PortfolioRecommendationStatus = Literal["ACTIVE", "SUPERSEDED", "ARCHIVED"]
PortfolioRecommendationEvidenceType = Literal[
    "DUPLICATE_INTELLIGENCE",
    "PORTFOLIO_LIQUIDITY",
    "GRADING_RECOMMENDATION",
    "RISK_ENGINE",
    "LISTING_INTELLIGENCE",
    "SALES_LEDGER",
    "MARKET_SALE",
    "PORTFOLIO_EXPOSURE",
]
PortfolioRecommendationScenarioName = Literal["pessimistic", "baseline", "optimistic"]


class PortfolioRecommendationGeneratePayload(BaseModel):
    model_config = {"extra": "forbid"}

    portfolio_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class PortfolioRecommendationEvidenceRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    portfolio_recommendation_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class PortfolioRecommendationScenarioRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    portfolio_recommendation_id: int
    scenario_name: str
    projected_capital_release: Decimal | None
    projected_liquidity_gain: Decimal | None
    projected_portfolio_impact: Decimal | None
    created_at: datetime


class PortfolioRecommendationHistoryRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    owner_user_id: int
    inventory_item_id: int | None
    portfolio_id: int | None
    recommendation_action: str
    recommendation_strength: str
    confidence_level: str
    risk_level: str
    checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioRecommendationRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    owner_user_id: int
    inventory_item_id: int | None
    portfolio_id: int | None
    canonical_comic_issue_id: int | None
    recommendation_action: str
    recommendation_strength: str
    confidence_level: str
    risk_level: str
    estimated_liquidity_impact: Decimal | None
    estimated_capital_release: Decimal | None
    estimated_portfolio_efficiency_gain: Decimal | None
    expected_roi_if_graded: Decimal | None
    rationale_summary: str
    warning_flags_json: list[object]
    recommendation_status: str
    checksum: str
    replay_key: str | None
    snapshot_date: date
    created_at: datetime


class PortfolioRecommendationDetailRead(BaseModel):
    model_config = {"extra": "forbid"}

    recommendation: PortfolioRecommendationRead
    evidence: list[PortfolioRecommendationEvidenceRead]
    scenarios: list[PortfolioRecommendationScenarioRead]
    history: list[PortfolioRecommendationHistoryRead]


class PortfolioRecommendationListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[PortfolioRecommendationRead]
    total: int


class PortfolioRecommendationGenerateResponse(BaseModel):
    model_config = {"extra": "forbid"}

    replayed: bool
    items: list[PortfolioRecommendationRead]
    total: int
    history_appended_count: int


class PortfolioRecommendationEvidenceListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[PortfolioRecommendationEvidenceRead]
    total: int


class PortfolioRecommendationHistoryListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[PortfolioRecommendationHistoryRead]
    total: int


class InventoryPortfolioRecommendationTeaser(BaseModel):
    model_config = {"extra": "forbid"}

    recommendation_action: str
    recommendation_strength: str
    confidence_level: str
    risk_level: str
    rationale_summary: str
    estimated_capital_release: str | None = None
    estimated_liquidity_impact: str | None = None
    estimated_portfolio_efficiency_gain: str | None = None
    recommendation_status: str
    recommendation_checksum: str | None = None
