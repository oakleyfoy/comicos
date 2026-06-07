"""Safe GET handlers for ops ingestion monitoring — no deep scans on read."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import Settings
from app.schemas.market_ingestion import (
    MarketAcquisitionIngestionBatchListResponse,
    MarketAcquisitionIngestionBatchRead,
    MarketAcquisitionRawSourceListResponse,
)
from app.schemas.ocr_pipeline_health import OpsBatchFailureSummary, OpsPipelineHealth, OpsReplayFailureSummary
from app.schemas.ops import OpsDashboardResponse, OpsReconciliationSummary
from app.schemas.scan_ingestion import ScanImageListResponse, ScanIngestionBatchListResponse
from app.schemas.scan_pipeline_dashboard import ScanPipelineDashboardRead, ScanPipelineDashboardSummaryRead
from app.services.collector_page_load_service import _short_error
from app.services.market_ingestion import get_ingestion_batch_ops, list_ingestion_batches_ops, list_ingestion_raw_ops
from app.services.ops_admin import build_ops_dashboard
from app.services.scan_ingestion import list_scan_ingestion_batches_ops, list_scan_ingestion_failures_ops
from app.services.scan_pipeline_dashboard import scan_pipeline_dashboard

logger = logging.getLogger(__name__)


def _empty_pipeline_health() -> OpsPipelineHealth:
    now = datetime.now(timezone.utc)
    empty_replay = OpsReplayFailureSummary(failed_items_total_recent=0, failed_recent_run_ids=[])
    empty_batch = OpsBatchFailureSummary(batches_with_failed_items=0, failed_items_total_recent=0)
    return OpsPipelineHealth(
        window_hours=24,
        cutoff_utc=now,
        failed_ocr_results=0,
        ocr_tesseract_timeouts=0,
        corrupt_image_failures=0,
        retry_exhausted_batch_items=0,
        replay_failed_items_total=0,
        stale_cover_ocr_processing=0,
        stale_batch_items=0,
        stale_replay_running_items=0,
        stale_batch_rows=[],
        stale_cover_ocr_rows=[],
        stale_replay_rows=[],
        replay_failures_recent=empty_replay,
        batch_failures=empty_batch,
    )


def safe_ops_dashboard(session: Session, settings: Settings) -> OpsDashboardResponse:
    try:
        body = build_ops_dashboard(session, settings, include_pipeline_health=False)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_ops_dashboard failed: %s", exc, exc_info=True)
        return OpsDashboardResponse(
            status="EMPTY",
            message=_short_error(exc) or "Ingestion dashboard data unavailable.",
            recent_gmail_sync_jobs=[],
            recent_ai_parse_jobs=[],
            gmail_sync_statuses=[],
            recent_draft_imports=[],
            parser_failures=[],
            duplicate_skip_events=[],
            confirm_events=[],
            queue_health=[],
            pipeline_health=_empty_pipeline_health(),
            recent_cover_pipeline_jobs=[],
            reconciliation_summary=OpsReconciliationSummary(
                open_conflicts=0,
                pending_canonical_suggestions=0,
                high_confidence_unreviewed_match_candidates=0,
                confirmed_duplicate_scans=0,
                probable_variant_families=0,
                recent_relationship_replay_changes=0,
            ),
        )


def safe_list_market_ingestion_batches_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionIngestionBatchListResponse:
    try:
        body = list_ingestion_batches_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_list_market_ingestion_batches_ops failed: %s", exc, exc_info=True)
        return MarketAcquisitionIngestionBatchListResponse(
            status="EMPTY",
            message=_short_error(exc) or "No market ingestion batches available.",
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
        )


def safe_get_market_ingestion_batch_ops(session: Session, *, batch_id: int) -> MarketAcquisitionIngestionBatchRead:
    try:
        return get_ingestion_batch_ops(session, batch_id=batch_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_get_market_ingestion_batch_ops failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=404, detail="Ingestion batch unavailable.") from exc


def safe_list_market_ingestion_raw_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    ingestion_batch_id: int | None,
    processing_status: str | None,
    limit: int,
    offset: int,
) -> MarketAcquisitionRawSourceListResponse:
    try:
        body = list_ingestion_raw_ops(
            session,
            owner_user_id=owner_user_id,
            ingestion_batch_id=ingestion_batch_id,
            processing_status=processing_status,
            limit=limit,
            offset=offset,
        )
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_list_market_ingestion_raw_ops failed: %s", exc, exc_info=True)
        return MarketAcquisitionRawSourceListResponse(
            status="EMPTY",
            message=_short_error(exc) or "No raw ingestion rows available.",
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
        )


def safe_list_scan_ingestion_batches_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanIngestionBatchListResponse:
    try:
        body = list_scan_ingestion_batches_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_list_scan_ingestion_batches_ops failed: %s", exc, exc_info=True)
        return ScanIngestionBatchListResponse(
            status="EMPTY",
            message=_short_error(exc) or "No scan ingestion batches available.",
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
        )


def safe_list_scan_ingestion_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanImageListResponse:
    try:
        body = list_scan_ingestion_failures_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_list_scan_ingestion_failures_ops failed: %s", exc, exc_info=True)
        return ScanImageListResponse(
            status="EMPTY",
            message=_short_error(exc) or "No scan ingestion failures recorded.",
            items=[],
            total_items=0,
            limit=limit,
            offset=offset,
        )


def safe_ops_scan_pipeline_dashboard(session: Session) -> ScanPipelineDashboardRead:
    try:
        body = scan_pipeline_dashboard(session, owner_user_id=None)
        body.status = "OK"
        body.message = ""
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_ops_scan_pipeline_dashboard failed: %s", exc, exc_info=True)
        empty_summary = ScanPipelineDashboardSummaryRead()
        return ScanPipelineDashboardRead(
            status="EMPTY",
            message=_short_error(exc) or "Pipeline dashboard unavailable.",
            summary=empty_summary,
            active_sessions=[],
            recent_sessions=[],
        )
