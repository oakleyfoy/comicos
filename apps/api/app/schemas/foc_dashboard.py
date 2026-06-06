from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.pull_list_decision import PullListDecisionType

FocDashboardSection = Literal[
    "ACTION_REQUIRED",
    "UPCOMING_FOC",
    "UPCOMING_RELEASES",
    "MISSED_FOC",
    "WATCHLIST",
]

FocDateStatus = Literal["DUE_NOW", "THIS_WEEK", "NEXT_WEEK", "THIS_MONTH", "MISSED"]


class FocDashboardSummaryRead(BaseModel):
    action_required_count: int = 0
    start_run_count: int = 0
    continue_run_count: int = 0
    watch_count: int = 0
    upcoming_foc_count: int = 0
    upcoming_release_count: int = 0


class FocDashboardItemRead(BaseModel):
    release_id: int
    pull_list_issue_id: int | None = None
    decision_id: int | None = None
    series_name: str = ""
    issue_number: str = ""
    title: str = ""
    publisher: str = ""
    decision_type: PullListDecisionType | None = None
    confidence_score: float | None = None
    foc_date: date | None = None
    release_date: date | None = None
    days_until_foc: int | None = None
    days_until_release: int | None = None
    foc_status: FocDateStatus | None = None
    reasons: list[str] = Field(default_factory=list)
    sections: list[FocDashboardSection] = Field(default_factory=list)
    on_pull_list: bool = False
    pull_list_action_state: str | None = None


class FocDashboardRead(BaseModel):
    status: str = "OK"
    message: str = ""
    summary: FocDashboardSummaryRead
    action_required: list[FocDashboardItemRead] = Field(default_factory=list)
    upcoming_foc: list[FocDashboardItemRead] = Field(default_factory=list)
    upcoming_releases: list[FocDashboardItemRead] = Field(default_factory=list)
    missed_foc: list[FocDashboardItemRead] = Field(default_factory=list)
    watchlist: list[FocDashboardItemRead] = Field(default_factory=list)


class FocDashboardListResponse(BaseModel):
    items: list[FocDashboardItemRead]
    total_items: int
    limit: int
    offset: int
