from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PurchaseQuantityTier = Literal["PASS", "WATCH", "BUY", "STRONG_BUY", "MUST_BUY"]


class PurchaseQuantityRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    release_id: int
    recommendation_tier: PurchaseQuantityTier
    quantity_recommended: int
    confidence_score: float
    rationale: str
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""
    series_name: str = ""
    pull_list_decision: str | None = None


class PurchaseQuantityRecommendationCreate(BaseModel):
    release_id: int
    recommendation_tier: PurchaseQuantityTier
    quantity_recommended: int = Field(ge=0, le=5)
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class PurchaseQuantityListResponse(BaseModel):
    items: list[PurchaseQuantityRecommendationRead]
    total_items: int
    limit: int
    offset: int


class PurchaseQuantityGenerateResponse(BaseModel):
    created_count: int
