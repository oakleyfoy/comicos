"""P89-01 Sell Candidate API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

P89Recommendation = Literal["SELL_NOW", "HOLD", "GRADE_FIRST", "MONITOR"]
P89Confidence = Literal["HIGH", "MEDIUM", "LOW"]


class P89SellCandidateRead(BaseModel):
    id: int
    owner_user_id: int
    inventory_copy_id: int
    recommendation: P89Recommendation
    sell_score: float
    hold_score: float
    grade_first_score: float
    monitor_score: float
    confidence: P89Confidence
    estimated_sale_value: float
    estimated_profit: float
    reason_summary: str
    reasons: list[str] = Field(default_factory=list)
    status: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""
    cover_image_url: str = ""
    is_top_opportunity: bool = False
    quick_sale_price: float | None = None
    market_price: float | None = None
    premium_price: float | None = None
    pricing_confidence: str | None = None
    sales_velocity: str | None = None
    sales_velocity_label: str | None = None
    created_at: datetime
    updated_at: datetime


class P89SellCandidateListRead(BaseModel):
    items: list[P89SellCandidateRead]
    total_items: int
    limit: int
    offset: int


class P89SellCandidateSummaryRead(BaseModel):
    total_candidates: int
    sell_now_count: int
    hold_count: int
    grade_first_count: int
    monitor_count: int
    total_estimated_profit: float
    total_estimated_sale_value: float
    top_opportunity: P89SellCandidateRead | None = None


class P89SellCandidateGenerateResponse(BaseModel):
    created_count: int
    updated_count: int = 0
    candidates: int = 0
