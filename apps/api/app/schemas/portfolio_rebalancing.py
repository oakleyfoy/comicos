from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

RebalanceType = Literal[
    "TITLE_OVEREXPOSURE",
    "PUBLISHER_OVEREXPOSURE",
    "CHARACTER_OVEREXPOSURE",
    "MODERN_SPEC_OVEREXPOSURE",
    "DUPLICATE_CAPITAL",
    "LOW_EFFICIENCY_CAPITAL",
]

RebalanceAction = Literal["REDUCE_EXPOSURE", "REVIEW_POSITION", "HOLD"]


class PortfolioRebalanceRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    rebalance_type: RebalanceType
    target_key: str
    target_label: str
    exposure_value: float
    exposure_percent: float
    recommended_action: RebalanceAction
    priority_score: float
    confidence_score: float
    rationale: str
    created_at: str
    publisher: str = ""


class PortfolioRebalanceRecommendationListRead(BaseModel):
    items: list[PortfolioRebalanceRecommendationRead]
    total_items: int
    limit: int
    offset: int


class PortfolioRebalanceSummaryRead(BaseModel):
    total_recommendations: int
    reduce_exposure_count: int
    review_position_count: int
    hold_count: int
    average_priority_score: float
    total_exposure_value: float
