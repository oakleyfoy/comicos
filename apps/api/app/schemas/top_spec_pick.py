from __future__ import annotations

from pydantic import BaseModel, Field


class TopSpecPickRead(BaseModel):
    id: int
    owner_id: int
    rank: int
    release_id: int | None
    spec_input_id: int
    title: str
    publisher: str
    issue_number: str
    final_score: float
    confidence_score: float
    risk_level: str
    suggested_quantity: int | None
    foc_date: str | None
    release_date: str | None
    rationale: str
    created_at: str


class TopSpecPickListRead(BaseModel):
    items: list[TopSpecPickRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class TopSpecPickLatestRead(BaseModel):
    picks_computed: int = Field(default=0, ge=0)
    picks_skipped: bool = False
    items: list[TopSpecPickRead] = Field(default_factory=list)


class TopSpecPickSummaryRead(BaseModel):
    total_picks: int = Field(default=0, ge=0)
    average_final_score: float = Field(default=0.0, ge=0.0)
    average_confidence_score: float = Field(default=0.0, ge=0.0)
    low_risk_count: int = Field(default=0, ge=0)
    medium_risk_count: int = Field(default=0, ge=0)
    high_risk_count: int = Field(default=0, ge=0)
    with_suggested_quantity: int = Field(default=0, ge=0)
