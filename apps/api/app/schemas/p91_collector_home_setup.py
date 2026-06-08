"""P91-03 first-time collector home setup checklist."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class P91CollectorHomeSetupStatusRead(BaseModel):
    imported_first_order: bool = False
    has_any_import: bool = False
    has_unmatched_imports: bool = False
    imports_review_complete: bool = False
    has_inventory: bool = False
    has_pull_list: bool = False
    recommendations_viewed: bool = False
    has_budget: bool = False
    completed_count: int = Field(ge=0, le=99)
    total_count: int = Field(default=6, ge=1, le=99)
    percent_complete: int = Field(default=0, ge=0, le=100)
    checklist_dismissed: bool = False
    checklist_dismissed_at: datetime | None = None
    can_dismiss_checklist: bool = False


class P91CollectorHomeSetupDismissRead(BaseModel):
    checklist_dismissed: bool
    checklist_dismissed_at: datetime | None = None
    completed_count: int
    can_dismiss_checklist: bool


class P91RecommendationsViewedRead(BaseModel):
    recommendations_viewed: bool
    recommendations_first_viewed_at: datetime | None = None
