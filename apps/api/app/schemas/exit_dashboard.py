from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel, Field

ExitDashboardSection = str

SECTION_TOP_SELL = "TOP_SELL_RECOMMENDATIONS"
SECTION_TOP_GRADE = "TOP_GRADE_BEFORE_SELL"
SECTION_TOP_REBALANCE = "TOP_REBALANCE_ACTIONS"
SECTION_CAPITAL = "CAPITAL_RECOVERY"
SECTION_REVIEW = "REVIEW_REQUIRED"


class ExitDashboardSummaryRead(BaseModel):
    total_exit_candidates: int = 0
    sell_recommendations: int = 0
    watch_recommendations: int = 0
    hold_recommendations: int = 0
    grade_before_sell_recommendations: int = 0
    sell_raw_recommendations: int = 0
    rebalance_actions: int = 0
    estimated_capital_recovery: float = 0.0
    review_required_count: int = 0


class ExitDashboardItemRead(BaseModel):
    section: str
    item_type: str
    item_id: int
    inventory_item_id: int | None = None
    publisher: str = ""
    series_name: str = ""
    issue_number: str = ""
    title: str = ""
    recommendation: str | None = None
    action: str | None = None
    priority_score: float | None = None
    confidence_score: float | None = None
    capital_value: float | None = None
    rationale: str = ""
    created_at: str = ""


class ExitDashboardRead(BaseModel):
    summary: ExitDashboardSummaryRead
    top_sell_recommendations: list[ExitDashboardItemRead] = Field(default_factory=list)
    top_grade_before_sell: list[ExitDashboardItemRead] = Field(default_factory=list)
    top_rebalance_actions: list[ExitDashboardItemRead] = Field(default_factory=list)
    capital_recovery: list[ExitDashboardItemRead] = Field(default_factory=list)
    review_required: list[ExitDashboardItemRead] = Field(default_factory=list)


class ExitDashboardActionsRead(BaseModel):
    priority_exit_actions: list[ExitDashboardItemRead] = Field(default_factory=list)
