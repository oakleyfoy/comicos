from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.lunar_feed import LunarFeedRun


class LunarCredentialStatusRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_available: bool
    username_masked: str | None = None


class LunarFeedImportSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    status: str
    source_type: str
    file_name: str
    file_period: str
    records_processed: int
    records_created: int
    records_updated: int
    records_failed: int
    foc_alerts_created: int
    errors: list[dict[str, str]] = Field(default_factory=list)

    @classmethod
    def from_run(cls, run: LunarFeedRun, *, errors: list[tuple[str, str, str]]) -> LunarFeedImportSummaryRead:
        return cls(
            run_id=int(run.id or 0),
            status=run.status,
            source_type=run.source_type,
            file_name=run.file_name,
            file_period=run.file_period,
            records_processed=run.records_processed,
            records_created=run.records_created,
            records_updated=run.records_updated,
            records_failed=run.records_failed,
            foc_alerts_created=run.foc_alerts_created,
            errors=[
                {"record_identifier": record_id, "error_code": code, "message": message}
                for record_id, code, message in errors
            ],
        )


class LunarFeedRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    run_uuid: str
    source_type: str
    file_name: str
    file_period: str
    status: str
    records_processed: int
    records_created: int
    records_updated: int
    records_failed: int
    foc_alerts_created: int
    source_url: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class LunarFeedDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_status: LunarCredentialStatusRead
    last_run: LunarFeedRunRead | None = None


class LunarRemoteDownloadRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str
    file_period: str
    file_type: str
    source_url: str
    byte_size: int
