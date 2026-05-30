from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    finding_id: int
    evidence_type: str
    source_name: str
    source_url: str | None
    source_payload_json: dict[str, Any]
    evidence_score: float
    created_at: datetime


class ResearchFindingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_id: int
    finding_code: str
    finding_type: str
    title: str
    description: str
    confidence_score: float = Field(ge=0.0)
    priority_score: float = Field(ge=0.0)
    status: str
    recommendation_json: dict[str, Any]
    created_at: datetime
    evidence: list[ResearchEvidenceRead] = Field(default_factory=list)


class ResearchSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    agent_execution_id: int
    snapshot_uuid: str
    agent_code: str
    research_type: str
    status: str
    generated_at: datetime
    input_scope_json: dict[str, Any]
    summary_json: dict[str, Any]
    created_at: datetime


class ResearchSnapshotDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: ResearchSnapshotRead
    findings: list[ResearchFindingRead] = Field(default_factory=list)


class ResearchSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResearchSnapshotRead]
    total_items: int
    limit: int
    offset: int


class ResearchFindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResearchFindingRead]
    total_items: int
    limit: int
    offset: int
