"""P81-01 discovery feed and opportunity schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

OpportunityType = Literal[
    "NEW_SERIES",
    "NEW_1",
    "MILESTONE",
    "ANNIVERSARY",
    "CREATOR_PROJECT",
    "VARIANT_EXPANSION",
]
ScoreCategory = Literal["MUST_WATCH", "HIGH_OPPORTUNITY", "WATCH", "LOW_PRIORITY"]
RegistryStatus = Literal["DISCOVERED", "QUALIFIED", "SCORED", "PUBLISHED"]


class P81DiscoveryOpportunityRead(BaseModel):
    id: int
    opportunity_type: OpportunityType
    registry_status: RegistryStatus
    title: str
    summary: str = ""
    publisher: str
    series_name: str
    issue_number: str
    variant_label: str = ""
    discovery_date: date
    release_date: date | None = None
    discovery_score: float
    score_category: ScoreCategory
    signals: list[str] = Field(default_factory=list)
    creator_metadata: dict = Field(default_factory=dict)
    source_type: str
    release_issue_id: int | None = None
    external_catalog_issue_id: int | None = None
    created_at: datetime
    updated_at: datetime


class P81DiscoveryOpportunityListResponse(BaseModel):
    items: list[P81DiscoveryOpportunityRead]
    total_items: int
    limit: int
    offset: int


class P81DiscoveryFeedRead(BaseModel):
    new_discoveries: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    top_opportunities: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    new_number_ones: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    milestone_issues: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    creator_projects: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    new_variants: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    snapshot_id: int | None = None


class P81DiscoveryDashboardRead(BaseModel):
    must_watch: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    high_opportunity: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    watch: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    recently_added: list[P81DiscoveryOpportunityRead] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    snapshot_id: int | None = None
