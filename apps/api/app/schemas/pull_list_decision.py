from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

PullListDecisionType = Literal["START_RUN", "CONTINUE_RUN", "WATCH", "PASS"]


class PullListDecisionRead(BaseModel):
    id: int
    owner_id: int
    release_id: int
    decision_type: PullListDecisionType
    confidence_score: float
    explanation: str
    reasons: list[str]
    created_at: datetime
    comic_title: str = ""
    issue_number: str = ""
    publisher: str = ""
    series_name: str = ""
    release_date: date | None = None
    foc_date: date | None = None
    recommendation_tier: str | None = None
    recommendation_score: float | None = None


class PullListDecisionListResponse(BaseModel):
    items: list[PullListDecisionRead]
    total_items: int
    limit: int
    offset: int


class PullListDecisionGenerateResponse(BaseModel):
    decisions_created: int
