from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScanAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_uuid: str
    inventory_copy_id: int | None
    front_image_id: int | None
    back_image_id: int | None
    analysis_status: str
    created_at: datetime


class ScanQualityAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    image_quality_score: float
    resolution_score: float
    alignment_score: float
    glare_score: float
    crop_score: float
    quality_status: str
    created_at: datetime


class ConditionProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    overall_condition_score: float
    confidence_score: float
    created_at: datetime


class ConditionDefectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    defect_type: str
    defect_location: str
    defect_severity: str
    confidence_score: float
    created_at: datetime


class ConditionSubgradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    subgrade_type: str
    score: float
    confidence_score: float
    created_at: datetime


class ConditionAgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class ScanAnalysisListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanAnalysisRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ScanAnalysisDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: ScanAnalysisRead
    quality_assessments: list[ScanQualityAssessmentRead] = Field(default_factory=list)
    profiles: list[ConditionProfileRead] = Field(default_factory=list)
    defects: list[ConditionDefectRead] = Field(default_factory=list)
    subgrades: list[ConditionSubgradeRead] = Field(default_factory=list)
    executions: list[ConditionAgentExecutionRead] = Field(default_factory=list)


class ScanQualityAssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanQualityAssessmentRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ConditionProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConditionProfileRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ConditionDefectListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConditionDefectRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ConditionSubgradeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConditionSubgradeRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ConditionAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConditionAgentExecutionRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ConditionIntelligenceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: int | None = None
    inventory_copy_id: int | None = None
    front_image_id: int | None = None
    back_image_id: int | None = None


class ConditionDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_count: int
    profile_count: int
    defect_count: int
    subgrade_count: int
    quality_assessment_count: int
    execution_count: int
    average_condition_score: float
    average_quality_score: float
    condition_summary: list[ConditionProfileRead] = Field(default_factory=list)
    defect_summary: list[ConditionDefectRead] = Field(default_factory=list)
    subgrade_summary: list[ConditionSubgradeRead] = Field(default_factory=list)
    scan_quality_summary: list[ScanQualityAssessmentRead] = Field(default_factory=list)
    agent_activity: list[ConditionAgentExecutionRead] = Field(default_factory=list)


class ConditionQualityRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: ScanAnalysisRead
    quality: ScanQualityAssessmentRead


class ConditionDefectsRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: ScanAnalysisRead
    defects: list[ConditionDefectRead] = Field(default_factory=list)


class ConditionProfileRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: ScanAnalysisRead
    profile: ConditionProfileRead


class ConditionSubgradesRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: ScanAnalysisRead
    subgrades: list[ConditionSubgradeRead] = Field(default_factory=list)
