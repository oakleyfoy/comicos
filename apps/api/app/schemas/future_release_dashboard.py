from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.future_release_action import FutureReleaseActionRead
from app.schemas.future_release_match import FutureReleaseMatchRead
from app.schemas.next_issue import NextIssueRead
from app.schemas.release_watchlist import WatchlistMatchRead


class FutureReleaseDashboardSummaryRead(BaseModel):
    active_runs: int = Field(default=0, ge=0)
    upcoming_issues: int = Field(default=0, ge=0)
    foc_this_week: int = Field(default=0, ge=0)
    preorder_now: int = Field(default=0, ge=0)
    missed_foc: int = Field(default=0, ge=0)


class FutureReleaseDashboardRead(BaseModel):
    summary: FutureReleaseDashboardSummaryRead
    next_issues: list[NextIssueRead] = Field(default_factory=list)
    upcoming_foc: list[FutureReleaseMatchRead] = Field(default_factory=list)
    preorder_now: list[FutureReleaseActionRead] = Field(default_factory=list)
    this_week: list[FutureReleaseActionRead] = Field(default_factory=list)
    missed_foc: list[FutureReleaseActionRead] = Field(default_factory=list)
    watchlist: list[WatchlistMatchRead] = Field(default_factory=list)
