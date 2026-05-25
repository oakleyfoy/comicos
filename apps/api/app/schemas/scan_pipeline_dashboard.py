"""Bulk scan ingest ops dashboard payloads (deterministic aggregates only).

No pipeline runs, OCR enqueue, or metadata mutation from these reads.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.scan_sessions import ScanSessionSummaryRead


class ScannerProfileUsageRowRead(BaseModel):
    """Scanner preset usage keyed by persisted profile rows when linked."""

    scanner_profile_id: int | None = None
    profile_label: str = Field(description="Frozen profile label on scan sessions.")
    scan_session_count: int = Field(ge=0)


class ScanPipelineDashboardSummaryRead(BaseModel):
    """Fleet / owner-scope counters for ingest, QA snapshots, routing, intake, replay."""

    active_sessions: int = Field(ge=0, description="Sessions in pending|active|paused.")

    sessions_completed_with_errors: int = Field(ge=0, description='Sessions with terminal status completed_with_errors.')

    failed_items: int = Field(ge=0, description="Across scan_session failed_items rollup for scoped sessions.")

    review_required_items: int = Field(ge=0, description='Scan_session_item rows where ingest_status == "review_required".')
    qa_needs_rescan: int = Field(ge=0, description='Persisted scan_qa_result rows scoped to qa_classification == "needs_rescan".')
    qa_corrupt_or_unreadable: int = Field(ge=0)

    routing_recommend_ocr: int = Field(
        ge=0,
        description='Open queue_routing_recommendation rows with recommendation_type == "recommend_ocr".',
    )
    routing_recommend_high_res_review: int = Field(
        ge=0,
        description='Open queue routing rows recommending high-res workflow.',
    )

    high_res_pending: int = Field(ge=0, description='high_res_review_request rows where status == "pending".')
    physical_intake_received_pending_scan: int = Field(
        ge=0,
        description="Physical intake projections in received_pending_scan state.",
    )

    replay_runs_with_changes: int = Field(
        ge=0,
        description="Scan_pipeline_replay_run rows scoped to owners with changed_items > 0.",
    )

    most_used_scanner_profiles: list[ScannerProfileUsageRowRead] = Field(
        default_factory=list,
        description="Top presets by bulk scan-session count (capped server-side).",
    )


class ScanPipelineDashboardRead(BaseModel):
    summary: ScanPipelineDashboardSummaryRead
    active_sessions: list[ScanSessionSummaryRead] = Field(default_factory=list)
    recent_sessions: list[ScanSessionSummaryRead] = Field(default_factory=list)
