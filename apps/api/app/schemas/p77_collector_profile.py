"""P77-01 collector profile API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CollectorType = Literal["INVESTOR", "SPECULATOR", "COMPLETIONIST", "READER", "HYBRID"]
RiskProfile = Literal["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]
TimeHorizon = Literal["SHORT_TERM_FLIP", "MEDIUM_TERM", "LONG_TERM", "LEGACY_COLLECTION", "MIXED"]
GradingPreference = Literal["NEVER_GRADE", "OPPORTUNISTIC", "AGGRESSIVE"]
HoldPreference = Literal["FLIP", "MIXED", "LONG_TERM"]
BudgetPeriod = Literal["MONTHLY", "QUARTERLY"]
InterestType = Literal["PUBLISHER", "CHARACTER", "CREATOR"]
GoalType = Literal[
    "RUN_COMPLETION",
    "CHARACTER_COLLECTION",
    "PUBLISHER_FOCUS",
    "KEY_ISSUE_FOCUS",
    "GRADING_GOAL",
    "PORTFOLIO_GOAL",
]


class P77InterestItemRead(BaseModel):
    id: int
    interest_type: InterestType
    label: str
    priority_rank: int


class P77InterestItemWrite(BaseModel):
    interest_type: InterestType
    label: str = Field(min_length=1, max_length=120)
    priority_rank: int = Field(default=1, ge=1, le=99)


class P77CollectorProfileRead(BaseModel):
    owner_id: int
    collector_type: CollectorType
    risk_profile: RiskProfile
    time_horizon: TimeHorizon
    grading_preference: GradingPreference
    hold_preference: HoldPreference
    default_copy_count: int
    key_issue_copy_count: int
    ratio_variant_copy_count: int
    publishers: list[P77InterestItemRead] = Field(default_factory=list)
    characters: list[P77InterestItemRead] = Field(default_factory=list)
    creators: list[P77InterestItemRead] = Field(default_factory=list)
    updated_at: datetime


class P77CollectorProfileUpdate(BaseModel):
    collector_type: CollectorType | None = None
    risk_profile: RiskProfile | None = None
    time_horizon: TimeHorizon | None = None
    grading_preference: GradingPreference | None = None
    hold_preference: HoldPreference | None = None
    default_copy_count: int | None = Field(default=None, ge=0, le=99)
    key_issue_copy_count: int | None = Field(default=None, ge=0, le=99)
    ratio_variant_copy_count: int | None = Field(default=None, ge=0, le=99)
    publishers: list[P77InterestItemWrite] | None = None
    characters: list[P77InterestItemWrite] | None = None
    creators: list[P77InterestItemWrite] | None = None


class P77BudgetAllocationRead(BaseModel):
    name: str
    amount: float


class P77CollectorBudgetRead(BaseModel):
    owner_id: int
    monthly_budget: float
    budget_period: BudgetPeriod
    publisher_allocations: list[P77BudgetAllocationRead] = Field(default_factory=list)
    category_allocations: list[P77BudgetAllocationRead] = Field(default_factory=list)
    updated_at: datetime


class P77CollectorBudgetUpdate(BaseModel):
    monthly_budget: float | None = Field(default=None, ge=0)
    budget_period: BudgetPeriod | None = None
    publisher_allocations: list[P77BudgetAllocationRead] | None = None
    category_allocations: list[P77BudgetAllocationRead] | None = None


class P77CollectorGoalRead(BaseModel):
    id: int
    goal_type: GoalType
    title: str
    target_value: float
    progress_value: float
    completion_percent: float
    metadata: dict = Field(default_factory=dict)
    updated_at: datetime


class P77CollectorGoalCreate(BaseModel):
    goal_type: GoalType
    title: str = Field(min_length=1, max_length=200)
    target_value: float = Field(ge=0)
    progress_value: float = Field(default=0, ge=0)
    metadata: dict = Field(default_factory=dict)


class P77CollectorGoalUpdate(BaseModel):
    goal_type: GoalType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_value: float | None = Field(default=None, ge=0)
    progress_value: float | None = Field(default=None, ge=0)
    metadata: dict | None = None


class P77CollectorGoalListResponse(BaseModel):
    items: list[P77CollectorGoalRead]
    total_items: int
    limit: int
    offset: int


class P77CollectorProfileDashboardRead(BaseModel):
    profile: P77CollectorProfileRead
    budget: P77CollectorBudgetRead
    goals: list[P77CollectorGoalRead] = Field(default_factory=list)
    goals_summary: dict[str, float | int] = Field(default_factory=dict)
