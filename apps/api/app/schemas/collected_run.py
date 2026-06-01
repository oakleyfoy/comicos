from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CollectedRunStatus = Literal["ACTIVE", "INACTIVE", "COMPLETE", "UNKNOWN"]


class CollectedRunRead(BaseModel):
    id: int
    owner_id: int
    publisher: str
    series_name: str
    latest_owned_issue: str
    total_owned_issues: int = Field(ge=0)
    run_status: CollectedRunStatus
    created_at: str


class CollectedRunListRead(BaseModel):
    items: list[CollectedRunRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class CollectedRunSummaryRead(BaseModel):
    total_runs: int = Field(default=0, ge=0)
    active_runs: int = Field(default=0, ge=0)
    inactive_runs: int = Field(default=0, ge=0)
    complete_runs: int = Field(default=0, ge=0)
    unknown_runs: int = Field(default=0, ge=0)
    last_refreshed_at: str | None = None
