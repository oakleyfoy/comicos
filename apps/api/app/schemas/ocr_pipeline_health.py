"""Pydantic payloads for OCR pipeline operations visibility."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OpsPipelineStaleRow(BaseModel):
    category: str
    entity_kind: str
    entity_id: int
    cover_image_id: int | None = None
    detail: str
    stale_since: str | None


class OpsReplayFailureSummary(BaseModel):
    failed_items_total_recent: int
    failed_recent_run_ids: list[int]


class OpsBatchFailureSummary(BaseModel):
    batches_with_failed_items: int
    failed_items_total_recent: int


class OpsPipelineHealth(BaseModel):
    window_hours: int
    cutoff_utc: datetime
    failed_ocr_results: int
    ocr_tesseract_timeouts: int
    corrupt_image_failures: int
    retry_exhausted_batch_items: int
    replay_failed_items_total: int
    stale_cover_ocr_processing: int
    stale_batch_items: int
    stale_replay_running_items: int
    stale_batch_rows: list[OpsPipelineStaleRow]
    stale_cover_ocr_rows: list[OpsPipelineStaleRow]
    stale_replay_rows: list[OpsPipelineStaleRow]
    replay_failures_recent: OpsReplayFailureSummary
    batch_failures: OpsBatchFailureSummary


class OpsOcrPipelineRecoverResponse(BaseModel):
    ocr_results_recovered: int
    batch_items_recovered: int
    replay_items_recovered: int
