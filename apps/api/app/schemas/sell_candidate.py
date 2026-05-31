from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

SellCandidateAction = Literal["STRONG_SELL", "SELL", "HOLD", "REVIEW"]


class SellCandidateRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    inventory_item_id: int
    recommendation: SellCandidateAction
    confidence_score: float
    rationale: str
    estimated_fmv: float
    estimated_profit: float
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""
    variant: str = ""


class SellCandidateRecommendationListRead(BaseModel):
    items: list[SellCandidateRecommendationRead]
    total_items: int
    limit: int
    offset: int


class SellCandidateSummaryRead(BaseModel):
    total_candidates: int
    strong_sell_count: int
    sell_count: int
    hold_count: int
    review_count: int
    total_estimated_profit: float


class SellCandidateGenerateResponse(BaseModel):
    created_count: int
