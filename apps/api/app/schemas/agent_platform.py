from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentPlatformValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object]


class AgentPlatformValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    checks: list[AgentPlatformValidationCheckRead]


class AgentPlatformSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    validation_status: str
    security_status: str
    analytics_status: str
    recommendation_engine_status: str
    workflow_status: str


class AgentPlatformReadinessSectionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object]


class AgentPlatformReadinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_name: str
    overall_status: str
    sections: list[AgentPlatformReadinessSectionRead]
