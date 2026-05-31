from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

GradeBeforeSellAction = Literal["GRADE_BEFORE_SELL", "SELL_RAW", "HOLD_FOR_REVIEW"]


class GradeBeforeSellRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    inventory_item_id: int
    recommendation: GradeBeforeSellAction
    current_estimated_value: float
    expected_graded_value: float
    estimated_grading_cost: float
    expected_value_gain: float
    expected_roi: float
    confidence_score: float
    rationale: str
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""


class GradeBeforeSellRecommendationListRead(BaseModel):
    items: list[GradeBeforeSellRecommendationRead]
    total_items: int
    limit: int
    offset: int


class GradeBeforeSellSummaryRead(BaseModel):
    total_recommendations: int
    grade_before_sell_count: int
    sell_raw_count: int
    hold_for_review_count: int
    average_expected_roi: float
    total_expected_value_gain: float
