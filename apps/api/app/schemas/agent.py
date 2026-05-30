from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentCapabilityDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_code: str = Field(min_length=1, max_length=80)
    capability_name: str = Field(min_length=1, max_length=160)


class AgentCapabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    capability_code: str
    capability_name: str


class AgentDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    version: str = Field(min_length=1, max_length=40)
    enabled: bool = False
    capabilities: list[AgentCapabilityDeclaration] = Field(default_factory=list)


class AgentDefinitionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    description: str
    version: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    capabilities: list[AgentCapabilityRead]


class AgentExecutionEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    execution_id: int
    event_type: str
    event_timestamp: datetime
    event_payload_json: dict


class AgentExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    agent_id: int
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    execution_duration_ms: int | None
    triggered_by: str
    trigger_source: str


class AgentExecutionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentDefinitionRead
    execution: AgentExecutionRead
    events: list[AgentExecutionEventRead]


class AgentDefinitionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentDefinitionRead]
    total_items: int
    limit: int
    offset: int


class AgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentExecutionRead]
    total_items: int
    limit: int
    offset: int
