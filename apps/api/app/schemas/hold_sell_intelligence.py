from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

HoldSellAction = Literal["HOLD", "WATCH", "SELL"]


class HoldSellRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    inventory_item_id: int
    recommendation: HoldSellAction
    conviction_score: float
    confidence_score: float
    estimated_fmv: float
    acquisition_cost: float
    unrealized_gain: float
    rationale: str
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""


class HoldSellRecommendationListRead(BaseModel):
    items: list[HoldSellRecommendationRead]
    total_items: int
    limit: int
    offset: int


class HoldSellSummaryRead(BaseModel):
    total_recommendations: int
    hold_count: int
    watch_count: int
    sell_count: int
    average_conviction: float
    total_unrealized_gain: float
