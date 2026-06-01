from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FutureReleaseActionType = Literal["PREORDER_NOW", "PREORDER_THIS_WEEK", "WATCH", "MISSED_FOC"]


class FutureReleaseActionRead(BaseModel):
    id: int
    owner_id: int
    series_name: str
    issue_number: str
    action_type: FutureReleaseActionType
    priority_score: float = Field(ge=0.0, le=100.0)
    foc_date: str | None = None
    release_id: int | None = None
    created_at: str


class FutureReleaseActionListRead(BaseModel):
    items: list[FutureReleaseActionRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)
