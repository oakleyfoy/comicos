from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseSeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    publisher: str
    series_name: str
    series_type: str
    status: str
    created_at: datetime


class ReleaseIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    release_uuid: str
    series_id: int
    issue_number: str
    title: str
    foc_date: date | None
    release_date: date | None
    original_foc_date: date | None = None
    original_release_date: date | None = None
    cover_price: float
    release_status: str
    created_at: datetime


class ReleaseVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    variant_uuid: str
    variant_name: str
    ratio_value: int | None
    ratio_type: str | None
    is_incentive_variant: bool
    variant_type: str
    cover_artist: str | None
    source_item_code: str
    printing_number: int | None = None
    printing_kind: str = "FIRST_PRINT"
    printing_foc_date: date | None = None
    printing_release_date: date | None = None
    created_at: datetime


class ReleaseKeySignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    signal_type: str
    confidence_score: float
    signal_payload_json: dict[str, object]
    created_at: datetime


class ReleaseAgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class ReleaseVariantImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_uuid: str = ""
    variant_name: str
    ratio_value: int | None = None
    ratio_type: str | None = None
    is_incentive_variant: bool = False
    variant_type: str
    cover_artist: str | None = None
    source_item_code: str = ""
    printing_number: int | None = None
    printing_kind: str = "FIRST_PRINT"
    printing_foc_date: date | None = None
    printing_release_date: date | None = None


class ReleaseIssueImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_uuid: str
    issue_number: str
    title: str = ""
    foc_date: date | None = None
    release_date: date | None = None
    cover_price: float = 0.0
    release_status: str = "ANNOUNCED"
    variants: list[ReleaseVariantImport] = Field(default_factory=list)


class ReleaseSeriesImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publisher: str
    series_name: str
    series_type: str
    status: str = "ACTIVE"
    issues: list[ReleaseIssueImport] = Field(default_factory=list)


class ReleaseImportFeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: list[ReleaseSeriesImport] = Field(default_factory=list)


class ReleaseImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_created: int
    issues_created: int
    variants_created: int
    series_matched: int = 0
    issues_matched: int = 0
    variants_matched: int = 0


class ReleaseSeriesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseSeriesRead]
    total_items: int
    limit: int
    offset: int


class ReleaseIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseIssueRead]
    total_items: int
    limit: int
    offset: int


class ReleaseVariantListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseVariantRead]
    total_items: int
    limit: int
    offset: int


class ReleaseKeySignalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseKeySignalRead]
    total_items: int
    limit: int
    offset: int


class ReleaseAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseAgentExecutionRead]
    total_items: int
    limit: int
    offset: int


class ReleaseSignalFeedItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: ReleaseSeriesRead
    issue: ReleaseIssueRead
    signal: ReleaseKeySignalRead


class ReleaseIntelligenceDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upcoming_releases: list[ReleaseIssueRead]
    foc_calendar: list[ReleaseIssueRead]
    new_number_one_feed: list[ReleaseSignalFeedItemRead]
    key_issue_feed: list[ReleaseSignalFeedItemRead]
    variant_feed: list[ReleaseSignalFeedItemRead]
    agent_activity: list[ReleaseAgentExecutionRead]
    variant_count: int = 0
    ratio_variant_count: int = 0
    cover_variant_count: int = 0
    recent_variants: list[ReleaseVariantRead] = Field(default_factory=list)
    top_ratio_variants: list[ReleaseVariantRead] = Field(default_factory=list)


class ReleaseSignalsRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[ReleaseKeySignalRead]
    execution: ReleaseAgentExecutionRead
