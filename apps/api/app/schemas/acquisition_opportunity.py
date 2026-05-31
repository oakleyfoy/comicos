from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AcquisitionSourceType = Literal["COLLECTION_GAP", "WANT_LIST", "MANUAL"]
AcquisitionOpportunityType = Literal[
    "COLLECTION_GAP",
    "WANT_LIST_ITEM",
    "KEY_TARGET",
    "MILESTONE_TARGET",
    "RUN_COMPLETION_TARGET",
]


class AcquisitionOpportunityRead(BaseModel):
    id: int
    owner_id: int
    source_type: AcquisitionSourceType
    source_reference_id: int | None
    publisher: str
    series_name: str
    issue_number: str
    variant_description: str | None
    opportunity_type: AcquisitionOpportunityType
    priority_score: float
    confidence_score: float
    estimated_fmv: float | None
    target_price: float | None
    value_gap: float | None
    rationale: str
    created_at: str


class AcquisitionOpportunitySummaryRead(BaseModel):
    total_opportunities: int
    average_priority_score: float = 0.0
    average_confidence_score: float = 0.0
    by_opportunity_type: dict[str, int] = Field(default_factory=dict)
    with_target_price: int = 0


class AcquisitionOpportunityListRead(BaseModel):
    items: list[AcquisitionOpportunityRead]
    total_items: int
    limit: int
    offset: int
