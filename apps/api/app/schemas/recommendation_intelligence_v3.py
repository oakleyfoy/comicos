"""P62 Recommendation V3 preview API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class V3ScoreComponentRead(BaseModel):
    component_name: str
    component_score: float
    component_weight: float
    explanation: str


class V3PreviewItemRead(BaseModel):
    title: str
    recommendation_type: str
    v2_priority_score: float
    v2_confidence_score: float
    v3_preview_score: float
    release_issue_id: int | None = None
    demand_intel_status: str
    components: list[V3ScoreComponentRead] = Field(default_factory=list)


class V3ReadinessRead(BaseModel):
    ready: bool
    reason_codes: list[str] = Field(default_factory=list)
    demand_snapshot_count: int = 0
    velocity_snapshot_count: int = 0
    spec_snapshot_present: bool = False
    spec_row_count: int = 0
    demand_median_age_hours: float | None = None


class V3PreviewRead(BaseModel):
    enabled: bool
    not_ready: bool
    reason_codes: list[str] = Field(default_factory=list)
    items: list[V3PreviewItemRead] = Field(default_factory=list)
    readiness: V3ReadinessRead | None = None
    persisted_row_count: int = 0
    v2_mutated: bool = False
    preview_count: int = 0


class V3CertificationRead(BaseModel):
    component: str
    certified: bool
    status: str
    summary: str
    notes: list[str] = Field(default_factory=list)
    checked_at: str
    flags: dict[str, bool] = Field(default_factory=dict)
    preview: dict = Field(default_factory=dict)
