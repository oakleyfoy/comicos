from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PurchaseBudgetTier = Literal["PASS", "WATCH", "BUY", "STRONG_BUY", "MUST_BUY"]


class PurchaseBudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    monthly_budget: float
    weekly_budget: float
    is_active: bool
    created_at: str
    updated_at: str


class PurchaseBudgetUpdate(BaseModel):
    monthly_budget: float | None = Field(default=None, ge=0.0)
    weekly_budget: float | None = Field(default=None, ge=0.0)
    is_active: bool | None = None


class PurchaseBudgetAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    release_id: int
    recommendation_tier: PurchaseBudgetTier
    allocated_amount: float
    priority_rank: int
    rationale: str
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""
    series_name: str = ""


class PurchaseBudgetAllocationListRead(BaseModel):
    items: list[PurchaseBudgetAllocationRead]
    total_items: int
    limit: int
    offset: int


class PurchaseBudgetSummaryRead(BaseModel):
    total_budget: float
    weekly_budget: float
    allocated_budget: float
    remaining_budget: float
    allocation_percentage: float
    is_active: bool


class PurchaseBudgetGenerateResponse(BaseModel):
    created_count: int
