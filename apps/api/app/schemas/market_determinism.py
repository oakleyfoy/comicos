from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarketDeterminismStatus = Literal["PASS", "FAIL", "WARNING"]


class MarketDeterminismValidationRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: date | None = None


class MarketDeterminismValidationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    validation_status: MarketDeterminismStatus | str
    validation_checksum: str
    pipeline_checksum: str
    snapshot_date: date
    total_stages_checked: int
    total_invariants_checked: int
    total_replays_checked: int
    invariant_failure_count: int
    checksum_mismatch_count: int
    replay_failure_count: int
    ordering_failure_count: int
    validation_summary_json: dict[str, Any]
    created_at: datetime


class MarketDeterminismInvariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_determinism_validation_run_id: int
    owner_user_id: int
    layer_name: str
    invariant_code: str
    invariant_status: MarketDeterminismStatus | str
    expected_value_json: dict[str, Any] | None = None
    actual_value_json: dict[str, Any] | None = None
    detail_json: dict[str, Any]
    created_at: datetime


class MarketDeterminismChecksumAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_determinism_validation_run_id: int
    owner_user_id: int
    stage_name: str
    upstream_stage_name: str | None = None
    validation_status: MarketDeterminismStatus | str
    upstream_checksum: str | None = None
    current_checksum: str | None = None
    pipeline_checksum: str
    detail_json: dict[str, Any]
    created_at: datetime


class MarketDeterminismReplayAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_determinism_validation_run_id: int
    owner_user_id: int
    artifact_type: str
    artifact_key: str
    replay_status: MarketDeterminismStatus | str
    original_checksum: str | None = None
    replay_checksum: str | None = None
    pipeline_checksum: str
    detail_json: dict[str, Any]
    created_at: datetime


class MarketDeterminismValidationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketDeterminismValidationRunRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketDeterminismInvariantListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketDeterminismInvariantRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketDeterminismReplayAuditListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketDeterminismReplayAuditRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketDeterminismRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    run: MarketDeterminismValidationRunRead
    checksum_audits: list[MarketDeterminismChecksumAuditRead] = Field(default_factory=list)
    invariants: list[MarketDeterminismInvariantRead] = Field(default_factory=list)
    replay_audits: list[MarketDeterminismReplayAuditRead] = Field(default_factory=list)
