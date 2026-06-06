"""P73-01 recommendation outcome schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation_event import P73RecommendationTimelineEntryRead


class P73RecommendationOutcomeCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(..., min_length=1, max_length=128)
    inventory_copy_id: int | None = Field(default=None, ge=1)
    series: str = Field(default="", max_length=256)
    issue: str = Field(default="", max_length=32)
    variant: str = Field(default="", max_length=128)
    publisher: str = Field(default="", max_length=128)
    character: str = Field(default="", max_length=128)
    creator: str = Field(default="", max_length=128)
    expected_profit: Decimal | None = None
    actual_profit: Decimal | None = None
    expected_roi_pct: Decimal | None = None
    actual_roi_pct: Decimal | None = None
    recommendation_type: str = Field(..., min_length=1, max_length=32)
    recommendation_category: str = Field(default="GENERAL", max_length=32)
    created_date: date | None = None
    source_table: str | None = Field(default=None, max_length=64)
    source_row_id: int | None = None
    notes: str | None = Field(default=None, max_length=8000)


class P73RecommendationOutcomeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    recommendation_id: str
    inventory_copy_id: int | None
    series: str
    issue: str
    variant: str
    publisher: str
    character: str
    creator: str
    expected_profit: Decimal | None
    actual_profit: Decimal | None
    expected_roi_pct: Decimal | None
    actual_roi_pct: Decimal | None
    recommendation_type: str
    recommendation_category: str
    created_date: date
    current_status: str
    attribution_outcome: str | None
    attribution_accurate: bool | None
    source_table: str | None
    source_row_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class P73RecommendationOutcomeDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: P73RecommendationOutcomeRead
    timeline: list[P73RecommendationTimelineEntryRead] = Field(default_factory=list)


class P73RecommendationOutcomeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P73RecommendationOutcomeRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0
