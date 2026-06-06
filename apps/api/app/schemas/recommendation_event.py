"""P73-01 recommendation action event schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class P73RecommendationEventCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(..., min_length=2, max_length=32)
    event_source: str = Field(default="manual", max_length=32)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=8000)


class P73RecommendationEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    outcome_id: int
    event_type: str
    event_source: str
    metadata_json: dict[str, object]
    notes: str | None
    created_at: datetime


class P73RecommendationTimelineEntryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    event_source: str
    created_at: datetime
    metadata_json: dict[str, object] = Field(default_factory=dict)
