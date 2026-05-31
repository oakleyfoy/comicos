from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.release_intelligence import ReleaseImportFeedRequest


class ReleaseImportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    import_uuid: str
    import_type: str
    file_name: str
    records_processed: int
    records_created: int
    records_updated: int
    records_failed: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class ReleaseImportFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_run_id: int
    file_name: str
    file_type: str
    file_size: int
    created_at: datetime


class ReleaseImportErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_run_id: int
    record_identifier: str
    error_code: str
    error_message: str
    created_at: datetime


class ReleaseImportUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = "release-feed.json"
    feed: ReleaseImportFeedRequest


class ReleaseImportRunDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: ReleaseImportRunRead
    files: list[ReleaseImportFileRead] = Field(default_factory=list)
    errors: list[ReleaseImportErrorRead] = Field(default_factory=list)


class ReleaseImportRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseImportRunRead]
    total_items: int
    limit: int
    offset: int


class ReleaseImportErrorListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseImportErrorRead]
    total_items: int
    limit: int
    offset: int


class ReleaseImportDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_imports: list[ReleaseImportRunRead]
    import_success_rate: float
    import_failures: int
    latest_uploads: list[ReleaseImportFileRead]
    error_summary: list[dict[str, object]]
