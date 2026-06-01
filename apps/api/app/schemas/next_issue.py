from __future__ import annotations

from pydantic import BaseModel, Field


class NextIssueRead(BaseModel):
    id: int
    owner_id: int
    series_name: str
    current_issue: str
    next_issue: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    created_at: str


class NextIssueListRead(BaseModel):
    items: list[NextIssueRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)
