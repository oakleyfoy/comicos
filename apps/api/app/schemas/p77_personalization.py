"""P77-02 personalized recommendation and quantity schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BudgetState = Literal["GREEN", "YELLOW", "RED"]


class P77PersonalizationAdjustmentRead(BaseModel):
    label: str
    delta: float


class P77PersonalizedRecommendationRead(BaseModel):
    source: str
    title: str
    subtitle: str = ""
    global_score: float
    collector_adjustment: float
    personalized_score: float
    budget_impact: float = 0.0
    goal_alignment: float = 0.0
    quantity_recommendation: int = 0
    reasons: list[str] = Field(default_factory=list)
    adjustments: list[P77PersonalizationAdjustmentRead] = Field(default_factory=list)


class P77PersonalizedRecommendationListResponse(BaseModel):
    items: list[P77PersonalizedRecommendationRead]
    total_items: int
    limit: int
    offset: int
    estimated_spend: float = 0.0
    budget_filtered_count: int = 0


class P77PersonalizedQuantityRead(BaseModel):
    release_id: int | None = None
    title: str
    series_name: str = ""
    publisher: str = ""
    global_quantity: int = 0
    personalized_quantity: int = 0
    global_score: float = 0.0
    personalized_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class P77PersonalizedQuantityListResponse(BaseModel):
    items: list[P77PersonalizedQuantityRead]
    total_items: int
    limit: int
    offset: int


class P77BudgetStatusRead(BaseModel):
    monthly_budget: float
    monthly_spend: float
    remaining_budget: float
    projected_spend: float
    utilization_percent: float
    budget_state: BudgetState


class P77PersonalizationSnapshotRead(BaseModel):
    global_score: float | None = None
    collector_adjustment: float = 0.0
    personalized_score: float | None = None
    budget_impact: float = 0.0
    goal_alignment: float = 0.0
    quantity_recommendation: int = 0
    budget_state: BudgetState = "GREEN"
    reasons: list[str] = Field(default_factory=list)


class P77PersonalizedDashboardRead(BaseModel):
    budget_status: P77BudgetStatusRead
    top_recommendations: list[P77PersonalizedRecommendationRead] = Field(default_factory=list)
    quantity_highlights: list[P77PersonalizedQuantityRead] = Field(default_factory=list)
    profile_summary: dict[str, str | int | float] = Field(default_factory=dict)
