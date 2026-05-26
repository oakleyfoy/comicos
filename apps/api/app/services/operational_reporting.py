"""P36-08 deterministic operational reporting (CSV export; lineage items; replay-safe)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ConventionEvent,
    ConventionInventoryAssignment,
    ConventionSaleSession,
    DealerDashboardAlert,
    DealerDashboardFeedEvent,
    DealerDashboardMetric,
    DealerDashboardSnapshot,
    InventoryLiquiditySnapshot,
    Listing,
    ListingExportRun,
    ListingExportRunItem,
    ListingImage,
    ListingInventoryLink,
    ListingStalenessEvent,
    ListingVelocitySnapshot,
    OperationalReportFile,
    OperationalReportItem,
    OperationalReportRun,
    SaleRecord,
)
from app.schemas.listing_export import EXPORT_CHANNELS
from app.schemas.operational_reporting import (
    OPERATIONAL_REPORT_TYPES,
    OperationalReportFileRead,
    OperationalReportGeneratePayload,
    OperationalReportGenerationParams,
    OperationalReportItemRead,
    OperationalReportRunDetailRead,
    OperationalReportRunListResponse,
    OperationalReportRunRead,
    OperationalReportingDashboardRollup,
)
from app.services import convention_operations as convention_operations_service
from app.services import dealer_dashboard as dealer_dashboard_service
from app.services import listing_export as listing_export_service
from app.services import listing_intelligence as listing_intelligence_service
from app.services import liquidity_engine as liquidity_engine_service
from app.services.reports_export import render_csv, sanitize_report_filename

GENERATOR_VERSION = "p36-08:v1"

RowPieces = list[tuple[str, str, dict[str, str], dict[str, Any]]]

LISTING_HEALTH_SOURCE_LAYERS: dict[str, list[str]] = {
    "active_ready_missing_primary_visual": ["listing_registry.listing_image"],
    "active_ready_missing_pricing": ["listing_registry.listing_price_fields"],
    "convention_assignment_inventory_stale_signal_rows": ["convention.assignments", "listing_staleness_event"],
    "intel_incomplete_registry_listings_scope": ["listing_intelligence.snapshot"],
    "latest_liquidity_snapshot_low_or_illiquid_rows": ["inventory_liquidity_snapshot"],
    "recent_weak_intel_rows_window": ["listing_intelligence.snapshot"],
    "staleness_risk_listings_intel": ["listing_intelligence.snapshot"],
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_report_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _median_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / Decimal("2")


def normalize_generation_params(payload: OperationalReportGenerationParams | dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"generator_version": GENERATOR_VERSION}
    if isinstance(payload, OperationalReportGenerationParams):
        blob = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        blob = OperationalReportGenerationParams.model_validate(payload).model_dump(mode="json")
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid generation params")

    normalized: dict[str, Any] = {"generator_version": GENERATOR_VERSION}
    if blob.get("sale_date_from"):
        normalized["sale_date_from"] = str(blob["sale_date_from"])[:10]
    if blob.get("sale_date_to"):
        normalized["sale_date_to"] = str(blob["sale_date_to"])[:10]
    return dict(sorted(normalized.items()))


def replay_lookup(session: Session, *, owner_user_id: int, replay_key: str | None) -> OperationalReportRun | None:
    if not replay_key:
        return None
    stmt = select(OperationalReportRun).where(
        OperationalReportRun.owner_user_id == owner_user_id,
        OperationalReportRun.replay_key == replay_key,
    )
    return session.exec(stmt).first()


def _coerce_run_read(row: OperationalReportRun) -> OperationalReportRunRead:
    gp = row.generation_params_json or {}
    if not isinstance(gp, dict):
        gp = {}
    return OperationalReportRunRead(
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


def _coerce_file_read(row: OperationalReportFile) -> OperationalReportFileRead:
    return OperationalReportFileRead.model_validate(row, from_attributes=True)


def _coerce_item_read(row: OperationalReportItem) -> OperationalReportItemRead:
    return OperationalReportItemRead.model_validate(row, from_attributes=True)


def build_run_detail(
    session: Session,
    *,
    owner_user_id: int,
    operational_report_run_id: int,
    include_children: bool = True,
    allow_cross_owner_ops: bool = False,
) -> OperationalReportRunDetailRead:
    row = session.get(OperationalReportRun, operational_report_run_id)
    if row is None or (int(row.owner_user_id) != owner_user_id and not allow_cross_owner_ops):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")

    base = _coerce_run_read(row).model_dump()
    if not include_children:
        return OperationalReportRunDetailRead.model_validate({**base, "items": [], "files": []})

    item_rows = session.exec(
        select(OperationalReportItem)
        .where(OperationalReportItem.operational_report_run_id == operational_report_run_id)
        .order_by(col(OperationalReportItem.row_number).asc(), col(OperationalReportItem.id).asc()),
    ).all()

    files = session.exec(
        select(OperationalReportFile)
        .where(OperationalReportFile.operational_report_run_id == operational_report_run_id)
        .order_by(col(OperationalReportFile.id).asc()),
    ).all()
    return OperationalReportRunDetailRead.model_validate(
        {
            **base,
            "items": [_coerce_item_read(ir).model_dump() for ir in item_rows],
            "files": [_coerce_file_read(fr).model_dump() for fr in files],
        },
    )


def list_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    report_type: str | None,
    status: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[OperationalReportRun], int]:
    q = select(OperationalReportRun).where(OperationalReportRun.owner_user_id == owner_user_id)
    c = select(func.count(col(OperationalReportRun.id))).where(
        OperationalReportRun.owner_user_id == owner_user_id,
    )
    if report_type:
        q = q.where(OperationalReportRun.report_type == report_type)
        c = c.where(OperationalReportRun.report_type == report_type)
    if status:
        q = q.where(OperationalReportRun.status == status.upper())
        c = c.where(OperationalReportRun.status == status.upper())
    if created_from is not None:
        q = q.where(OperationalReportRun.created_at >= created_from)
        c = c.where(OperationalReportRun.created_at >= created_from)
    if created_to is not None:
        q = q.where(OperationalReportRun.created_at <= created_to)
        c = c.where(OperationalReportRun.created_at <= created_to)

    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(OperationalReportRun.created_at).desc())
        .order_by(col(OperationalReportRun.id).desc())
        .offset(offset)
        .limit(limit),
    ).all()
    return list(rows), total


def list_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    report_type: str | None,
    status: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[OperationalReportRun], int]:
    q = select(OperationalReportRun)
    c = select(func.count(col(OperationalReportRun.id))).select_from(OperationalReportRun)
    if owner_user_id is not None:
        q = q.where(OperationalReportRun.owner_user_id == owner_user_id)
        c = c.where(OperationalReportRun.owner_user_id == owner_user_id)
    if report_type:
        q = q.where(OperationalReportRun.report_type == report_type)
        c = c.where(OperationalReportRun.report_type == report_type)
    if status:
        normalized = status.upper()
        q = q.where(OperationalReportRun.status == normalized)
        c = c.where(OperationalReportRun.status == normalized)
    if created_from is not None:
        q = q.where(OperationalReportRun.created_at >= created_from)
        c = c.where(OperationalReportRun.created_at >= created_from)
    if created_to is not None:
        q = q.where(OperationalReportRun.created_at <= created_to)
        c = c.where(OperationalReportRun.created_at <= created_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(OperationalReportRun.created_at).desc())
        .order_by(col(OperationalReportRun.id).desc())
        .offset(offset)
        .limit(limit),
    ).all()
    return list(rows), total


def dashboard_rollup_owner(session: Session, *, owner_user_id: int, window: int = 14) -> OperationalReportingDashboardRollup:
    cutoff = utc_now() - timedelta(days=max(window, 1))
    stmt_recent = (
        select(OperationalReportRun)
        .where(
            OperationalReportRun.owner_user_id == owner_user_id,
            OperationalReportRun.created_at >= cutoff,
        )
        .order_by(col(OperationalReportRun.created_at).desc(), col(OperationalReportRun.id).desc())
        .limit(12)
    )
    recent_rows = session.exec(stmt_recent).all()
    stmt_failed = (
        select(OperationalReportRun)
        .where(
            OperationalReportRun.owner_user_id == owner_user_id,
            OperationalReportRun.status == "FAILED",
        )
        .order_by(col(OperationalReportRun.created_at).desc(), col(OperationalReportRun.id).desc())
        .limit(8),
    )
    failed_rows = session.exec(stmt_failed).all()
    return OperationalReportingDashboardRollup(
        recent_runs=[_coerce_run_read(r) for r in recent_rows],
        failed_runs=[_coerce_run_read(r) for r in failed_rows],
    )


def _parse_sale_dates(params_blob: dict[str, Any]) -> tuple[date | None, date | None]:
    raw_from = params_blob.get("sale_date_from") if isinstance(params_blob, dict) else None
    raw_to = params_blob.get("sale_date_to") if isinstance(params_blob, dict) else None
    sf = datetime.fromisoformat(str(raw_from)[:10]).date() if raw_from else None
    st = datetime.fromisoformat(str(raw_to)[:10]).date() if raw_to else None
    if sf and st and sf > st:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="sale_date_from after sale_date_to")
    return sf, st


def _sale_record_filters(owner_user_id: int, *, sale_from: date | None, sale_to: date | None):
    conds = [
        SaleRecord.owner_user_id == owner_user_id,
        SaleRecord.status == "RECORDED",
    ]
    if sale_from is not None:
        conds.append(SaleRecord.sale_date >= sale_from)
    if sale_to is not None:
        conds.append(SaleRecord.sale_date <= sale_to)
    return and_(*conds)


def _listing_summary_rows(session: Session, *, owner_user_id: int) -> tuple[tuple[str, ...], RowPieces]:
    header = ("metric_family", "metric_key", "metric_value")
    pieces: RowPieces = []
    statuses = ("ACTIVE", "ARCHIVED", "CANCELLED", "DRAFT", "READY", "SOLD")
    for st in statuses:
        cnt = int(
            session.exec(
                select(func.count(col(Listing.id))).where(
                    Listing.owner_user_id == owner_user_id,
                    Listing.status == st,
                ),
            ).one(),
        )
        mk = f"listing_status::{st.lower()}"
        cells = {"metric_family": "LISTING_REGISTRY", "metric_key": mk, "metric_value": str(cnt)}
        lineage = {"sources": [{"system": "listing_registry", "aggregation": "count_by_status"}], "generator": GENERATOR_VERSION}
        pieces.append(("listing_registry.summary", mk, cells, lineage))

    intel = listing_intelligence_service.build_listing_intelligence_dashboard_summary(
        session, owner_user_id=owner_user_id
    )

    supplemental = sorted(
        {
            "export_ready_listings_intel": intel.export_ready_count,
            "incomplete_listings_intel": intel.incomplete_listing_count,
            "staleness_risk_listings_intel": intel.stale_risk_count,
            "strong_intel_listings": intel.strong_listing_count,
        }.items(),
        key=lambda kv: kv[0],
    )

    for mk, mv in supplemental:
        cells = {"metric_family": "LISTING_INTELLIGENCE_ROLLUP", "metric_key": mk, "metric_value": str(int(mv))}
        lineage = {
            "sources": [{"system": "listing_intelligence", "method": "build_listing_intelligence_dashboard_summary"}],
            "generator": GENERATOR_VERSION,
        }
        pieces.append(("listing_intelligence.summary", mk, cells, lineage))

    avg = intel.average_completeness_score
    cells_avg = {"metric_family": "LISTING_INTELLIGENCE_ROLLUP", "metric_key": "average_completeness_score", "metric_value": _decimal_str(avg)}
    pieces.append(
        (
            "listing_intelligence.summary",
            "average_completeness_score",
            cells_avg,
            {"sources": [{"system": "listing_intelligence", "metric": "average_completeness_score"}]},
        ),
    )

    pieces.sort(key=lambda p: (p[2]["metric_family"], p[2]["metric_key"]))
    return header, pieces


def _sales_summary_rows(session: Session, *, owner_user_id: int, params_blob: dict[str, Any]):
    cols = ("metric_family", "metric_key", "metric_value_decimal", "metric_value_integer", "sale_window_from", "sale_window_to")
    sf, st = _parse_sale_dates(params_blob)

    filt = _sale_record_filters(owner_user_id, sale_from=sf, sale_to=st)
    totals = session.exec(
        select(
            func.count(col(SaleRecord.id)),
            func.coalesce(func.sum(SaleRecord.gross_sale_amount), Decimal("0")),
            func.coalesce(func.sum(SaleRecord.net_proceeds_amount), Decimal("0")),
            func.coalesce(func.sum(SaleRecord.realized_profit_amount), Decimal("0")),
        ).where(filt),
    ).one()

    cnt, gross, net, profit = totals
    window_from = sf.isoformat() if sf else ""
    window_to = st.isoformat() if st else ""
    rows: RowPieces = []

    def pack(metric_key: str, dec_val: Decimal | None, int_val: int | None):
        rows.append(
            (
                "sales_ledger.rollups",
                metric_key,
                {
                    "metric_family": "SALES_LEDGER",
                    "metric_key": metric_key,
                    "metric_value_decimal": "" if dec_val is None else _decimal_str(dec_val),
                    "metric_value_integer": "" if int_val is None else str(int_val),
                    "sale_window_from": window_from,
                    "sale_window_to": window_to,
                },
                {"sources": [{"system": "sales_ledger", "aggregation": "sql_sum_or_count"}], "generator": GENERATOR_VERSION},
            ),
        )

    pack("completed_sale_count", None, int(cnt))
    pack("gross_sales_total", gross, None)
    pack("net_proceeds_total", net, None)
    pack("realized_profit_total", profit, None)

    channels = session.exec(
        select(SaleRecord.channel, func.count(col(SaleRecord.id)))
        .where(filt)
        .group_by(SaleRecord.channel)
        .order_by(SaleRecord.channel.asc()),
    ).all()

    for channel, ct in channels:
        ch = str(channel)
        mk = f"sale_channel_count::{ch.lower()}"
        rows.append(
            (
                "sales_ledger.channels",
                mk,
                {
                    "metric_family": "SALES_LEDGER",
                    "metric_key": mk,
                    "metric_value_decimal": "",
                    "metric_value_integer": str(int(ct)),
                    "sale_window_from": window_from,
                    "sale_window_to": window_to,
                },
                {"sources": [{"system": "sales_ledger", "aggregation": "count_by_channel", "channel": ch}]},
            ),
        )

    rows.sort(key=lambda r: r[2]["metric_key"])
    return cols, rows


def _liquidity_summary_rows(session: Session, *, owner_user_id: int):
    cols = ("metric_family", "metric_key", "metric_value_decimal", "metric_value_integer", "liquidity_snapshot_date")
    dash = liquidity_engine_service.dashboard_summary_owner(session, owner_user_id=owner_user_id)
    max_date = session.exec(
        select(func.max(col(InventoryLiquiditySnapshot.snapshot_date))).where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
        ),
    ).one()

    sd = ""
    counts: dict[str, int] = {}
    if max_date is not None:
        sd = max_date.isoformat()
        tuples = session.exec(
            select(InventoryLiquiditySnapshot.liquidity_status, func.count(col(InventoryLiquiditySnapshot.id)))
            .where(
                InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
                InventoryLiquiditySnapshot.snapshot_date == max_date,
            )
            .group_by(InventoryLiquiditySnapshot.liquidity_status)
            .order_by(InventoryLiquiditySnapshot.liquidity_status.asc()),
        ).all()
        counts = {str(status): int(ct) for status, ct in tuples}

    rows: RowPieces = []
    for lk in sorted(counts.keys()):
        mk = f"liquidity_snapshot_count::{lk.lower()}"
        rows.append(
            (
                "liquidity.snapshots.latest_date",
                mk,
                {
                    "metric_family": "LIQUIDITY_ENGINE",
                    "metric_key": mk,
                    "metric_value_decimal": "",
                    "metric_value_integer": str(counts[lk]),
                    "liquidity_snapshot_date": sd,
                },
                {"sources": [{"system": "inventory_liquidity_snapshot", "rollup": "liquidity_status"}]},
            ),
        )

    rows.append(
        (
            "liquidity.dashboard",
            "stale_inventory_dashboard_count",
            {
                "metric_family": "LIQUIDITY_ENGINE",
                "metric_key": "stale_inventory_dashboard_count",
                "metric_value_decimal": "",
                "metric_value_integer": str(int(dash.stale_inventory_count)),
                "liquidity_snapshot_date": sd,
            },
            {"sources": [{"system": "liquidity_engine", "method": "dashboard_summary_owner"}]},
        ),
    )
    med = dash.median_days_to_sale
    rows.append(
        (
            "liquidity.dashboard",
            "median_days_to_sale_dashboard",
            {
                "metric_family": "LIQUIDITY_ENGINE",
                "metric_key": "median_days_to_sale_dashboard",
                "metric_value_decimal": "" if med is None else _decimal_str(med),
                "metric_value_integer": "",
                "liquidity_snapshot_date": sd,
            },
            {"sources": [{"system": "liquidity_engine", "metric": "median_days_to_sale"}]},
        ),
    )

    rows.append(
        (
            "liquidity.dashboard",
            "sell_through_pct_dashboard",
            {
                "metric_family": "LIQUIDITY_ENGINE",
                "metric_key": "sell_through_pct_dashboard",
                "metric_value_decimal": _decimal_str(dash.sell_through_pct),
                "metric_value_integer": "",
                "liquidity_snapshot_date": sd,
            },
            {"sources": [{"system": "liquidity_engine", "metric": "sell_through_pct"}]},
        ),
    )

    vmax = session.exec(
        select(func.max(col(ListingVelocitySnapshot.snapshot_date))).where(
            ListingVelocitySnapshot.owner_user_id == owner_user_id,
        ),
    ).one()

    velocity_sd = ""
    relist_avg_txt = ""
    median_velocity_txt = ""

    if vmax is not None:
        velocity_sd = vmax.isoformat()
        rel_avg = session.exec(
            select(func.avg(col(ListingVelocitySnapshot.relist_count))).where(
                ListingVelocitySnapshot.owner_user_id == owner_user_id,
                ListingVelocitySnapshot.snapshot_date == vmax,
            ),
        ).one()

        vals = session.exec(
            select(ListingVelocitySnapshot.days_active).where(
                ListingVelocitySnapshot.owner_user_id == owner_user_id,
                ListingVelocitySnapshot.snapshot_date == vmax,
                ListingVelocitySnapshot.days_active.is_not(None),
            ),
        ).all()
        decimals = [Decimal(str(v)) for v in vals if v is not None]
        mv = _median_decimal(decimals)
        median_velocity_txt = "" if mv is None else _decimal_str(mv)
        relist_avg_txt = "" if rel_avg is None else format(Decimal(str(rel_avg)), "f")

    rows.append(
        (
            "liquidity.velocity",
            "median_days_active_velocity_snapshot_latest",
            {
                "metric_family": "LISTING_VELOCITY_SNAPSHOT",
                "metric_key": "median_days_active_velocity_snapshot_latest",
                "metric_value_decimal": median_velocity_txt,
                "metric_value_integer": "",
                "liquidity_snapshot_date": velocity_sd,
            },
            {"sources": [{"system": "listing_velocity_snapshot", "rollup": "median_days_active"}]},
        ),
    )

    rows.append(
        (
            "liquidity.velocity",
            "avg_relist_count_velocity_latest",
            {
                "metric_family": "LISTING_VELOCITY_SNAPSHOT",
                "metric_key": "avg_relist_count_velocity_latest",
                "metric_value_decimal": relist_avg_txt,
                "metric_value_integer": "",
                "liquidity_snapshot_date": velocity_sd,
            },
            {"sources": [{"system": "listing_velocity_snapshot", "rollup": "avg_relist_count"}]},
        ),
    )

    rows.sort(key=lambda r: (r[2]["metric_family"], r[2]["metric_key"]))
    return cols, rows


def _convention_assignment_bins(session: Session, *, owner_user_id: int) -> tuple[int, int, int]:
    qb = (
        select(ConventionInventoryAssignment)
        .join(
            ConventionEvent,
            ConventionInventoryAssignment.convention_event_id == ConventionEvent.id,
        )
        .where(
            ConventionEvent.owner_user_id == owner_user_id,
            ConventionEvent.status == "ACTIVE",
            ConventionInventoryAssignment.removed_at.is_(None),
        )
    )
    rows = session.exec(qb.order_by(col(ConventionInventoryAssignment.id).asc())).all()
    wall = sum(1 for row in rows if row.assignment_type == "wall")
    showcase = sum(1 for row in rows if row.assignment_type == "showcase")
    bins = sum(1 for row in rows if row.assignment_type == "bin")
    return wall, showcase, bins


def _convention_summary_rows(session: Session, *, owner_user_id: int):
    cols = ("metric_family", "metric_key", "metric_value_integer", "notes")
    dash = convention_operations_service.dashboard_summary_owner(session, owner_user_id=owner_user_id)

    rows: RowPieces = []
    wall, showcase, bins = _convention_assignment_bins(session, owner_user_id=owner_user_id)

    def bump(metric_key: str, count: int, notes: str, domain: str) -> None:
        rows.append(
            (
                domain,
                metric_key,
                {"metric_family": "CONVENTION_OPS", "metric_key": metric_key, "metric_value_integer": str(int(count)), "notes": notes},
                {"sources": [{"system": "convention_operations", "deterministic_dashboard": True}]},
            ),
        )

    bump("active_conventions", dash.active_convention_count, "", "convention.events")
    bump("assigned_unique_inventory_slots", dash.assigned_inventory_count, "", "convention.assignments.unique_inventory")
    bump("assignment_wall_slots", wall, "wall placements", "convention.assignments.wall")
    bump("assignment_showcase_slots", showcase, "", "convention.assignments.showcase")
    bump("assignment_bin_slots", bins, "", "convention.assignments.bin")

    open_ct = session.scalar(
        select(func.count(col(ConventionSaleSession.id))).select_from(ConventionSaleSession).join(
            ConventionEvent,
            ConventionSaleSession.convention_event_id == ConventionEvent.id,
        ).where(
            ConventionSaleSession.status == "OPEN",
            ConventionEvent.status == "ACTIVE",
            ConventionEvent.owner_user_id == owner_user_id,
        ),
    )
    closed_ct = session.scalar(
        select(func.count(col(ConventionSaleSession.id))).select_from(ConventionSaleSession).join(
            ConventionEvent,
            ConventionSaleSession.convention_event_id == ConventionEvent.id,
        ).where(
            ConventionSaleSession.status == "CLOSED",
            ConventionEvent.status == "ACTIVE",
            ConventionEvent.owner_user_id == owner_user_id,
        ),
    )
    bump("open_sale_sessions", int(open_ct or 0), "", "convention.sale_sessions")
    bump("closed_sale_sessions", int(closed_ct or 0), "", "convention.sale_sessions")

    rows.sort(key=lambda r: r[2]["metric_key"])
    return cols, rows


def _slug_channel(label: str) -> str:
    return sanitize_report_filename(label.replace("/", "-"))[:80] or "channel"


def _export_summary_rows(session: Session, *, owner_user_id: int):
    cols = ("metric_family", "metric_key", "metric_value_integer", "notes")
    dash = listing_export_service.dashboard_summary_owner(session, owner_user_id=owner_user_id)

    replay_ct = int(
        session.scalar(
            select(func.count(col(ListingExportRun.id))).where(
                ListingExportRun.owner_user_id == owner_user_id,
                ListingExportRun.status == "COMPLETED",
                col(ListingExportRun.replay_key).is_not(None),
            ),
        ),
    )

    skipped_ct = session.scalar(
        select(func.count(col(ListingExportRunItem.id))).select_from(ListingExportRunItem).join(
            ListingExportRun,
            col(ListingExportRunItem.export_run_id) == col(ListingExportRun.id),
        ).where(ListingExportRun.owner_user_id == owner_user_id, ListingExportRunItem.status == "SKIPPED"),
    )

    failed_exports = session.scalar(
        select(func.sum(col(ListingExportRun.error_count))).where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRun.status == "COMPLETED",
        ),
    )

    rollup = sorted(
        {
            "completed_export_runs_total": dash.completed_run_count,
            "failed_row_sum_completed_runs": int(failed_exports or 0),
            "replay_backed_completed_runs_total": replay_ct,
            "skipped_export_rows_owner_lifetime_dashboard": dash.skipped_rows_lifetime_sum,
            "skipped_row_items_aggregate": int(skipped_ct or 0),
        }.items(),
        key=lambda kv: kv[0],
    )

    rows_payload: RowPieces = []

    for mk, mv in rollup:
        rows_payload.append(
            (
                "listing_export.rollups",
                mk,
                {"metric_family": "LISTING_EXPORT_REGISTRY", "metric_key": mk, "metric_value_integer": str(int(mv)), "notes": ""},
                {"sources": [{"system": "listing_export_run"}]},
            ),
        )

    chan_rows = session.exec(
        select(ListingExportRun.channel, func.count(col(ListingExportRun.id)))
        .where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRun.status == "COMPLETED",
        )
        .group_by(ListingExportRun.channel)
        .order_by(ListingExportRun.channel.asc()),
    ).all()
    emitted: set[str] = set()

    for channel, chan_ct in chan_rows:
        ch_slug = _slug_channel(str(channel))
        mk = f"completed_runs_by_channel::{ch_slug}"
        emitted.add(ch_slug)
        rows_payload.append(
            (
                "listing_export.channel",
                mk,
                {
                    "metric_family": "LISTING_EXPORT_REGISTRY",
                    "metric_key": mk,
                    "metric_value_integer": str(int(chan_ct)),
                    "notes": "completed_runs_scope",
                },
                {"sources": [{"system": "listing_export_run", "channel": str(channel)}]},
            ),
        )

    for seeded in sorted(EXPORT_CHANNELS):
        slug = _slug_channel(seeded)
        if slug in emitted:
            continue
        mk = f"completed_runs_by_channel::{slug}"
        rows_payload.append(
            (
                "listing_export.stub_channel_rows",
                mk,
                {
                    "metric_family": "LISTING_EXPORT_REGISTRY",
                    "metric_key": mk,
                    "metric_value_integer": "0",
                    "notes": "implicit_zero_for_deterministic_channel_grid",
                },
                {"sources": [{"system": "listing_export.registry_stub"}]},
            ),
        )

    rows_payload.sort(key=lambda r: r[2]["metric_key"])
    return cols, rows_payload


def _dealer_dashboard_summary_rows(session: Session, *, owner_user_id: int):
    cols = ("metric_family", "metric_key", "metric_value_text", "metric_value_decimal")
    snap = dealer_dashboard_service.latest_snapshot_for_owner(session, owner_user_id=owner_user_id)

    lineage_hook = ""

    scalar_fields: dict[str, Decimal | str | int] = {}

    if snap is None:
        lineage_hook = "NO_SNAPSHOT"
        scalar_fields = {
            "active_convention_events": 0,
            "active_listing_registry_count": 0,
            "assigned_convention_inventory": 0,
            "export_ready_listings_intel": 0,
            "export_run_count_calendar_30d": 0,
            "failed_export_count_calendar_30d": 0,
            "gross_sales_money_rolling_30d": Decimal("0"),
            "liquidity_inventory_high_snapshots_latest": 0,
            "liquidity_inventory_low_snapshots_latest": 0,
            "net_sales_money_rolling_30d": Decimal("0"),
            "open_sale_session_count": 0,
            "realized_profit_money_rolling_30d": Decimal("0"),
            "stale_listing_union_count": 0,
            "weak_intel_incomplete_registry_listings": 0,
        }
    else:
        lineage_hook = f"snapshot#{int(snap.id)}"
        scalar_fields = {
            "snapshot_id": int(snap.id),
            "active_listing_registry_count": int(snap.active_listing_count),
            "weak_intel_incomplete_registry_listings": int(snap.incomplete_listing_count),
            "export_ready_listings_intel": int(snap.export_ready_count),
            "stale_listing_union_count": int(snap.stale_listing_count),
            "active_convention_events": int(snap.active_convention_count),
            "assigned_convention_inventory": int(snap.assigned_convention_inventory_count),
            "open_sale_session_count": int(snap.open_sale_session_count),
            "gross_sales_money_rolling_30d": snap.gross_sales_30d,
            "net_sales_money_rolling_30d": snap.net_sales_30d,
            "realized_profit_money_rolling_30d": snap.realized_profit_30d,
            "liquidity_inventory_high_snapshots_latest": int(snap.liquidity_high_count),
            "liquidity_inventory_low_snapshots_latest": int(snap.liquidity_low_count),
            "export_run_count_calendar_30d": int(snap.export_run_count_30d),
            "failed_export_count_calendar_30d": int(snap.failed_export_count_30d),
        }

    pieces: RowPieces = []
    for mk, mv in sorted(scalar_fields.items(), key=lambda kv: kv[0]):
        if isinstance(mv, Decimal):
            cells = {
                "metric_family": "DEALER_DASHBOARD",
                "metric_key": mk,
                "metric_value_text": "",
                "metric_value_decimal": _decimal_str(mv),
            }
        else:
            cells = {
                "metric_family": "DEALER_DASHBOARD",
                "metric_key": mk,
                "metric_value_text": str(mv),
                "metric_value_decimal": "",
            }
        lineage = {"sources": [{"system": "dealer_dashboard_snapshot", "hook": lineage_hook}]}
        pieces.append(("dealer_dashboard.scalars", mk, cells, lineage))

    alert_window_since = utc_now() - timedelta(days=90)

    alerts_ct = session.scalar(
        select(func.count(col(DealerDashboardAlert.id))).where(
            DealerDashboardAlert.owner_user_id == owner_user_id,
            DealerDashboardAlert.created_at >= alert_window_since,
        ),
    )
    feeds_ct = session.scalar(
        select(func.count(col(DealerDashboardFeedEvent.id))).where(
            DealerDashboardFeedEvent.owner_user_id == owner_user_id,
            DealerDashboardFeedEvent.created_at >= alert_window_since,
        ),
    )

    pieces.extend(
        [
            (
                "dealer_dashboard.activity_counters",
                "alerts_logged_90d_owner",
                {
                    "metric_family": "DEALER_ACTIVITY",
                    "metric_key": "alerts_logged_90d_owner",
                    "metric_value_text": str(int(alerts_ct or 0)),
                    "metric_value_decimal": "",
                },
                {"sources": [{"system": "dealer_dashboard_alert"}]},
            ),
            (
                "dealer_dashboard.activity_counters",
                "feed_events_logged_90d_owner",
                {
                    "metric_family": "DEALER_ACTIVITY",
                    "metric_key": "feed_events_logged_90d_owner",
                    "metric_value_text": str(int(feeds_ct or 0)),
                    "metric_value_decimal": "",
                },
                {"sources": [{"system": "dealer_dashboard_feed_event"}]},
            ),
        ],
    )

    if snap is not None:
        dm_rows = session.exec(
            select(DealerDashboardMetric)
            .where(DealerDashboardMetric.dashboard_snapshot_id == int(snap.id))
            .order_by(col(DealerDashboardMetric.metric_key).asc(), col(DealerDashboardMetric.id).asc()),
        ).all()
        for m in dm_rows:
            dec = m.metric_value_decimal
            txt_val = "" if dec is not None else (m.metric_value_text or "")
            if dec is None:
                dec_txt = ""
            elif isinstance(dec, Decimal):
                dec_txt = _decimal_str(dec)
            else:
                dec_txt = _decimal_str(Decimal(str(dec)))

            metric_key_slug = sanitize_report_filename(str(m.metric_key)).replace("-", "_")
            mk_full = f"child_metric::{metric_key_slug}"

            lineage = {"sources": [{"system": "dealer_dashboard_metric", "snapshot_id": int(snap.id), "metric_pk": int(m.id)}]}
            cells = {
                "metric_family": "DEALER_DASHBOARD_METRIC_CHILD",
                "metric_key": mk_full,
                "metric_value_text": txt_val,
                "metric_value_decimal": dec_txt,
            }

            pieces.append(("dealer_dashboard.metric_children", mk_full, cells, lineage))

    pieces.sort(key=lambda p: (p[2]["metric_family"], p[2]["metric_key"]))
    return cols, pieces


def _active_ready_missing_primary_visual(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(col(Listing.id))).where(
                Listing.owner_user_id == owner_user_id,
                Listing.status.in_(["ACTIVE", "READY"]),
                ~exists(
                    select(ListingImage.id).where(
                        ListingImage.listing_id == Listing.id,
                        ListingImage.role == "primary",
                    ),
                ),
            ),
        ),
    )


def _active_ready_missing_pricing(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(col(Listing.id))).where(
                Listing.owner_user_id == owner_user_id,
                Listing.status.in_(["ACTIVE", "READY"]),
                or_(Listing.asking_price_amount.is_(None), Listing.asking_price_currency.is_(None)),
            ),
        ),
    )


def _low_liquidity_snapshot_rows(session: Session, *, owner_user_id: int) -> int:
    mx = session.exec(
        select(func.max(col(InventoryLiquiditySnapshot.snapshot_date))).where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
        ),
    ).one()

    if mx is None:
        return 0
    return int(
        session.scalar(
            select(func.count(col(InventoryLiquiditySnapshot.id))).where(
                InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
                InventoryLiquiditySnapshot.snapshot_date == mx,
                InventoryLiquiditySnapshot.liquidity_status.in_(("LOW", "ILLIQUID")),
            ),
        ),
    )


def _stale_convention_assignment_signals(session: Session, *, owner_user_id: int) -> int:
    stmt = (
        select(func.count(func.distinct(col(ConventionInventoryAssignment.id))))
        .select_from(ConventionInventoryAssignment)
        .join(ConventionEvent, ConventionInventoryAssignment.convention_event_id == ConventionEvent.id)
        .join(
            ListingInventoryLink,
            ListingInventoryLink.inventory_copy_id == ConventionInventoryAssignment.inventory_item_id,
        )
        .join(Listing, ListingInventoryLink.listing_id == Listing.id)
        .join(ListingStalenessEvent, ListingStalenessEvent.listing_id == Listing.id)
        .where(
            ConventionEvent.owner_user_id == owner_user_id,
            ConventionEvent.status == "ACTIVE",
            ConventionInventoryAssignment.removed_at.is_(None),
            ListingStalenessEvent.event_type.in_(("STALE_CONFIRMED", "LONG_RUNNING")),
            Listing.status.in_(["ACTIVE", "READY"]),
        )
    )

    raw = session.exec(stmt).one()
    return int(raw)


def _inventory_health_summary_rows(session: Session, *, owner_user_id: int):
    cols = ("metric_family", "metric_key", "metric_value_integer", "notes")
    intel = listing_intelligence_service.build_listing_intelligence_dashboard_summary(session, owner_user_id=owner_user_id)

    stats = sorted(
        {
            "active_ready_missing_primary_visual": _active_ready_missing_primary_visual(session, owner_user_id=owner_user_id),
            "active_ready_missing_pricing": _active_ready_missing_pricing(session, owner_user_id=owner_user_id),
            "convention_assignment_inventory_stale_signal_rows": _stale_convention_assignment_signals(
                session, owner_user_id=owner_user_id
            ),
            "intel_incomplete_registry_listings_scope": intel.incomplete_listing_count,
            "latest_liquidity_snapshot_low_or_illiquid_rows": _low_liquidity_snapshot_rows(
                session,
                owner_user_id=owner_user_id,
            ),
            "recent_weak_intel_rows_window": len(intel.recent_weak_or_incomplete),
            "staleness_risk_listings_intel": intel.stale_risk_count,
        }.items(),
        key=lambda kv: kv[0],
    )

    pieces: RowPieces = []
    for mk, mv in stats:
        pieces.append(
            (
                "inventory.health.deterministic_signals",
                mk,
                {
                    "metric_family": "INVENTORY_HEALTH",
                    "metric_key": mk,
                    "metric_value_integer": str(int(mv)),
                    "notes": "read_only_aggregates",
                },
                {
                    "sources": [
                        {"system": "cross_layer_deterministic_read", "layers": LISTING_HEALTH_SOURCE_LAYERS.get(mk, [])},
                    ],
                },
            ),
        )

    return cols, pieces


def _collect_report_matrix(
    session: Session,
    *,
    owner_user_id: int,
    report_type: str,
    params_blob: dict[str, Any],
) -> tuple[tuple[str, ...], RowPieces]:
    if report_type == "listing_summary":
        return _listing_summary_rows(session, owner_user_id=owner_user_id)

    if report_type == "sales_summary":
        return _sales_summary_rows(session, owner_user_id=owner_user_id, params_blob=params_blob)

    if report_type == "liquidity_summary":
        return _liquidity_summary_rows(session, owner_user_id=owner_user_id)

    if report_type == "convention_summary":
        return _convention_summary_rows(session, owner_user_id=owner_user_id)

    if report_type == "export_summary":
        return _export_summary_rows(session, owner_user_id=owner_user_id)

    if report_type == "dealer_dashboard_summary":
        return _dealer_dashboard_summary_rows(session, owner_user_id=owner_user_id)

    if report_type == "inventory_health_summary":
        return _inventory_health_summary_rows(session, owner_user_id=owner_user_id)

    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unsupported report_type")


def _stable_piece_order(header: tuple[str, ...], pieces: RowPieces) -> list[tuple[str, str, dict[str, str], dict[str, Any]]]:
    return sorted(pieces, key=lambda p: tuple(p[2][h] for h in header))


def _persist_csv_bundle(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_row_id: int,
    header: tuple[str, ...],
    pieces_sorted: RowPieces,
    report_slug: str,
) -> OperationalReportRunDetailRead:
    row_cells_only = [{h: cells[h] for h in header} for _, _, cells, __ in pieces_sorted]

    csv_text = render_csv(header, row_cells_only)
    rn = 0
    insert_items = []
    for lineage_domain, _lk_hint, cells, lineage_extra in pieces_sorted:
        rn += 1
        row_cs = _row_checksum(cells)
        lineage_blob = dict(sorted({"domain": lineage_domain, **lineage_extra}.items()))
        lk_seed = cells.get("metric_key") or cells.get(header[-1]) or f"row_{rn}"
        lineage_key_safe = (f"{lineage_domain}:{lk_seed}")[:248]
        insert_items.append(
            OperationalReportItem(
                operational_report_run_id=int(run_row_id),
                row_number=rn,
                lineage_domain=lineage_domain[:128],
                lineage_key=lineage_key_safe,
                lineage_json=lineage_blob,
                row_checksum=row_cs,
                created_at=utc_now(),
            ),
        )

    stamp = utc_now().date().isoformat()
    slug_seg = sanitize_report_filename(report_slug)
    fname = re.sub(r"_+", "_", f"comic_os_{slug_seg}_{stamp}_run_{run_row_id}.csv")
    fname = fname.replace("-.csv", ".csv")

    csv_bytes_checksum = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()

    root = settings.operational_reports_storage_root
    rel_dir = f"{owner_user_id}/{int(run_row_id)}"
    dir_path = root / Path(rel_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    abs_path = dir_path / fname
    abs_path.write_text(csv_text, encoding="utf-8")
    storage_rel = f"{rel_dir}/{fname}".replace("\\", "/")

    session.add_all(insert_items)

    session.add(
        OperationalReportFile(
            operational_report_run_id=int(run_row_id),
            file_name=fname,
            file_type="csv",
            storage_path=storage_rel,
            checksum=csv_bytes_checksum,
            row_count=len(insert_items),
            created_at=utc_now(),
        ),
    )

    run_ref = session.get(OperationalReportRun, int(run_row_id))
    if run_ref is None:
        raise RuntimeError("report run vanished during persistence")

    run_ref.status = "COMPLETED"
    run_ref.csv_row_count = len(insert_items)
    run_ref.checksum = csv_bytes_checksum
    run_ref.failure_reason = None
    run_ref.completed_at = utc_now()
    session.add(run_ref)
    session.commit()
    return build_run_detail(session, owner_user_id=owner_user_id, operational_report_run_id=int(run_row_id))


def generate_operational_report(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: OperationalReportGeneratePayload | dict[str, Any],
) -> tuple[OperationalReportRunDetailRead, bool]:
    blob = payload if isinstance(payload, OperationalReportGeneratePayload) else OperationalReportGeneratePayload.model_validate(payload)

    rtype = str(blob.report_type)
    if rtype not in OPERATIONAL_REPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid operational report_type")

    gp = normalize_generation_params(blob.generation_params)
    rk = blob.replay_key

    dup = replay_lookup(session, owner_user_id=owner_user_id, replay_key=rk)

    if dup is not None:
        session.refresh(dup)

        return build_run_detail(session, owner_user_id=owner_user_id, operational_report_run_id=int(dup.id)), True

    ts = utc_now()
    run = OperationalReportRun(
        owner_user_id=owner_user_id,
        report_type=rtype,
        status="RUNNING",
        replay_key=rk,
        generation_params_json=gp,
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
        if rk:
            hit = replay_lookup(session, owner_user_id=owner_user_id, replay_key=rk)

            if hit is not None:
                session.refresh(hit)
                return build_run_detail(session, owner_user_id=owner_user_id, operational_report_run_id=int(hit.id)), True
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="operational report replay collision")

    run_id_tmp = int(run.id)

    try:
        hdr, pcs = _collect_report_matrix(session, owner_user_id=owner_user_id, report_type=rtype, params_blob=gp)
        ordered = _stable_piece_order(hdr, pcs)

        return (
            _persist_csv_bundle(
                session,
                settings,
                owner_user_id=owner_user_id,
                run_row_id=run_id_tmp,
                header=hdr,
                pieces_sorted=ordered,
                report_slug=rtype.replace("_summary", ""),
            ),
            False,
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:  # pragma: no cover - defensive persistence path
        msg = str(exc)[:4096]
        session.rollback()
        survivor = session.get(OperationalReportRun, run_id_tmp)
        if survivor is not None:
            survivor.status = "FAILED"
            survivor.failure_reason = msg
            survivor.completed_at = utc_now()
            session.add(survivor)
            session.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="report generation failed")


def resolve_operational_report_download_path(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    operational_report_run_id: int,
    operational_report_file_id: int | None,
    allow_ops_any_owner: bool = False,
) -> tuple[Path, OperationalReportFile]:
    row = session.get(OperationalReportRun, operational_report_run_id)
    if row is None or (int(row.owner_user_id) != owner_user_id and not allow_ops_any_owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")

    if operational_report_file_id is not None:
        frow = session.get(OperationalReportFile, operational_report_file_id)
        if (
            frow is None or int(frow.operational_report_run_id) != operational_report_run_id
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report file not found")

    else:
        frow = session.exec(
            select(OperationalReportFile)
            .where(OperationalReportFile.operational_report_run_id == operational_report_run_id)
            .order_by(col(OperationalReportFile.id).asc())
            .limit(1),
        ).first()

        if frow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report file not found")

    root = settings.operational_reports_storage_root.resolve()

    rel = str(frow.storage_path).replace("\\", "/")

    if ".." in rel or rel.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid storage path")

    target = (root / rel).resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path escape blocked") from exc

    if not target.is_file():

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report file missing on disk")

    return target, frow


def list_response_from_rows(rows: list[OperationalReportRun], *, total: int, limit: int, offset: int) -> OperationalReportRunListResponse:
    return OperationalReportRunListResponse(
        items=[_coerce_run_read(r) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )

