"""P37-09 deterministic grading operational reporting (CSV export; lineage items; replay-safe)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    DealerGradingDashboardAlert,
    DealerGradingDashboardFeedEvent,
    DealerGradingDashboardMetric,
    DealerGradingDashboardSnapshot,
    GraderPerformanceSnapshot,
    GradingCandidate,
    GradingOperationalReportFile,
    GradingOperationalReportItem,
    GradingOperationalReportRun,
    GradingReconciliationRecord,
    GradingRecommendation,
    GradingRiskSnapshot,
    GradingRoiSnapshot,
    GradingSpreadSnapshot,
    GradingSubmissionBatch,
    GradingSubmissionShipment,
    InventoryLiquiditySnapshot,
)
from app.schemas.grading_operational_reporting import (
    GRADING_OPERATIONAL_REPORT_TYPES,
    GradingOperationalReportFileRead,
    GradingOperationalReportGeneratePayload,
    GradingOperationalReportGenerationParams,
    GradingOperationalReportItemRead,
    GradingOperationalReportRunDetailRead,
    GradingOperationalReportRunListResponse,
    GradingOperationalReportRunRead,
)
from app.services.reports_export import render_csv, sanitize_report_filename

GENERATOR_VERSION = "p37-09:v1"
SUMMARY_HEADERS: tuple[str, ...] = (
    "metric_family",
    "metric_key",
    "metric_value_integer",
    "metric_value_decimal",
    "metric_value_text",
    "notes",
)
ZERO = Decimal("0")
T = TypeVar("T")
RowPieces = list[tuple[str, str, dict[str, str], dict[str, Any]]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_grading_report_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _row_checksum(cells: dict[str, str]) -> str:
    ordered = {k: cells[k] for k in sorted(cells)}
    return hashlib.sha256(_json_canonical(ordered).encode("utf-8")).hexdigest()


def _decimal_str(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def normalize_generation_params(payload: GradingOperationalReportGenerationParams | dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"generator_version": GENERATOR_VERSION}
    if isinstance(payload, GradingOperationalReportGenerationParams):
        blob = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        blob = GradingOperationalReportGenerationParams.model_validate(payload).model_dump(mode="json")
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid generation params")
    normalized = {"generator_version": GENERATOR_VERSION, **blob}
    return dict(sorted(normalized.items()))


def replay_lookup(session: Session, *, owner_user_id: int, replay_key: str | None) -> GradingOperationalReportRun | None:
    if not replay_key:
        return None
    return session.exec(
        select(GradingOperationalReportRun).where(
            GradingOperationalReportRun.owner_user_id == owner_user_id,
            GradingOperationalReportRun.replay_key == replay_key,
        )
    ).first()


def _coerce_run_read(row: GradingOperationalReportRun) -> GradingOperationalReportRunRead:
    gp = row.generation_params_json or {}
    if not isinstance(gp, dict):
        gp = {}
    return GradingOperationalReportRunRead(
        id=int(row.id),
        owner_user_id=int(row.owner_user_id),
        report_type=str(row.report_type),
        status=str(row.status),
        replay_key=row.replay_key,
        generation_params_json=dict(sorted(gp.items(), key=lambda kv: kv[0])),
        checksum=row.checksum,
        csv_row_count=int(row.csv_row_count),
        failure_reason=row.failure_reason,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _coerce_file_read(row: GradingOperationalReportFile) -> GradingOperationalReportFileRead:
    return GradingOperationalReportFileRead.model_validate(row, from_attributes=True)


def _coerce_item_read(row: GradingOperationalReportItem) -> GradingOperationalReportItemRead:
    return GradingOperationalReportItemRead.model_validate(row, from_attributes=True)


def build_run_detail(
    session: Session,
    *,
    owner_user_id: int,
    grading_operational_report_run_id: int,
    include_children: bool = True,
    allow_cross_owner_ops: bool = False,
) -> GradingOperationalReportRunDetailRead:
    row = session.get(GradingOperationalReportRun, grading_operational_report_run_id)
    if row is None or (int(row.owner_user_id) != owner_user_id and not allow_cross_owner_ops):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report run not found")
    base = _coerce_run_read(row).model_dump()
    if not include_children:
        return GradingOperationalReportRunDetailRead.model_validate({**base, "items": [], "files": []})

    item_rows = session.exec(
        select(GradingOperationalReportItem)
        .where(GradingOperationalReportItem.grading_operational_report_run_id == grading_operational_report_run_id)
        .order_by(col(GradingOperationalReportItem.row_number).asc(), col(GradingOperationalReportItem.id).asc()),
    ).all()
    files = session.exec(
        select(GradingOperationalReportFile)
        .where(GradingOperationalReportFile.grading_operational_report_run_id == grading_operational_report_run_id)
        .order_by(col(GradingOperationalReportFile.id).asc()),
    ).all()
    return GradingOperationalReportRunDetailRead.model_validate(
        {
            **base,
            "items": [_coerce_item_read(row).model_dump() for row in item_rows],
            "files": [_coerce_file_read(row).model_dump() for row in files],
        }
    )


def list_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    report_type: str | None,
    status_filter: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingOperationalReportRun], int]:
    q = select(GradingOperationalReportRun).where(GradingOperationalReportRun.owner_user_id == owner_user_id)
    c = select(func.count(col(GradingOperationalReportRun.id))).where(GradingOperationalReportRun.owner_user_id == owner_user_id)
    if report_type:
        q = q.where(GradingOperationalReportRun.report_type == report_type)
        c = c.where(GradingOperationalReportRun.report_type == report_type)
    if status_filter:
        normalized = status_filter.upper()
        q = q.where(GradingOperationalReportRun.status == normalized)
        c = c.where(GradingOperationalReportRun.status == normalized)
    if created_from is not None:
        q = q.where(GradingOperationalReportRun.created_at >= created_from)
        c = c.where(GradingOperationalReportRun.created_at >= created_from)
    if created_to is not None:
        q = q.where(GradingOperationalReportRun.created_at <= created_to)
        c = c.where(GradingOperationalReportRun.created_at <= created_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(GradingOperationalReportRun.created_at).desc(), col(GradingOperationalReportRun.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    report_type: str | None,
    status_filter: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingOperationalReportRun], int]:
    q = select(GradingOperationalReportRun)
    c = select(func.count(col(GradingOperationalReportRun.id))).select_from(GradingOperationalReportRun)
    if owner_user_id is not None:
        q = q.where(GradingOperationalReportRun.owner_user_id == owner_user_id)
        c = c.where(GradingOperationalReportRun.owner_user_id == owner_user_id)
    if report_type:
        q = q.where(GradingOperationalReportRun.report_type == report_type)
        c = c.where(GradingOperationalReportRun.report_type == report_type)
    if status_filter:
        normalized = status_filter.upper()
        q = q.where(GradingOperationalReportRun.status == normalized)
        c = c.where(GradingOperationalReportRun.status == normalized)
    if created_from is not None:
        q = q.where(GradingOperationalReportRun.created_at >= created_from)
        c = c.where(GradingOperationalReportRun.created_at >= created_from)
    if created_to is not None:
        q = q.where(GradingOperationalReportRun.created_at <= created_to)
        c = c.where(GradingOperationalReportRun.created_at <= created_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(GradingOperationalReportRun.created_at).desc(), col(GradingOperationalReportRun.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_response_from_rows(
    rows: list[GradingOperationalReportRun],
    *,
    total: int,
    limit: int,
    offset: int,
) -> GradingOperationalReportRunListResponse:
    return GradingOperationalReportRunListResponse(
        items=[_coerce_run_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def _latest_rows(
    rows: list[T],
    *,
    key_fn: Callable[[T], Any],
    sort_key_fn: Callable[[T], tuple[Any, ...]],
) -> list[T]:
    latest: dict[Any, T] = {}
    for row in sorted(rows, key=sort_key_fn, reverse=True):
        latest.setdefault(key_fn(row), row)
    return sorted(latest.values(), key=sort_key_fn)


def _scoped_key(*values: Any) -> tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in values)


def _metric_piece(
    lineage_domain: str,
    metric_family: str,
    metric_key: str,
    *,
    integer_value: int | None = None,
    decimal_value: Decimal | None = None,
    text_value: str | None = None,
    notes: str | None = None,
    lineage: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, str], dict[str, Any]]:
    cells = {
        "metric_family": metric_family,
        "metric_key": metric_key,
        "metric_value_integer": "" if integer_value is None else str(int(integer_value)),
        "metric_value_decimal": _decimal_str(decimal_value),
        "metric_value_text": "" if text_value is None else str(text_value),
        "notes": "" if notes is None else str(notes),
    }
    return lineage_domain, metric_key, cells, _json_safe(lineage or {})


def _candidate_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    rows = session.exec(
        select(GradingCandidate)
        .where(GradingCandidate.owner_user_id == owner_user_id)
        .order_by(col(GradingCandidate.id).asc())
    ).all()
    pieces: RowPieces = []
    status_values = sorted({str(row.status) for row in rows} | {"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED", "GRADED", "REJECTED", "ARCHIVED"})
    for status_value in status_values:
        pieces.append(
            _metric_piece(
                "grading_candidate.status_counts",
                "GRADING_CANDIDATE_STATUS",
                f"status::{status_value.lower()}",
                integer_value=sum(1 for row in rows if row.status == status_value),
                lineage={"sources": [{"table": "grading_candidate", "aggregation": "count_by_status"}], "generator": GENERATOR_VERSION},
            )
        )
    for grader in sorted({str(row.target_grader) for row in rows} | {"CBCS", "CGC", "PSA", "RAW_ONLY"}):
        pieces.append(
            _metric_piece(
                "grading_candidate.grader_targets",
                "GRADING_CANDIDATE_GRADER",
                f"target_grader::{grader.lower()}",
                integer_value=sum(1 for row in rows if row.target_grader == grader),
                lineage={"sources": [{"table": "grading_candidate", "aggregation": "count_by_target_grader"}]},
            )
        )
    for priority in sorted({str(row.candidate_priority) for row in rows} | {"LOW", "MEDIUM", "HIGH", "ELITE"}):
        pieces.append(
            _metric_piece(
                "grading_candidate.priority_counts",
                "GRADING_CANDIDATE_PRIORITY",
                f"priority::{priority.lower()}",
                integer_value=sum(1 for row in rows if row.candidate_priority == priority and row.status != "ARCHIVED"),
                lineage={"sources": [{"table": "grading_candidate", "aggregation": "count_by_priority"}]},
            )
        )
    pieces.append(
        _metric_piece(
            "grading_candidate.pipeline_counts",
            "GRADING_CANDIDATE_PIPELINE",
            "submission_readiness::ready_for_submission",
            integer_value=sum(1 for row in rows if row.status == "READY_FOR_SUBMISSION"),
            lineage={"sources": [{"table": "grading_candidate", "aggregation": "ready_for_submission_count"}]},
        )
    )
    pieces.append(
        _metric_piece(
            "grading_candidate.pipeline_counts",
            "GRADING_CANDIDATE_PIPELINE",
            "pipeline_active_count",
            integer_value=sum(1 for row in rows if row.status in {"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED"}),
            lineage={"sources": [{"table": "grading_candidate", "aggregation": "pipeline_active_count"}]},
        )
    )
    return SUMMARY_HEADERS, pieces


def _roi_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    roi_rows = session.exec(
        select(GradingRoiSnapshot).where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    ).all()
    latest_roi = _latest_rows(
        list(roi_rows),
        key_fn=lambda row: _scoped_key(
            row.grading_candidate_id,
            row.inventory_item_id,
            row.canonical_comic_issue_id,
            row.target_grader,
            row.target_grade,
        ),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    risk_rows = session.exec(select(GradingRiskSnapshot).where(GradingRiskSnapshot.owner_user_id == owner_user_id)).all()
    latest_risks = _latest_rows(
        list(risk_rows),
        key_fn=lambda row: _scoped_key(row.grading_candidate_id, row.inventory_item_id, row.canonical_comic_issue_id, row.recommendation_id),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    pieces: RowPieces = []
    for status_value in sorted({str(row.roi_status) for row in latest_roi} | {"ELITE", "STRONG", "NEGATIVE"}):
        pieces.append(
            _metric_piece(
                "grading_roi.status_counts",
                "GRADING_ROI_STATUS",
                f"roi_status::{status_value.lower()}",
                integer_value=sum(1 for row in latest_roi if row.roi_status == status_value),
                lineage={"sources": [{"table": "grading_roi_snapshot", "aggregation": "latest_count_by_status"}]},
            )
        )
    roi_values = [row.estimated_roi_pct for row in latest_roi if row.estimated_roi_pct is not None]
    liquidity_values = [row.liquidity_adjusted_roi for row in latest_roi if row.liquidity_adjusted_roi is not None]
    profit_values = [row.estimated_net_profit for row in latest_roi if row.estimated_net_profit is not None]
    risk_adjusted_values = [row.risk_adjusted_roi for row in latest_risks if row.risk_adjusted_roi is not None]
    pieces.extend(
        [
            _metric_piece(
                "grading_roi.rollups",
                "GRADING_ROI_ROLLUP",
                "average_estimated_roi",
                decimal_value=(sum(roi_values, ZERO) / Decimal(len(roi_values))) if roi_values else None,
                lineage={"sources": [{"table": "grading_roi_snapshot", "aggregation": "latest_average_estimated_roi"}]},
            ),
            _metric_piece(
                "grading_roi.rollups",
                "GRADING_ROI_ROLLUP",
                "average_risk_adjusted_roi",
                decimal_value=(sum(risk_adjusted_values, ZERO) / Decimal(len(risk_adjusted_values))) if risk_adjusted_values else None,
                lineage={"sources": [{"table": "grading_risk_snapshot", "aggregation": "latest_average_risk_adjusted_roi"}]},
            ),
            _metric_piece(
                "grading_roi.rollups",
                "GRADING_ROI_ROLLUP",
                "total_expected_profit",
                decimal_value=sum(profit_values, ZERO) if profit_values else ZERO,
                lineage={"sources": [{"table": "grading_roi_snapshot", "aggregation": "latest_total_expected_profit"}]},
            ),
            _metric_piece(
                "grading_roi.rollups",
                "GRADING_ROI_ROLLUP",
                "average_liquidity_adjusted_economics",
                decimal_value=(sum(liquidity_values, ZERO) / Decimal(len(liquidity_values))) if liquidity_values else None,
                lineage={"sources": [{"table": "grading_roi_snapshot", "aggregation": "latest_average_liquidity_adjusted_roi"}]},
            ),
        ]
    )
    for grade in sorted({str(row.break_even_grade) for row in latest_roi if row.break_even_grade}):
        pieces.append(
            _metric_piece(
                "grading_roi.break_even_grades",
                "GRADING_ROI_BREAK_EVEN",
                f"break_even_grade::{sanitize_report_filename(grade).replace('-', '_')}",
                integer_value=sum(1 for row in latest_roi if row.break_even_grade == grade),
                text_value=grade,
                lineage={"sources": [{"table": "grading_roi_snapshot", "aggregation": "latest_break_even_grade_counts"}]},
            )
        )
    return SUMMARY_HEADERS, pieces


def _submission_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    rows = session.exec(select(GradingSubmissionBatch).where(GradingSubmissionBatch.owner_user_id == owner_user_id)).all()
    shipment_rows = session.exec(
        select(GradingSubmissionShipment)
        .join(
            GradingSubmissionBatch,
            GradingSubmissionShipment.grading_submission_batch_id == GradingSubmissionBatch.id,
        )
        .where(GradingSubmissionBatch.owner_user_id == owner_user_id)
    ).all()
    today = utc_now().date()
    delayed_batches = 0
    for row in rows:
        if row.status not in {"DRAFT", "READY", "SHIPPED", "RECEIVED_BY_GRADER", "GRADING", "RETURN_SHIPPED"}:
            continue
        if row.estimated_turnaround_days is None:
            continue
        start_date = row.submission_date or row.shipped_date or row.created_at.date()
        if (today - start_date).days > int(row.estimated_turnaround_days):
            delayed_batches += 1
    pieces: RowPieces = []
    for status_value in sorted(
        {str(row.status) for row in rows}
        | {"DRAFT", "READY", "SHIPPED", "RECEIVED_BY_GRADER", "GRADING", "RETURN_SHIPPED", "COMPLETED", "CANCELLED"}
    ):
        pieces.append(
            _metric_piece(
                "grading_submission.status_counts",
                "GRADING_SUBMISSION_STATUS",
                f"batch_status::{status_value.lower()}",
                integer_value=sum(1 for row in rows if row.status == status_value),
                lineage={"sources": [{"table": "grading_submission_batch", "aggregation": "count_by_status"}]},
            )
        )
    est_turnaround = [Decimal(str(row.estimated_turnaround_days)) for row in rows if row.estimated_turnaround_days is not None]
    actual_turnaround = [Decimal(str(row.actual_turnaround_days)) for row in rows if row.actual_turnaround_days is not None]
    est_costs = [row.estimated_total_cost for row in rows if row.estimated_total_cost is not None]
    actual_costs = [row.actual_total_cost for row in rows if row.actual_total_cost is not None]
    pieces.extend(
        [
            _metric_piece(
                "grading_submission.turnaround",
                "GRADING_SUBMISSION_TURNAROUND",
                "average_estimated_turnaround_days",
                decimal_value=(sum(est_turnaround, ZERO) / Decimal(len(est_turnaround))) if est_turnaround else None,
                lineage={"sources": [{"table": "grading_submission_batch", "aggregation": "average_estimated_turnaround_days"}]},
            ),
            _metric_piece(
                "grading_submission.turnaround",
                "GRADING_SUBMISSION_TURNAROUND",
                "average_actual_turnaround_days",
                decimal_value=(sum(actual_turnaround, ZERO) / Decimal(len(actual_turnaround))) if actual_turnaround else None,
                lineage={"sources": [{"table": "grading_submission_batch", "aggregation": "average_actual_turnaround_days"}]},
            ),
            _metric_piece(
                "grading_submission.turnaround",
                "GRADING_SUBMISSION_TURNAROUND",
                "delayed_batch_count",
                integer_value=delayed_batches,
                lineage={"sources": [{"table": "grading_submission_batch", "aggregation": "delayed_batch_count"}]},
            ),
            _metric_piece(
                "grading_submission.costs",
                "GRADING_SUBMISSION_COST",
                "estimated_total_submission_cost",
                decimal_value=sum(est_costs, ZERO) if est_costs else ZERO,
                lineage={"sources": [{"table": "grading_submission_batch", "aggregation": "sum_estimated_total_cost"}]},
            ),
            _metric_piece(
                "grading_submission.costs",
                "GRADING_SUBMISSION_COST",
                "actual_total_submission_cost",
                decimal_value=sum(actual_costs, ZERO) if actual_costs else ZERO,
                lineage={"sources": [{"table": "grading_submission_batch", "aggregation": "sum_actual_total_cost"}]},
            ),
        ]
    )
    for direction in sorted({str(row.shipment_direction) for row in shipment_rows} | {"OUTBOUND", "RETURN"}):
        pieces.append(
            _metric_piece(
                "grading_submission.shipments",
                "GRADING_SUBMISSION_SHIPMENT",
                f"shipment_direction::{direction.lower()}",
                integer_value=sum(1 for row in shipment_rows if row.shipment_direction == direction),
                lineage={"sources": [{"table": "grading_submission_shipment", "aggregation": "count_by_direction"}]},
            )
        )
    pieces.append(
        _metric_piece(
            "grading_submission.shipments",
            "GRADING_SUBMISSION_SHIPMENT",
            "delivered_shipment_count",
            integer_value=sum(1 for row in shipment_rows if row.delivered_date is not None),
            lineage={"sources": [{"table": "grading_submission_shipment", "aggregation": "delivered_shipment_count"}]},
        )
    )
    return SUMMARY_HEADERS, pieces


def _reconciliation_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    rows = session.exec(
        select(GradingReconciliationRecord).where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    ).all()
    latest_perf = _latest_rows(
        list(
            session.exec(
                select(GraderPerformanceSnapshot).where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)
            ).all()
        ),
        key_fn=lambda row: str(row.grader),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    reconciled = [row for row in rows if row.reconciliation_status == "RECONCILED"]
    deltas = [row.roi_delta for row in reconciled if row.roi_delta is not None]
    pieces: RowPieces = []
    for status_value in sorted({str(row.grading_accuracy_status) for row in reconciled} | {"ABOVE_EXPECTATION", "MET_EXPECTATION", "BELOW_EXPECTATION", "INSUFFICIENT_DATA"}):
        pieces.append(
            _metric_piece(
                "grading_reconciliation.accuracy_counts",
                "GRADING_RECONCILIATION_ACCURACY",
                f"accuracy::{status_value.lower()}",
                integer_value=sum(1 for row in reconciled if row.grading_accuracy_status == status_value),
                lineage={"sources": [{"table": "grading_reconciliation_record", "aggregation": "count_by_accuracy"}]},
            )
        )
    pieces.append(
        _metric_piece(
            "grading_reconciliation.rollups",
            "GRADING_RECONCILIATION_ROLLUP",
            "average_roi_delta",
            decimal_value=(sum(deltas, ZERO) / Decimal(len(deltas))) if deltas else None,
            lineage={"sources": [{"table": "grading_reconciliation_record", "aggregation": "average_roi_delta"}]},
        )
    )
    for row in sorted(reconciled, key=lambda item: (str(item.expected_grade or ""), str(item.final_grade or ""), int(item.id or 0))):
        if row.expected_grade is None and row.final_grade is None:
            continue
        metric_key = (
            f"grade_pair::{sanitize_report_filename(str(row.expected_grade or 'unknown')).replace('-', '_')}"
            f"__{sanitize_report_filename(str(row.final_grade or 'unknown')).replace('-', '_')}"
        )
        pieces.append(
            _metric_piece(
                "grading_reconciliation.grade_pairs",
                "GRADING_RECONCILIATION_GRADE_PAIR",
                metric_key,
                integer_value=1,
                text_value=f"{row.expected_grade or 'unknown'}->{row.final_grade or 'unknown'}",
                notes=f"record_id={int(row.id or 0)}",
                lineage={"sources": [{"table": "grading_reconciliation_record", "record_id": int(row.id or 0)}]},
            )
        )
    for row in sorted(latest_perf, key=lambda item: item.grader):
        grader_slug = sanitize_report_filename(row.grader).replace("-", "_")
        pieces.extend(
            [
                _metric_piece(
                    "grader_performance.latest",
                    "GRADER_PERFORMANCE",
                    f"grader::{grader_slug}::submission_count",
                    integer_value=int(row.submission_count),
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
                _metric_piece(
                    "grader_performance.latest",
                    "GRADER_PERFORMANCE",
                    f"grader::{grader_slug}::average_roi_delta",
                    decimal_value=row.average_roi_delta,
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
                _metric_piece(
                    "grader_performance.latest",
                    "GRADER_PERFORMANCE",
                    f"grader::{grader_slug}::average_turnaround_days",
                    decimal_value=row.average_turnaround_days,
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
            ]
        )
    return SUMMARY_HEADERS, pieces


def _recommendation_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    rows = session.exec(select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)).all()
    latest_rows = _latest_rows(
        list(rows),
        key_fn=lambda row: _scoped_key(row.grading_candidate_id, row.inventory_item_id, row.canonical_comic_issue_id),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    active = [row for row in latest_rows if row.recommendation_status == "ACTIVE"]
    expected = [row.expected_roi for row in active if row.expected_roi is not None]
    confidence = [row.confidence_score for row in active if row.confidence_score is not None]
    pieces: RowPieces = []
    for action in sorted({str(row.recommended_action) for row in active} | {"GRADE", "HOLD_RAW", "REVIEW_MANUALLY", "NOT_RECOMMENDED"}):
        pieces.append(
            _metric_piece(
                "grading_recommendation.action_counts",
                "GRADING_RECOMMENDATION_ACTION",
                f"recommended_action::{action.lower()}",
                integer_value=sum(1 for row in active if row.recommended_action == action),
                lineage={"sources": [{"table": "grading_recommendation", "aggregation": "latest_count_by_action"}]},
            )
        )
    pieces.extend(
        [
            _metric_piece(
                "grading_recommendation.rollups",
                "GRADING_RECOMMENDATION_ROLLUP",
                "elite_opportunity_count",
                integer_value=sum(1 for row in active if row.recommendation_strength == "ELITE"),
                lineage={"sources": [{"table": "grading_recommendation", "aggregation": "latest_elite_count"}]},
            ),
            _metric_piece(
                "grading_recommendation.rollups",
                "GRADING_RECOMMENDATION_ROLLUP",
                "high_risk_recommendation_count",
                integer_value=sum(1 for row in active if row.risk_level == "HIGH"),
                lineage={"sources": [{"table": "grading_recommendation", "aggregation": "latest_high_risk_count"}]},
            ),
            _metric_piece(
                "grading_recommendation.rollups",
                "GRADING_RECOMMENDATION_ROLLUP",
                "average_expected_roi",
                decimal_value=(sum(expected, ZERO) / Decimal(len(expected))) if expected else None,
                lineage={"sources": [{"table": "grading_recommendation", "aggregation": "latest_average_expected_roi"}]},
            ),
            _metric_piece(
                "grading_recommendation.rollups",
                "GRADING_RECOMMENDATION_ROLLUP",
                "average_confidence_score",
                decimal_value=(sum(confidence, ZERO) / Decimal(len(confidence))) if confidence else None,
                lineage={"sources": [{"table": "grading_recommendation", "aggregation": "latest_average_confidence_score"}]},
            ),
        ]
    )
    for grader in sorted({str(row.recommended_grader) for row in active if row.recommended_grader}):
        pieces.append(
            _metric_piece(
                "grading_recommendation.grader_counts",
                "GRADING_RECOMMENDATION_GRADER",
                f"recommended_grader::{grader.lower()}",
                integer_value=sum(1 for row in active if row.recommended_grader == grader),
                lineage={"sources": [{"table": "grading_recommendation", "aggregation": "latest_count_by_recommended_grader"}]},
            )
        )
    return SUMMARY_HEADERS, pieces


def _risk_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    rows = session.exec(select(GradingRiskSnapshot).where(GradingRiskSnapshot.owner_user_id == owner_user_id)).all()
    latest_rows = _latest_rows(
        list(rows),
        key_fn=lambda row: _scoped_key(row.grading_candidate_id, row.inventory_item_id, row.canonical_comic_issue_id, row.recommendation_id),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    pieces: RowPieces = []
    for risk_level in sorted({str(row.overall_risk_level) for row in latest_rows} | {"LOW", "MEDIUM", "HIGH", "EXTREME"}):
        pieces.append(
            _metric_piece(
                "grading_risk.level_counts",
                "GRADING_RISK_LEVEL",
                f"risk_level::{risk_level.lower()}",
                integer_value=sum(1 for row in latest_rows if row.overall_risk_level == risk_level),
                lineage={"sources": [{"table": "grading_risk_snapshot", "aggregation": "latest_count_by_risk_level"}]},
            )
        )
    for confidence_level in sorted({str(row.overall_confidence_level) for row in latest_rows} | {"LOW", "MEDIUM", "HIGH"}):
        pieces.append(
            _metric_piece(
                "grading_risk.confidence_counts",
                "GRADING_RISK_CONFIDENCE",
                f"confidence_level::{confidence_level.lower()}",
                integer_value=sum(1 for row in latest_rows if row.overall_confidence_level == confidence_level),
                lineage={"sources": [{"table": "grading_risk_snapshot", "aggregation": "latest_count_by_confidence_level"}]},
            )
        )
    adjusted = [row.risk_adjusted_roi for row in latest_rows if row.risk_adjusted_roi is not None]
    for metric_key, attr in (
        ("average_liquidity_risk_score", "liquidity_risk_score"),
        ("average_spread_volatility_score", "spread_volatility_score"),
        ("average_roi_volatility_score", "roi_volatility_score"),
        ("average_grader_variability_score", "grader_variability_score"),
        ("average_reconciliation_variance_score", "reconciliation_variance_score"),
    ):
        values = [getattr(row, attr) for row in latest_rows if getattr(row, attr) is not None]
        pieces.append(
            _metric_piece(
                "grading_risk.volatility",
                "GRADING_RISK_VOLATILITY",
                metric_key,
                decimal_value=(sum(values, ZERO) / Decimal(len(values))) if values else None,
                lineage={"sources": [{"table": "grading_risk_snapshot", "aggregation": f"latest_average::{attr}"}]},
            )
        )
    pieces.append(
        _metric_piece(
            "grading_risk.rollups",
            "GRADING_RISK_ROLLUP",
            "average_risk_adjusted_roi",
            decimal_value=(sum(adjusted, ZERO) / Decimal(len(adjusted))) if adjusted else None,
            lineage={"sources": [{"table": "grading_risk_snapshot", "aggregation": "latest_average_risk_adjusted_roi"}]},
        )
    )
    warning_counts: dict[str, int] = {}
    for row in latest_rows:
        for flag in row.warning_flags_json or []:
            warning_counts[str(flag)] = warning_counts.get(str(flag), 0) + 1
    for flag, count in sorted(warning_counts.items()):
        pieces.append(
            _metric_piece(
                "grading_risk.warning_flags",
                "GRADING_RISK_WARNING_FLAG",
                f"warning_flag::{sanitize_report_filename(flag).replace('-', '_')}",
                integer_value=count,
                text_value=flag,
                lineage={"sources": [{"table": "grading_risk_snapshot", "aggregation": "latest_warning_flag_count"}]},
            )
        )
    return SUMMARY_HEADERS, pieces


def _dashboard_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    snapshot = session.exec(
        select(DealerGradingDashboardSnapshot)
        .where(DealerGradingDashboardSnapshot.owner_user_id == owner_user_id)
        .order_by(
            col(DealerGradingDashboardSnapshot.snapshot_date).desc(),
            col(DealerGradingDashboardSnapshot.created_at).desc(),
            col(DealerGradingDashboardSnapshot.id).desc(),
        )
    ).first()
    pieces: RowPieces = []
    if snapshot is None:
        return SUMMARY_HEADERS, [
            _metric_piece(
                "dealer_grading_dashboard.snapshot",
                "DEALER_GRADING_DASHBOARD",
                "snapshot_materialized",
                integer_value=0,
                notes="No persisted grading dashboard snapshot available.",
                lineage={"sources": [{"table": "dealer_grading_dashboard_snapshot", "aggregation": "latest_snapshot_lookup"}]},
            )
        ]
    for metric_key, integer_value, decimal_value in (
        ("active_candidate_count", snapshot.active_candidate_count, None),
        ("ready_for_submission_count", snapshot.ready_for_submission_count, None),
        ("submitted_candidate_count", snapshot.submitted_candidate_count, None),
        ("graded_candidate_count", snapshot.graded_candidate_count, None),
        ("elite_recommendation_count", snapshot.elite_recommendation_count, None),
        ("high_risk_candidate_count", snapshot.high_risk_candidate_count, None),
        ("low_confidence_candidate_count", snapshot.low_confidence_candidate_count, None),
        ("active_submission_batch_count", snapshot.active_submission_batch_count, None),
        ("average_estimated_roi", None, snapshot.average_estimated_roi),
        ("average_risk_adjusted_roi", None, snapshot.average_risk_adjusted_roi),
        ("grading_pipeline_value", None, snapshot.grading_pipeline_value),
        ("estimated_total_submission_cost", None, snapshot.estimated_total_submission_cost),
        ("expected_total_profit", None, snapshot.expected_total_profit),
    ):
        pieces.append(
            _metric_piece(
                "dealer_grading_dashboard.snapshot",
                "DEALER_GRADING_DASHBOARD_SNAPSHOT",
                metric_key,
                integer_value=integer_value,
                decimal_value=decimal_value,
                notes=f"snapshot_id={int(snapshot.id or 0)}",
                lineage={"sources": [{"table": "dealer_grading_dashboard_snapshot", "snapshot_id": int(snapshot.id or 0)}]},
            )
        )
    metric_rows = session.exec(
        select(DealerGradingDashboardMetric)
        .where(DealerGradingDashboardMetric.dashboard_snapshot_id == int(snapshot.id or 0))
        .order_by(col(DealerGradingDashboardMetric.metric_key).asc(), col(DealerGradingDashboardMetric.id).asc())
    ).all()
    for row in metric_rows:
        metric_key_slug = sanitize_report_filename(str(row.metric_key)).replace("-", "_")
        pieces.append(
            _metric_piece(
                "dealer_grading_dashboard.metric_rows",
                "DEALER_GRADING_DASHBOARD_METRIC",
                f"child_metric::{metric_key_slug}",
                decimal_value=row.metric_value_decimal,
                text_value=row.metric_value_text,
                notes=f"metric_id={int(row.id or 0)}",
                lineage={"sources": [{"table": "dealer_grading_dashboard_metric", "metric_id": int(row.id or 0)}]},
            )
        )
    alert_rows = session.exec(
        select(DealerGradingDashboardAlert)
        .where(DealerGradingDashboardAlert.dashboard_snapshot_id == int(snapshot.id or 0))
        .order_by(col(DealerGradingDashboardAlert.alert_type).asc(), col(DealerGradingDashboardAlert.id).asc())
    ).all()
    alert_counts: dict[str, int] = {}
    for row in alert_rows:
        alert_counts[str(row.alert_type)] = alert_counts.get(str(row.alert_type), 0) + 1
    for alert_type, count in sorted(alert_counts.items()):
        pieces.append(
            _metric_piece(
                "dealer_grading_dashboard.alerts",
                "DEALER_GRADING_DASHBOARD_ALERT",
                f"alert_type::{sanitize_report_filename(alert_type).replace('-', '_')}",
                integer_value=count,
                text_value=alert_type,
                lineage={"sources": [{"table": "dealer_grading_dashboard_alert", "snapshot_id": int(snapshot.id or 0)}]},
            )
        )
    feed_rows = session.exec(
        select(DealerGradingDashboardFeedEvent)
        .where(DealerGradingDashboardFeedEvent.owner_user_id == owner_user_id)
        .order_by(col(DealerGradingDashboardFeedEvent.event_type).asc(), col(DealerGradingDashboardFeedEvent.id).asc())
    ).all()
    feed_counts: dict[str, int] = {}
    for row in feed_rows:
        feed_counts[str(row.event_type)] = feed_counts.get(str(row.event_type), 0) + 1
    for event_type, count in sorted(feed_counts.items()):
        pieces.append(
            _metric_piece(
                "dealer_grading_dashboard.feed",
                "DEALER_GRADING_DASHBOARD_FEED",
                f"event_type::{sanitize_report_filename(event_type).replace('-', '_')}",
                integer_value=count,
                text_value=event_type,
                lineage={"sources": [{"table": "dealer_grading_dashboard_feed_event", "aggregation": "count_by_event_type"}]},
            )
        )
    return SUMMARY_HEADERS, pieces


def _grader_performance_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    latest_rows = _latest_rows(
        list(
            session.exec(select(GraderPerformanceSnapshot).where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)).all()
        ),
        key_fn=lambda row: str(row.grader),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    pieces: RowPieces = []
    for row in sorted(latest_rows, key=lambda item: item.grader):
        grader_slug = sanitize_report_filename(row.grader).replace("-", "_")
        pieces.extend(
            [
                _metric_piece(
                    "grader_performance.summary",
                    "GRADER_PERFORMANCE_SUMMARY",
                    f"grader::{grader_slug}::submission_count",
                    integer_value=int(row.submission_count),
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
                _metric_piece(
                    "grader_performance.summary",
                    "GRADER_PERFORMANCE_SUMMARY",
                    f"grader::{grader_slug}::grading_accuracy_above",
                    integer_value=int(row.above_expectation_count),
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
                _metric_piece(
                    "grader_performance.summary",
                    "GRADER_PERFORMANCE_SUMMARY",
                    f"grader::{grader_slug}::grading_accuracy_below",
                    integer_value=int(row.below_expectation_count),
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
                _metric_piece(
                    "grader_performance.summary",
                    "GRADER_PERFORMANCE_SUMMARY",
                    f"grader::{grader_slug}::average_roi_delta",
                    decimal_value=row.average_roi_delta,
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
                _metric_piece(
                    "grader_performance.summary",
                    "GRADER_PERFORMANCE_SUMMARY",
                    f"grader::{grader_slug}::average_turnaround_days",
                    decimal_value=row.average_turnaround_days,
                    text_value=row.grader,
                    lineage={"sources": [{"table": "grader_performance_snapshot", "snapshot_id": int(row.id or 0)}]},
                ),
            ]
        )
    if not pieces:
        pieces.append(
            _metric_piece(
                "grader_performance.summary",
                "GRADER_PERFORMANCE_SUMMARY",
                "grader_snapshot_count",
                integer_value=0,
                notes="No grader performance snapshots available.",
                lineage={"sources": [{"table": "grader_performance_snapshot", "aggregation": "latest_per_grader"}]},
            )
        )
    return SUMMARY_HEADERS, pieces


def _collect_report_matrix(
    session: Session,
    *,
    owner_user_id: int,
    report_type: str,
    params_blob: dict[str, Any],
) -> tuple[tuple[str, ...], RowPieces]:
    _ = params_blob
    if report_type == "grading_candidate_summary":
        return _candidate_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grading_roi_summary":
        return _roi_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grading_submission_summary":
        return _submission_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grading_reconciliation_summary":
        return _reconciliation_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grading_recommendation_summary":
        return _recommendation_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grading_risk_summary":
        return _risk_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grading_dashboard_summary":
        return _dashboard_summary_rows(session, owner_user_id=owner_user_id)
    if report_type == "grader_performance_summary":
        return _grader_performance_summary_rows(session, owner_user_id=owner_user_id)
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unsupported grading report_type")


def _stable_piece_order(header: tuple[str, ...], pieces: RowPieces) -> RowPieces:
    return sorted(pieces, key=lambda piece: tuple(piece[2][column] for column in header))


def _persist_csv_bundle(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_row_id: int,
    header: tuple[str, ...],
    pieces_sorted: RowPieces,
    report_slug: str,
) -> GradingOperationalReportRunDetailRead:
    row_cells_only = [{header_name: cells[header_name] for header_name in header} for _, _, cells, __ in pieces_sorted]
    csv_text = render_csv(header, row_cells_only)
    insert_items: list[GradingOperationalReportItem] = []
    for idx, (lineage_domain, _, cells, lineage_extra) in enumerate(pieces_sorted, start=1):
        row_cs = _row_checksum(cells)
        lineage_blob = dict(sorted({"domain": lineage_domain, **_json_safe(lineage_extra)}.items()))
        lk_seed = cells.get("metric_key") or cells.get(header[-1]) or f"row_{idx}"
        lineage_key_safe = (f"{lineage_domain}:{lk_seed}")[:248]
        insert_items.append(
            GradingOperationalReportItem(
                grading_operational_report_run_id=int(run_row_id),
                row_number=idx,
                lineage_domain=lineage_domain[:128],
                lineage_key=lineage_key_safe,
                lineage_json=lineage_blob,
                row_checksum=row_cs,
                created_at=utc_now(),
            )
        )
    stamp = utc_now().date().isoformat()
    slug_seg = sanitize_report_filename(report_slug)
    fname = re.sub(r"_+", "_", f"comic_os_{slug_seg}_{stamp}_run_{run_row_id}.csv").replace("-.csv", ".csv")
    csv_checksum = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    root = settings.operational_reports_storage_root / "grading"
    rel_dir = f"{owner_user_id}/{int(run_row_id)}"
    dir_path = root / Path(rel_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    abs_path = dir_path / fname
    abs_path.write_text(csv_text, encoding="utf-8")
    storage_rel = f"{rel_dir}/{fname}".replace("\\", "/")
    session.add_all(insert_items)
    session.add(
        GradingOperationalReportFile(
            grading_operational_report_run_id=int(run_row_id),
            file_name=fname,
            file_type="csv",
            storage_path=storage_rel,
            checksum=csv_checksum,
            row_count=len(insert_items),
            created_at=utc_now(),
        )
    )
    run_ref = session.get(GradingOperationalReportRun, int(run_row_id))
    if run_ref is None:
        raise RuntimeError("grading report run vanished during persistence")
    run_ref.status = "COMPLETED"
    run_ref.csv_row_count = len(insert_items)
    run_ref.checksum = csv_checksum
    run_ref.failure_reason = None
    run_ref.completed_at = utc_now()
    session.add(run_ref)
    session.commit()
    return build_run_detail(session, owner_user_id=owner_user_id, grading_operational_report_run_id=int(run_row_id))


def generate_grading_report(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: GradingOperationalReportGeneratePayload | dict[str, Any],
) -> tuple[GradingOperationalReportRunDetailRead, bool]:
    blob = payload if isinstance(payload, GradingOperationalReportGeneratePayload) else GradingOperationalReportGeneratePayload.model_validate(payload)
    report_type = str(blob.report_type)
    if report_type not in GRADING_OPERATIONAL_REPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid grading report_type")
    generation_params = normalize_generation_params(blob.generation_params)
    replay_key = blob.replay_key.strip() if blob.replay_key else None
    duplicate = replay_lookup(session, owner_user_id=owner_user_id, replay_key=replay_key)
    if duplicate is not None:
        session.refresh(duplicate)
        return build_run_detail(session, owner_user_id=owner_user_id, grading_operational_report_run_id=int(duplicate.id)), True
    ts = utc_now()
    run = GradingOperationalReportRun(
        owner_user_id=owner_user_id,
        report_type=report_type,
        status="RUNNING",
        replay_key=replay_key,
        generation_params_json=generation_params,
        checksum=None,
        csv_row_count=0,
        failure_reason=None,
        created_at=ts,
        started_at=ts,
        completed_at=None,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if replay_key:
            hit = replay_lookup(session, owner_user_id=owner_user_id, replay_key=replay_key)
            if hit is not None:
                session.refresh(hit)
                return build_run_detail(session, owner_user_id=owner_user_id, grading_operational_report_run_id=int(hit.id)), True
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="grading report replay collision")
    run_id = int(run.id)
    try:
        header, pieces = _collect_report_matrix(session, owner_user_id=owner_user_id, report_type=report_type, params_blob=generation_params)
        ordered = _stable_piece_order(header, pieces)
        return (
            _persist_csv_bundle(
                session,
                settings,
                owner_user_id=owner_user_id,
                run_row_id=run_id,
                header=header,
                pieces_sorted=ordered,
                report_slug=report_type,
            ),
            False,
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        survivor = session.get(GradingOperationalReportRun, run_id)
        if survivor is not None:
            survivor.status = "FAILED"
            survivor.failure_reason = "grading report generation failed"
            survivor.completed_at = utc_now()
            session.add(survivor)
            session.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="grading report generation failed")


def resolve_grading_report_download_path(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    grading_operational_report_run_id: int,
    grading_operational_report_file_id: int | None,
    allow_ops_any_owner: bool = False,
) -> tuple[Path, GradingOperationalReportFile]:
    row = session.get(GradingOperationalReportRun, grading_operational_report_run_id)
    if row is None or (int(row.owner_user_id) != owner_user_id and not allow_ops_any_owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report run not found")
    if grading_operational_report_file_id is not None:
        frow = session.get(GradingOperationalReportFile, grading_operational_report_file_id)
        if frow is None or int(frow.grading_operational_report_run_id) != grading_operational_report_run_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report file not found")
    else:
        frow = session.exec(
            select(GradingOperationalReportFile)
            .where(GradingOperationalReportFile.grading_operational_report_run_id == grading_operational_report_run_id)
            .order_by(col(GradingOperationalReportFile.id).asc())
        ).first()
        if frow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report file not found")
    root = settings.operational_reports_storage_root / "grading"
    abs_path = (root / Path(str(frow.storage_path))).resolve()
    try:
        abs_path.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="grading report path escaped root") from exc
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report artifact missing")
    return abs_path, frow
