from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AcquisitionDashboardSection = Literal[
    "TOP_COLLECTION_GAPS",
    "TOP_WANT_LIST_ITEMS",
    "TOP_OPPORTUNITIES",
    "MARKETPLACE_CANDIDATES",
    "BELOW_TARGET_PRICE",
    "REVIEW_REQUIRED",
]


class AcquisitionDashboardSummaryRead(BaseModel):
    total_want_list_items: int = 0
    critical_want_list_items: int = 0
    open_collection_gaps: int = 0
    high_priority_opportunities: int = 0
    buy_candidates: int = 0
    watch_candidates: int = 0
    pass_candidates: int = 0
    below_target_candidates: int = 0
    review_required_candidates: int = 0


class AcquisitionDashboardItemRead(BaseModel):
    section: AcquisitionDashboardSection
    item_type: str
    item_id: int
    publisher: str
    series_name: str
    issue_number: str
    title: str
    priority_label: str | None = None
    priority_score: float | None = None
    recommendation: str | None = None
    confidence_score: float | None = None
    total_price: float | None = None
    target_price: float | None = None
    source_type: str | None = None
    rationale: str = ""
    created_at: str


class AcquisitionDashboardRead(BaseModel):
    summary: AcquisitionDashboardSummaryRead
    top_collection_gaps: list[AcquisitionDashboardItemRead] = Field(default_factory=list)
    top_want_list_items: list[AcquisitionDashboardItemRead] = Field(default_factory=list)
    top_opportunities: list[AcquisitionDashboardItemRead] = Field(default_factory=list)
    marketplace_candidates: list[AcquisitionDashboardItemRead] = Field(default_factory=list)
    below_target_price: list[AcquisitionDashboardItemRead] = Field(default_factory=list)
    review_required: list[AcquisitionDashboardItemRead] = Field(default_factory=list)


class AcquisitionDashboardActionsRead(BaseModel):
    urgent_acquisition_actions: list[AcquisitionDashboardItemRead] = Field(default_factory=list)
