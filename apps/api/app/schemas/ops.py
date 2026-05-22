from datetime import datetime

from pydantic import BaseModel


class OpsQueueSnapshot(BaseModel):
    queue_name: str
    queued_jobs: int
    started_jobs: int
    failed_jobs: int
    most_recent_job_result: str | None = None


class OpsJobRow(BaseModel):
    job_id: str
    job_type: str
    queue_name: str
    status: str
    user_id: int | None = None
    user_email: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    result_summary: str | None = None
    error: str | None = None


class OpsDraftImportRow(BaseModel):
    draft_id: int
    user_id: int
    user_email: str
    retailer: str | None = None
    status: str
    confidence: str
    warning_count: int
    created_at: datetime
    linked_order_id: int | None = None


class OpsGmailSyncRow(BaseModel):
    gmail_account_id: int
    user_id: int
    user_email: str
    gmail_email: str
    auto_sync_enabled: bool
    last_sync_status: str | None = None
    last_sync_started_at: datetime | None = None
    last_sync_completed_at: datetime | None = None
    processed_messages: int | None = None
    created_draft_imports: int | None = None
    skipped_duplicates: int | None = None
    last_error_message: str | None = None


class OpsEventRow(BaseModel):
    id: int
    event_type: str
    status: str
    created_at: datetime
    user_id: int | None = None
    user_email: str | None = None
    draft_import_id: int | None = None
    order_id: int | None = None
    external_message_id: str | None = None
    message: str | None = None
    details: dict


class OpsDashboardResponse(BaseModel):
    recent_gmail_sync_jobs: list[OpsJobRow]
    recent_ai_parse_jobs: list[OpsJobRow]
    gmail_sync_statuses: list[OpsGmailSyncRow]
    recent_draft_imports: list[OpsDraftImportRow]
    parser_failures: list[OpsEventRow]
    duplicate_skip_events: list[OpsEventRow]
    confirm_events: list[OpsEventRow]
    queue_health: list[OpsQueueSnapshot]
