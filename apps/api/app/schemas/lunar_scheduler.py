from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.lunar_scheduler import LunarScheduleConfig, LunarScheduledRun, LunarScheduledRunError


class LunarSchedulerStatusRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_available: bool
    enabled: bool
    schedule_type: str
    schedule_time: str
    timezone: str
    next_run_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_imported_file_name: str
    last_imported_file_period: str
    last_imported_at: datetime | None

    @classmethod
    def from_config(cls, config: LunarScheduleConfig, *, credential_available: bool) -> LunarSchedulerStatusRead:
        return cls(
            credential_available=credential_available,
            enabled=config.enabled,
            schedule_type=config.schedule_type,
            schedule_time=config.schedule_time,
            timezone=config.timezone,
            next_run_at=config.next_run_at,
            last_success_at=config.last_success_at,
            last_failure_at=config.last_failure_at,
            last_imported_file_name=config.last_imported_file_name,
            last_imported_file_period=config.last_imported_file_period,
            last_imported_at=config.last_imported_at,
        )


class LunarScheduledRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    run_uuid: str
    trigger_type: str
    status: str
    file_name: str | None
    file_period: str | None
    records_processed: int
    records_imported: int
    records_updated: int
    records_failed: int
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class LunarScheduledRunErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scheduled_run_id: int
    error_code: str
    error_message: str
    created_at: datetime


class LunarSchedulerHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[LunarScheduledRunRead]
    total_runs: int
    no_change_runs: int
    import_runs: int
    failed_runs: int


class LunarSchedulerSetTimeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_time: str
    timezone: str | None = None


class LunarSchedulerRunNowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    run_uuid: str
    status: str
    file_name: str | None = None
    file_period: str | None = None
    records_processed: int
    records_imported: int
    records_updated: int
    records_failed: int

    @classmethod
    def from_run(cls, run: LunarScheduledRun) -> LunarSchedulerRunNowRead:
        return cls(
            run_id=int(run.id or 0),
            run_uuid=run.run_uuid,
            status=run.status,
            file_name=run.file_name,
            file_period=run.file_period,
            records_processed=run.records_processed,
            records_imported=run.records_imported,
            records_updated=run.records_updated,
            records_failed=run.records_failed,
        )
