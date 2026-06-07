from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.ocr_pipeline_health import OpsPipelineHealth


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


class OpsInventoryDuplicateCopyRow(BaseModel):
    inventory_copy_id: int
    user_id: int | None = None
    user_email: str | None = None
    order_id: int | None = None
    retailer: str | None = None
    order_date: date | None = None
    acquisition_cost: str
    created_at: datetime


class OpsInventoryDuplicateCandidateGroup(BaseModel):
    metadata_identity_key: str
    count: int
    publisher: str
    series_title: str
    issue_number: str
    variant: str
    review_status: str
    notes: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    copies: list[OpsInventoryDuplicateCopyRow]


class OpsCanonicalSeriesRow(BaseModel):
    id: int
    canonical_title: str
    canonical_publisher: str
    series_key: str
    first_seen_at: datetime
    last_seen_at: datetime
    earliest_known_release_date: date | None = None
    latest_known_release_date: date | None = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    inventory_count: int


class OpsCanonicalCreatorRow(BaseModel):
    id: int
    canonical_name: str
    normalized_name: str
    creator_key: str
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    is_active: bool


class OpsMetadataAuditRow(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    before_snapshot: dict | None = None
    after_snapshot: dict | None = None
    reason: str | None = None
    actor_user_id: int | None = None
    actor_email: str | None = None
    created_at: datetime


class OpsMetadataReenrichmentEnqueueResponse(BaseModel):
    job_id: str
    status: str
    entity_type: str
    entity_id: int


class OpsReconciliationSummary(BaseModel):
    open_conflicts: int
    pending_canonical_suggestions: int
    high_confidence_unreviewed_match_candidates: int
    confirmed_duplicate_scans: int
    probable_variant_families: int
    recent_relationship_replay_changes: int


class OpsDashboardResponse(BaseModel):
    status: str = "OK"
    message: str = ""
    recent_gmail_sync_jobs: list[OpsJobRow]
    recent_ai_parse_jobs: list[OpsJobRow]
    gmail_sync_statuses: list[OpsGmailSyncRow]
    recent_draft_imports: list[OpsDraftImportRow]
    parser_failures: list[OpsEventRow]
    duplicate_skip_events: list[OpsEventRow]
    confirm_events: list[OpsEventRow]
    queue_health: list[OpsQueueSnapshot]
    pipeline_health: OpsPipelineHealth
    recent_cover_pipeline_jobs: list[OpsJobRow]
    reconciliation_summary: OpsReconciliationSummary