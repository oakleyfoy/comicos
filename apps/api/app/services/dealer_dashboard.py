"""P36-07 deterministic dealer dashboard aggregation (read-mostly joins; persisted snapshots).

No mutation of listing, inventory, sales, export, liquidity, convention, or intelligence rows.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

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
    ListingImage,
    ListingIntelligenceSnapshot,
    ListingLifecycleEvent,
    ListingStalenessEvent,
    SaleLifecycleEvent,
    SaleRecord,
)
from app.schemas.dealer_dashboard import (
    DealerDashboardAlertListResponse,
    DealerDashboardAlertRead,
    DealerDashboardFeedEventRead,
    DealerDashboardFeedListResponse,
    DealerDashboardGeneratePayload,
    DealerDashboardGenerateResponse,
    DealerDashboardGetResponse,
    DealerDashboardMetricListResponse,
    DealerDashboardMetricRead,
    DealerDashboardSnapshotRead,
)

AGGREGATION_VERSION = "p36-07:v1"
MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
COMPLETENESS_THRESHOLD = Decimal("65")
INTEL_SNAPSHOT_SORT = ["STRONG", "ADEQUATE", "WEAK", "INCOMPLETE", "INSUFFICIENT_DATA"]
EXPORT_READY_SCORE_THRESHOLD = Decimal("100")
_FEED_LOOKBACK_DAYS = 90


def clamp_dealer_dashboard_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _snapshot_read(row: DealerDashboardSnapshot) -> DealerDashboardSnapshotRead:
    return DealerDashboardSnapshotRead.model_validate(row, from_attributes=True)


def latest_snapshot_for_owner(session: Session, *, owner_user_id: int) -> DealerDashboardSnapshot | None:
    return session.exec(
        select(DealerDashboardSnapshot)
        .where(DealerDashboardSnapshot.owner_user_id == owner_user_id)
        .order_by(col(DealerDashboardSnapshot.snapshot_date).desc())
        .order_by(col(DealerDashboardSnapshot.created_at).desc())
        .order_by(col(DealerDashboardSnapshot.id).desc())
    ).first()


def latest_snapshot_ops(session: Session, *, owner_user_id: int | None) -> DealerDashboardSnapshot | None:
    q = select(DealerDashboardSnapshot).order_by(
        col(DealerDashboardSnapshot.snapshot_date).desc(),
        col(DealerDashboardSnapshot.created_at).desc(),
        col(DealerDashboardSnapshot.id).desc(),
    )
    if owner_user_id is not None:
        q = q.where(DealerDashboardSnapshot.owner_user_id == owner_user_id)
    return session.exec(q).first()


def get_dashboard_owner(session: Session, *, owner_user_id: int) -> DealerDashboardGetResponse:
    row = latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
    return DealerDashboardGetResponse(snapshot=_snapshot_read(row) if row else None)


def get_dashboard_ops(session: Session, *, owner_user_id: int | None) -> DealerDashboardGetResponse:
    row = latest_snapshot_ops(session, owner_user_id=owner_user_id)
    return DealerDashboardGetResponse(snapshot=_snapshot_read(row) if row else None)


def _window_datetimes(snapshot_date: date, *, days: int = 30) -> tuple[datetime, datetime]:
    """Inclusive calendar window ending snapshot_date."""
    day_end = datetime.combine(snapshot_date, datetime.max.time(), tzinfo=timezone.utc)
    start_date = snapshot_date - timedelta(days=days - 1)
    day_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    return day_start, day_end


def _active_convention_assignment_rows(session: Session, *, owner_user_id: int) -> list[ConventionInventoryAssignment]:
    return list(
        session.exec(
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
            .order_by(col(ConventionInventoryAssignment.id).asc()),
        ).all(),
    )


def _compute_payload(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date,
) -> dict[str, Any]:
    """All reads; deterministic payload for checksum."""
    active_listing_count = int(
        session.exec(
            select(func.count(col(Listing.id))).where(
                Listing.owner_user_id == owner_user_id,
                Listing.status == "ACTIVE",
            ),
        ).one(),
    )

    intel_rows = session.exec(
        select(ListingIntelligenceSnapshot).where(
            ListingIntelligenceSnapshot.owner_user_id == owner_user_id,
            ListingIntelligenceSnapshot.snapshot_date == snapshot_date,
        ),
    ).all()
    export_ready_count = sum(
        1
        for row in intel_rows
        if row.export_readiness_score is not None
        and _money(row.export_readiness_score) >= EXPORT_READY_SCORE_THRESHOLD
    )
    incomplete_listing_count = sum(1 for row in intel_rows if row.intelligence_status == "INCOMPLETE")
    stale_intel_flags = sorted({row.listing_id for row in intel_rows if row.stale_risk_flag})

    staleness_listing_ids = session.exec(
        select(ListingStalenessEvent.listing_id)
        .join(Listing, ListingStalenessEvent.listing_id == Listing.id)
        .where(
            Listing.owner_user_id == owner_user_id,
            ListingStalenessEvent.event_type.in_(("STALE_CONFIRMED", "LONG_RUNNING")),
            Listing.status.in_(("ACTIVE", "READY")),
        )
        .order_by(col(ListingStalenessEvent.listing_id).asc()),
    ).all()
    stale_union = sorted(set(list(staleness_listing_ids)) | set(stale_intel_flags))
    stale_listing_count = len(stale_union)

    events = session.exec(
        select(ConventionEvent).where(ConventionEvent.owner_user_id == owner_user_id),
    ).all()
    active_convention_ids = sorted(int(row.id) for row in events if row.status == "ACTIVE")
    active_convention_count = len(active_convention_ids)

    assignment_rows = _active_convention_assignment_rows(session, owner_user_id=owner_user_id)
    assigned_inventory = sorted({row.inventory_item_id for row in assignment_rows})
    assigned_convention_inventory_count = len(assigned_inventory)

    open_sale_session_query = (
        select(ConventionSaleSession)
        .join(ConventionEvent, ConventionSaleSession.convention_event_id == ConventionEvent.id)
        .where(
            ConventionSaleSession.status == "OPEN",
            ConventionEvent.status == "ACTIVE",
            ConventionEvent.owner_user_id == owner_user_id,
        )
    )
    open_sale_session_count = int(
        session.scalar(select(func.count()).select_from(open_sale_session_query.subquery())) or 0,
    )

    day_start_30, day_end_30 = _window_datetimes(snapshot_date, days=30)
    gross_sales_30d = _money(
        session.exec(
            select(func.coalesce(func.sum(col(SaleRecord.gross_sale_amount)), ZERO)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
                SaleRecord.sale_date >= day_start_30.date(),
                SaleRecord.sale_date <= snapshot_date,
            ),
        ).one(),
    )
    net_sales_30d = _money(
        session.exec(
            select(func.coalesce(func.sum(col(SaleRecord.net_proceeds_amount)), ZERO)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
                SaleRecord.sale_date >= day_start_30.date(),
                SaleRecord.sale_date <= snapshot_date,
            ),
        ).one(),
    )
    realized_profit_30d = _money(
        session.exec(
            select(func.coalesce(func.sum(col(SaleRecord.realized_profit_amount)), ZERO)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
                SaleRecord.sale_date >= day_start_30.date(),
                SaleRecord.sale_date <= snapshot_date,
            ),
        ).one(),
    )

    liq_rows = session.exec(
        select(InventoryLiquiditySnapshot).where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            InventoryLiquiditySnapshot.snapshot_date == snapshot_date,
            col(InventoryLiquiditySnapshot.inventory_item_id).is_not(None),
        ),
    ).all()
    highs: set[int] = set()
    lows: set[int] = set()
    for row in liq_rows:
        inv_id = int(row.inventory_item_id or 0)
        if inv_id <= 0:
            continue
        if row.liquidity_status == "HIGH":
            highs.add(inv_id)
        elif row.liquidity_status in ("LOW", "ILLIQUID"):
            lows.add(inv_id)
    # Remove overlap deterministically if both exist (ambiguous): classify as neither high nor low-only
    overlap = highs & lows
    highs -= overlap
    lows -= overlap
    liquidity_high_count = len(highs)
    liquidity_low_count = len(lows)

    export_start, export_end = _window_datetimes(snapshot_date, days=30)
    export_runs_window = session.exec(
        select(ListingExportRun)
        .where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRun.created_at >= export_start,
            ListingExportRun.created_at <= export_end,
        )
        .order_by(col(ListingExportRun.created_at).asc(), col(ListingExportRun.id).asc()),
    ).all()
    export_run_count_30d = len(export_runs_window)

    failed_export_count_30d = sum(
        1
        for row in export_runs_window
        if int(row.error_count or 0) > 0 or str(row.status) != "COMPLETED"
    )

    avg_completeness: Decimal | None = None
    export_ready_pct: Decimal | None = None
    weak_listing_count = sum(1 for row in intel_rows if row.intelligence_status == "WEAK")
    if intel_rows:
        total_score = ZERO
        for row in intel_rows:
            total_score += _money(row.completeness_score)
        avg_completeness = _money(total_score / Decimal(str(len(intel_rows))))
        active_ids_rows = session.exec(
            select(col(Listing.id)).where(Listing.owner_user_id == owner_user_id, Listing.status == "ACTIVE"),
        ).all()
        active_ids_set = {int(i) for i in active_ids_rows if i is not None}
        active_intel_ready = sum(
            1
            for row in intel_rows
            if int(row.listing_id) in active_ids_set
            and row.export_readiness_score is not None
            and _money(row.export_readiness_score) >= EXPORT_READY_SCORE_THRESHOLD
        )
        if active_ids_set:
            export_ready_pct = _money(Decimal(active_intel_ready * 100) / Decimal(len(active_ids_set)))

    checklist: dict[str, Any] = {
        "aggregation_version": AGGREGATION_VERSION,
        "owner_user_id": owner_user_id,
        "snapshot_date": snapshot_date,
        "active_listing_count": active_listing_count,
        "export_ready_count": export_ready_count,
        "incomplete_listing_count": incomplete_listing_count,
        "stale_listing_count": stale_listing_count,
        "active_convention_count": active_convention_count,
        "assigned_convention_inventory_count": assigned_convention_inventory_count,
        "open_sale_session_count": open_sale_session_count,
        "gross_sales_30d": gross_sales_30d,
        "net_sales_30d": net_sales_30d,
        "realized_profit_30d": realized_profit_30d,
        "liquidity_high_count": liquidity_high_count,
        "liquidity_low_count": liquidity_low_count,
        "export_run_count_30d": export_run_count_30d,
        "failed_export_count_30d": failed_export_count_30d,
        "intel_listing_order": [
            [
                int(row.listing_id),
                {
                    "intelligence_status": row.intelligence_status,
                    "completeness_score": row.completeness_score,
                    "export_readiness_score": row.export_readiness_score,
                    "stale_risk_flag": row.stale_risk_flag,
                },
            ]
            for row in sorted(intel_rows, key=lambda r: int(r.listing_id))
        ],
        "intel_status_counts": {status: sum(1 for row in intel_rows if row.intelligence_status == status) for status in INTEL_SNAPSHOT_SORT},
        "average_completeness_score": avg_completeness,
        "export_ready_active_pct_snapshot": export_ready_pct,
        "weak_listing_count": weak_listing_count,
        "stale_union_listing_ids": stale_union,
    }
    return checklist


def generate_dealer_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    payload: DealerDashboardGeneratePayload,
) -> DealerDashboardGenerateResponse:
    replay_key_trim = payload.replay_key.strip() if payload.replay_key else None
    snapshot_date = payload.snapshot_date or _utc_today()

    if replay_key_trim:
        collision = session.exec(
            select(DealerDashboardSnapshot).where(
                DealerDashboardSnapshot.owner_user_id == owner_user_id,
                DealerDashboardSnapshot.replay_key == replay_key_trim,
            ),
        ).first()
        if collision:
            return DealerDashboardGenerateResponse(snapshot=_snapshot_read(collision))

    payload_dict = _compute_payload(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
    checksum = _hash_payload(payload_dict)

    snap = DealerDashboardSnapshot(
        owner_user_id=owner_user_id,
        replay_key=replay_key_trim,
        active_listing_count=int(payload_dict["active_listing_count"]),
        export_ready_count=int(payload_dict["export_ready_count"]),
        incomplete_listing_count=int(payload_dict["incomplete_listing_count"]),
        stale_listing_count=int(payload_dict["stale_listing_count"]),
        active_convention_count=int(payload_dict["active_convention_count"]),
        assigned_convention_inventory_count=int(payload_dict["assigned_convention_inventory_count"]),
        open_sale_session_count=int(payload_dict["open_sale_session_count"]),
        gross_sales_30d=_money(payload_dict["gross_sales_30d"]),
        net_sales_30d=_money(payload_dict["net_sales_30d"]),
        realized_profit_30d=_money(payload_dict["realized_profit_30d"]),
        liquidity_high_count=int(payload_dict["liquidity_high_count"]),
        liquidity_low_count=int(payload_dict["liquidity_low_count"]),
        export_run_count_30d=int(payload_dict["export_run_count_30d"]),
        failed_export_count_30d=int(payload_dict["failed_export_count_30d"]),
        checksum=checksum,
        snapshot_date=snapshot_date,
    )
    session.add(snap)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if replay_key_trim:
            existing = session.exec(
                select(DealerDashboardSnapshot).where(
                    DealerDashboardSnapshot.owner_user_id == owner_user_id,
                    DealerDashboardSnapshot.replay_key == replay_key_trim,
                ),
            ).first()
            if existing:
                return DealerDashboardGenerateResponse(snapshot=_snapshot_read(existing))
        raise

    metrics_map: dict[str, Any] = {
        "aggregation_version": Decimal("1"),
        "aggregation_label": AGGREGATION_VERSION,
        "intel_weak_count": Decimal(str(payload_dict["weak_listing_count"])),
        "intel_insufficient_count": Decimal(str(payload_dict["intel_status_counts"].get("INSUFFICIENT_DATA", 0))),
        "completeness_alert_threshold": COMPLETENESS_THRESHOLD,
        "average_completeness_score": payload_dict["average_completeness_score"],
        "export_ready_active_pct_estimate": payload_dict["export_ready_active_pct_snapshot"],
    }

    metric_rows: list[DealerDashboardMetric] = []
    for metric_key in sorted(metrics_map.keys()):
        value = metrics_map[metric_key]
        mv_dec: Decimal | None = None
        mv_txt: str | None = None
        if isinstance(value, Decimal):
            mv_dec = _money(value)
        elif isinstance(value, (int, float)):
            mv_dec = Decimal(str(value))
        elif value is not None:
            mv_txt = str(value)
        metric_rows.append(
            DealerDashboardMetric(
                dashboard_snapshot_id=int(snap.id),
                metric_key=metric_key,
                metric_value_decimal=_money(mv_dec) if mv_dec is not None else None,
                metric_value_text=mv_txt,
                metric_metadata_json=None if metric_key != "aggregation_label" else {"label": AGGREGATION_VERSION},
            ),
        )
    session.add_all(metric_rows)
    snapshot_id_int = int(snap.id)

    # Alerts — append-only inserts; deterministic replay keys.
    stale_ids: list[int] = list(payload_dict["stale_union_listing_ids"])
    for lid in stale_ids:
        lk = hashlib.sha256(f"{snapshot_id_int}:STALE_LISTING:{lid}".encode()).hexdigest()
        session.add(
            DealerDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=snapshot_id_int,
                alert_type="STALE_LISTING",
                severity="warning",
                alert_replay_key=lk,
                source_listing_id=lid,
                message=f"Listing #{lid} is flagged stale-confirmed/long-running or has stale-risk intelligence.",
            ),
        )

    if int(payload_dict["failed_export_count_30d"]) > 0:
        ek = hashlib.sha256(f"{snapshot_id_int}:EXPORT_FAILURE:rollup".encode()).hexdigest()
        session.add(
            DealerDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=snapshot_id_int,
                alert_type="EXPORT_FAILURE",
                severity="critical",
                alert_replay_key=ek,
                message=(
                    f"{payload_dict['failed_export_count_30d']} export run(s) in the trailing 30d window exited non-success "
                    "or reported errors."
                ),
            ),
        )

    intel_rows_sorted = sorted(
        session.exec(
            select(ListingIntelligenceSnapshot).where(
                ListingIntelligenceSnapshot.owner_user_id == owner_user_id,
                ListingIntelligenceSnapshot.snapshot_date == snapshot_date,
            ),
        ).all(),
        key=lambda row: row.listing_id,
    )
    active_listings = session.exec(select(Listing).where(Listing.owner_user_id == owner_user_id)).all()
    active_by_id = {int(row.id or 0): row for row in active_listings if row.id}

    inv_to_active_listing: dict[int, int] = {}
    for lst in active_listings:
        if lst.id and lst.status == "ACTIVE":
            inv_to_active_listing[int(lst.inventory_copy_id)] = int(lst.id)

    convention_assignments_alert = _active_convention_assignment_rows(session, owner_user_id=owner_user_id)

    for intel in intel_rows_sorted:
        lid = int(intel.listing_id)
        if intel.evidence_count == 0:
            continue
        if _money(intel.completeness_score) >= COMPLETENESS_THRESHOLD:
            continue
        ak = hashlib.sha256(f"{snapshot_id_int}:LOW_COMPLETENESS:{lid}".encode()).hexdigest()
        session.add(
            DealerDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=snapshot_id_int,
                alert_type="LOW_COMPLETENESS",
                severity="warning",
                alert_replay_key=ak,
                source_listing_id=lid,
                message=(
                    f"Listing #{lid} completeness score {_money(intel.completeness_score)} is below the {COMPLETENESS_THRESHOLD} Adequate floor."
                ),
            ),
        )

    li_low_by_listing: dict[int, InventoryLiquiditySnapshot] = {}
    for row in session.exec(
        select(InventoryLiquiditySnapshot).where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            InventoryLiquiditySnapshot.snapshot_date == snapshot_date,
            InventoryLiquiditySnapshot.liquidity_status.in_(("LOW", "ILLIQUID")),
        ),
    ).all():
        inv = int(row.inventory_item_id or 0)
        if inv <= 0:
            continue
        lid_candidate = inv_to_active_listing.get(inv)
        if lid_candidate is None:
            continue
        if lid_candidate not in li_low_by_listing:
            li_low_by_listing[lid_candidate] = row

    for lid, snap_row in sorted(li_low_by_listing.items(), key=lambda item: item[0]):
        lk2 = hashlib.sha256(f"{snapshot_id_int}:LOW_LIQUIDITY:{lid}:{snap_row.id}".encode()).hexdigest()
        session.add(
            DealerDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=snapshot_id_int,
                alert_type="LOW_LIQUIDITY",
                severity="warning",
                alert_replay_key=lk2,
                source_listing_id=lid,
                source_inventory_item_id=int(snap_row.inventory_item_id or 0),
                message=(
                    f"Listing #{lid} inventory item liquidity is {snap_row.liquidity_status} on {snapshot_date} evidence."
                ),
            ),
        )

    for asn in convention_assignments_alert:
        if asn.local_price_amount is not None:
            continue
        ck = hashlib.sha256(f"{snapshot_id_int}:CONVENTION_PRICING_MISSING:{asn.id}".encode()).hexdigest()
        session.add(
            DealerDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=snapshot_id_int,
                alert_type="CONVENTION_PRICING_MISSING",
                severity="warning",
                alert_replay_key=ck,
                source_inventory_item_id=int(asn.inventory_item_id),
                source_convention_event_id=int(asn.convention_event_id),
                message=(
                    f"Convention assignment #{asn.id} is active without a local price snapshot for inventory #{asn.inventory_item_id}."
                ),
            ),
        )

    listing_ids_sorted = sorted({lid for lid in active_by_id.keys() if lid})
    for lid in listing_ids_sorted:
        listing_row = active_by_id.get(lid)
        if listing_row is None:
            continue
        images = session.exec(
            select(ListingImage).where(ListingImage.listing_id == lid).order_by(col(ListingImage.display_order).asc(), col(ListingImage.id).asc()),
        ).all()
        primary_ok = any(str(img.role).lower() == "primary" for img in images)
        if primary_ok:
            continue
        mk = hashlib.sha256(f"{snapshot_id_int}:MISSING_PRIMARY_IMAGE:{lid}".encode()).hexdigest()
        session.add(
            DealerDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=snapshot_id_int,
                alert_type="MISSING_PRIMARY_IMAGE",
                severity="warning",
                alert_replay_key=mk,
                source_listing_id=lid,
                message=f"Active listing #{lid} does not designate a PRIMARY gallery image.",
            ),
        )

    feed_start_date = snapshot_date - timedelta(days=_FEED_LOOKBACK_DAYS)
    feed_candidates: list[tuple[datetime, str, DealerDashboardFeedEvent]] = []

    lifecycle_rows = session.exec(
        select(ListingLifecycleEvent)
        .join(Listing, ListingLifecycleEvent.listing_id == Listing.id)
        .where(
            Listing.owner_user_id == owner_user_id,
            ListingLifecycleEvent.created_at >= datetime.combine(feed_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .order_by(col(ListingLifecycleEvent.created_at).asc(), col(ListingLifecycleEvent.id).asc()),
    ).all()
    for ev in lifecycle_rows:
        if ev.event_type == "CREATED":
            key = f"LISTING_CREATED:lifecycle_event:{ev.id}"
            dt = ev.created_at
            feed_candidates.append(
                (
                    dt,
                    key,
                    DealerDashboardFeedEvent(
                        owner_user_id=owner_user_id,
                        deterministic_key=key,
                        dashboard_snapshot_id=snapshot_id_int,
                        event_type="LISTING_CREATED",
                        source_id=int(ev.id),
                        summary=f"Listing #{ev.listing_id} lifecycle CREATED logged.",
                        metadata_json={"listing_id": ev.listing_id, "replay_key": ev.replay_key},
                        created_at=dt,
                    ),
                ),
            )
        elif ev.event_type == "SOLD":
            key = f"LISTING_SOLD:lifecycle_event:{ev.id}"
            dt = ev.created_at
            feed_candidates.append(
                (
                    dt,
                    key,
                    DealerDashboardFeedEvent(
                        owner_user_id=owner_user_id,
                        deterministic_key=key,
                        dashboard_snapshot_id=snapshot_id_int,
                        event_type="LISTING_SOLD",
                        source_id=int(ev.id),
                        summary=f"Listing #{ev.listing_id} marked SOLD.",
                        metadata_json={"listing_id": ev.listing_id},
                        created_at=dt,
                    ),
                ),
            )

    export_rows = session.exec(
        select(ListingExportRun)
        .where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRun.created_at >= datetime.combine(feed_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .order_by(col(ListingExportRun.created_at).asc(), col(ListingExportRun.id).asc()),
    ).all()
    for run in export_rows:
        dt_run = run.completed_at or run.created_at
        if str(run.status) == "COMPLETED" and int(run.error_count or 0) == 0:
            key = f"EXPORT_COMPLETED:{run.id}"
            feed_candidates.append(
                (
                    dt_run,
                    key,
                    DealerDashboardFeedEvent(
                        owner_user_id=owner_user_id,
                        deterministic_key=key,
                        dashboard_snapshot_id=snapshot_id_int,
                        event_type="EXPORT_COMPLETED",
                        source_id=int(run.id),
                        summary=f"Export run #{run.id} completed on {run.channel}.",
                        metadata_json={"channel": run.channel},
                        created_at=dt_run,
                    ),
                ),
            )
        elif int(run.error_count or 0) > 0 or str(run.status) != "COMPLETED":
            key = f"EXPORT_FAILED:{run.id}"
            feed_candidates.append(
                (
                    dt_run,
                    key,
                    DealerDashboardFeedEvent(
                        owner_user_id=owner_user_id,
                        deterministic_key=key,
                        dashboard_snapshot_id=snapshot_id_int,
                        event_type="EXPORT_FAILED",
                        source_id=int(run.id),
                        summary=f"Export run #{run.id} reported failures or unfinished status ({run.status}).",
                        metadata_json={"channel": run.channel, "error_count": int(run.error_count or 0)},
                        created_at=dt_run,
                    ),
                ),
            )

    recorded_events = session.exec(
        select(SaleLifecycleEvent)
        .join(SaleRecord, SaleLifecycleEvent.sale_record_id == SaleRecord.id)
        .where(
            SaleRecord.owner_user_id == owner_user_id,
            SaleLifecycleEvent.event_type == "RECORDED",
            SaleLifecycleEvent.created_at >= datetime.combine(feed_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .order_by(col(SaleLifecycleEvent.created_at).asc(), col(SaleLifecycleEvent.id).asc()),
    ).all()
    for sev in recorded_events:
        key = f"SALE_RECORDED:lifecycle:{sev.id}"
        dt_sales = sev.created_at
        feed_candidates.append(
            (
                dt_sales,
                key,
                DealerDashboardFeedEvent(
                    owner_user_id=owner_user_id,
                    deterministic_key=key,
                    dashboard_snapshot_id=snapshot_id_int,
                    event_type="SALE_RECORDED",
                    source_id=int(sev.id),
                    summary=f"Sale #{sev.sale_record_id} recorded in ledger.",
                    metadata_json={"sale_record_id": sev.sale_record_id},
                    created_at=dt_sales,
                ),
            ),
        )

    staleness_logs = session.exec(
        select(ListingStalenessEvent)
        .where(
            ListingStalenessEvent.owner_user_id == owner_user_id,
            ListingStalenessEvent.created_at >= datetime.combine(feed_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .order_by(col(ListingStalenessEvent.created_at).asc(), col(ListingStalenessEvent.id).asc()),
    ).all()
    for st in staleness_logs:
        key = f"STALE_DETECTED:{st.id}"
        feed_candidates.append(
            (
                st.created_at,
                key,
                DealerDashboardFeedEvent(
                    owner_user_id=owner_user_id,
                    deterministic_key=key,
                    dashboard_snapshot_id=snapshot_id_int,
                    event_type="STALE_DETECTED",
                    source_id=int(st.id),
                    summary=f"Staleness detector logged {st.event_type} for listing #{st.listing_id}.",
                    metadata_json={"listing_id": st.listing_id, "event_type": st.event_type},
                    created_at=st.created_at,
                ),
            ),
        )

    assign_feed = session.exec(
        select(ConventionInventoryAssignment)
        .join(ConventionEvent, ConventionInventoryAssignment.convention_event_id == ConventionEvent.id)
        .where(
            ConventionEvent.owner_user_id == owner_user_id,
            ConventionInventoryAssignment.assigned_at
            >= datetime.combine(feed_start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .order_by(col(ConventionInventoryAssignment.assigned_at).asc(), col(ConventionInventoryAssignment.id).asc()),
    ).all()
    for asn_feed in assign_feed:
        key = f"CONVENTION_ASSIGNED:{asn_feed.id}"
        feed_candidates.append(
            (
                asn_feed.assigned_at,
                key,
                DealerDashboardFeedEvent(
                    owner_user_id=owner_user_id,
                    deterministic_key=key,
                    dashboard_snapshot_id=snapshot_id_int,
                    event_type="CONVENTION_ASSIGNED",
                    source_id=int(asn_feed.id),
                    summary=f"Inventory #{asn_feed.inventory_item_id} assigned for convention #{asn_feed.convention_event_id}.",
                    metadata_json={
                        "convention_event_id": asn_feed.convention_event_id,
                        "inventory_item_id": asn_feed.inventory_item_id,
                    },
                    created_at=asn_feed.assigned_at,
                ),
            ),
        )

    li_feed = session.exec(
        select(InventoryLiquiditySnapshot)
        .where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            InventoryLiquiditySnapshot.snapshot_date == snapshot_date,
        )
        .order_by(col(InventoryLiquiditySnapshot.id).asc()),
    ).all()
    for li_snap in li_feed:
        key = f"LIQUIDITY_UPDATED:{li_snap.id}"
        feed_candidates.append(
            (
                li_snap.created_at,
                key,
                DealerDashboardFeedEvent(
                    owner_user_id=owner_user_id,
                    deterministic_key=key,
                    dashboard_snapshot_id=snapshot_id_int,
                    event_type="LIQUIDITY_UPDATED",
                    source_id=int(li_snap.id),
                    summary=f"Liquidity snapshot #{li_snap.id} materialized ({li_snap.liquidity_status}).",
                    metadata_json={"liquidity_status": li_snap.liquidity_status},
                    created_at=li_snap.created_at,
                ),
            ),
        )

    feed_candidates.sort(key=lambda tup: (tup[0], tup[1]))
    for _, __, evt in feed_candidates:
        existing = session.exec(
            select(DealerDashboardFeedEvent).where(
                DealerDashboardFeedEvent.owner_user_id == owner_user_id,
                DealerDashboardFeedEvent.deterministic_key == evt.deterministic_key,
            ),
        ).first()
        if existing is None:
            session.add(evt)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise

    persisted = session.get(DealerDashboardSnapshot, snapshot_id_int)
    if persisted is None:
        raise RuntimeError("dealer dashboard snapshot missing post-commit")
    return DealerDashboardGenerateResponse(snapshot=_snapshot_read(persisted))


def list_metrics_owner(
    session: Session,
    *,
    owner_user_id: int,
    dashboard_snapshot_id: int | None,
    limit: int,
    offset: int,
) -> DealerDashboardMetricListResponse:
    lim, off = clamp_dealer_dashboard_pagination(limit=limit, offset=offset)
    if dashboard_snapshot_id is None:
        latest = latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
        if latest is None:
            return DealerDashboardMetricListResponse(items=[], total_items=0, limit=lim, offset=off)
        dashboard_snapshot_id = int(latest.id)
    qb = (
        select(DealerDashboardMetric)
        .join(DealerDashboardSnapshot, DealerDashboardMetric.dashboard_snapshot_id == DealerDashboardSnapshot.id)
        .where(
            DealerDashboardSnapshot.owner_user_id == owner_user_id,
            DealerDashboardMetric.dashboard_snapshot_id == dashboard_snapshot_id,
        )
        .order_by(col(DealerDashboardMetric.metric_key).asc(), col(DealerDashboardMetric.id).asc())
    )
    qc = select(func.count()).select_from(qb.subquery())
    total = int(session.scalar(qc) or 0)
    rows = session.exec(qb.offset(off).limit(lim)).all()
    items = [DealerDashboardMetricRead.model_validate(r, from_attributes=True) for r in rows]
    return DealerDashboardMetricListResponse(items=items, total_items=total, limit=lim, offset=off)


def list_metrics_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    dashboard_snapshot_id: int | None,
    limit: int,
    offset: int,
) -> DealerDashboardMetricListResponse:
    lim, off = clamp_dealer_dashboard_pagination(limit=limit, offset=offset)
    if dashboard_snapshot_id is not None:
        snap_row = session.get(DealerDashboardSnapshot, dashboard_snapshot_id)
        if snap_row is None:
            return DealerDashboardMetricListResponse(items=[], total_items=0, limit=lim, offset=off)
        if owner_user_id is not None and int(snap_row.owner_user_id) != int(owner_user_id):
            return DealerDashboardMetricListResponse(items=[], total_items=0, limit=lim, offset=off)
    else:
        latest = latest_snapshot_ops(session, owner_user_id=owner_user_id)
        if latest is None:
            return DealerDashboardMetricListResponse(items=[], total_items=0, limit=lim, offset=off)
        dashboard_snapshot_id = int(latest.id)
        if owner_user_id is not None and int(latest.owner_user_id) != int(owner_user_id):
            return DealerDashboardMetricListResponse(items=[], total_items=0, limit=lim, offset=off)
    qb = (
        select(DealerDashboardMetric)
        .join(DealerDashboardSnapshot, DealerDashboardMetric.dashboard_snapshot_id == DealerDashboardSnapshot.id)
        .where(
            DealerDashboardMetric.dashboard_snapshot_id == dashboard_snapshot_id,
        )
    )
    if owner_user_id is not None:
        qb = qb.where(DealerDashboardSnapshot.owner_user_id == owner_user_id)
    qb = qb.order_by(col(DealerDashboardMetric.metric_key).asc(), col(DealerDashboardMetric.id).asc())
    qc = select(func.count()).select_from(qb.subquery())
    total = int(session.scalar(qc) or 0)
    rows = session.exec(qb.offset(off).limit(lim)).all()
    items = [DealerDashboardMetricRead.model_validate(r, from_attributes=True) for r in rows]
    return DealerDashboardMetricListResponse(items=items, total_items=total, limit=lim, offset=off)


def list_alerts_owner(
    session: Session,
    *,
    owner_user_id: int,
    severity: str | None,
    alert_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerDashboardAlertListResponse:
    lim, off = clamp_dealer_dashboard_pagination(limit=limit, offset=offset)
    qb = select(DealerDashboardAlert).where(DealerDashboardAlert.owner_user_id == owner_user_id)
    if severity is not None:
        qb = qb.where(DealerDashboardAlert.severity == severity)
    if alert_type is not None:
        qb = qb.where(DealerDashboardAlert.alert_type == alert_type)
    if created_from is not None:
        qb = qb.where(DealerDashboardAlert.created_at >= created_from)
    if created_to is not None:
        qb = qb.where(DealerDashboardAlert.created_at <= created_to)
    qb = qb.order_by(col(DealerDashboardAlert.created_at).desc(), col(DealerDashboardAlert.id).desc())
    qc = select(func.count()).select_from(qb.subquery())
    total = int(session.scalar(qc) or 0)
    rows = session.exec(qb.offset(off).limit(lim)).all()
    items = [DealerDashboardAlertRead.model_validate(r, from_attributes=True) for r in rows]
    return DealerDashboardAlertListResponse(items=items, total_items=total, limit=lim, offset=off)


def list_alerts_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    severity: str | None,
    alert_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerDashboardAlertListResponse:
    lim, off = clamp_dealer_dashboard_pagination(limit=limit, offset=offset)
    qb = select(DealerDashboardAlert)
    if owner_user_id is not None:
        qb = qb.where(DealerDashboardAlert.owner_user_id == owner_user_id)
    if severity is not None:
        qb = qb.where(DealerDashboardAlert.severity == severity)
    if alert_type is not None:
        qb = qb.where(DealerDashboardAlert.alert_type == alert_type)
    if created_from is not None:
        qb = qb.where(DealerDashboardAlert.created_at >= created_from)
    if created_to is not None:
        qb = qb.where(DealerDashboardAlert.created_at <= created_to)
    qb = qb.order_by(col(DealerDashboardAlert.created_at).desc(), col(DealerDashboardAlert.id).desc())
    qc = select(func.count()).select_from(qb.subquery())
    total = int(session.scalar(qc) or 0)
    rows = session.exec(qb.offset(off).limit(lim)).all()
    items = [DealerDashboardAlertRead.model_validate(r, from_attributes=True) for r in rows]
    return DealerDashboardAlertListResponse(items=items, total_items=total, limit=lim, offset=off)


def list_feed_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerDashboardFeedListResponse:
    lim, off = clamp_dealer_dashboard_pagination(limit=limit, offset=offset)
    qb = select(DealerDashboardFeedEvent).where(DealerDashboardFeedEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        qb = qb.where(DealerDashboardFeedEvent.event_type == event_type)
    if created_from is not None:
        qb = qb.where(DealerDashboardFeedEvent.created_at >= created_from)
    if created_to is not None:
        qb = qb.where(DealerDashboardFeedEvent.created_at <= created_to)
    qb = qb.order_by(col(DealerDashboardFeedEvent.created_at).desc(), col(DealerDashboardFeedEvent.id).desc())
    qc = select(func.count()).select_from(qb.subquery())
    total = int(session.scalar(qc) or 0)
    rows = session.exec(qb.offset(off).limit(lim)).all()
    items = [DealerDashboardFeedEventRead.model_validate(r, from_attributes=True) for r in rows]
    return DealerDashboardFeedListResponse(items=items, total_items=total, limit=lim, offset=off)


def list_feed_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    event_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerDashboardFeedListResponse:
    lim, off = clamp_dealer_dashboard_pagination(limit=limit, offset=offset)
    qb = select(DealerDashboardFeedEvent)
    if owner_user_id is not None:
        qb = qb.where(DealerDashboardFeedEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        qb = qb.where(DealerDashboardFeedEvent.event_type == event_type)
    if created_from is not None:
        qb = qb.where(DealerDashboardFeedEvent.created_at >= created_from)
    if created_to is not None:
        qb = qb.where(DealerDashboardFeedEvent.created_at <= created_to)
    qb = qb.order_by(col(DealerDashboardFeedEvent.created_at).desc(), col(DealerDashboardFeedEvent.id).desc())
    qc = select(func.count()).select_from(qb.subquery())
    total = int(session.scalar(qc) or 0)
    rows = session.exec(qb.offset(off).limit(lim)).all()
    items = [DealerDashboardFeedEventRead.model_validate(r, from_attributes=True) for r in rows]
    return DealerDashboardFeedListResponse(items=items, total_items=total, limit=lim, offset=off)
