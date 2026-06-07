"""P90-02 FMV Intelligence V2 dashboard and diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.p90_fmv_snapshot import P90FmvSnapshot
from app.schemas.p90_fmv_v2 import (
    P90FmvDiagnosticsRead,
    P90FmvIntelligenceDashboardRead,
    P90FmvSnapshotRead,
    P90FmvV2CopyRead,
)
from app.models.asset_ledger import InventoryCopy
from app.services.fmv_v2_service import latest_snapshots_for_owner, lookup_fmv_v2_for_copy
from app.services.portfolio_fmv_v2_service import build_portfolio_fmv_v2


def _snap_read(row: P90FmvSnapshot) -> P90FmvSnapshotRead:
    return P90FmvSnapshotRead(
        id=int(row.id or 0),
        series=row.series,
        issue_number=row.issue_number,
        variant=row.variant,
        quick_sale_value=float(row.quick_sale_value),
        market_value=float(row.market_value),
        premium_value=float(row.premium_value),
        valuation_confidence=row.valuation_confidence,
        trend_direction=row.trend_direction,
        trend_score=float(row.trend_score),
        sales_velocity=row.sales_velocity,
        listing_count=int(row.listing_count),
        marketplace_count=int(row.marketplace_count),
        valuation_source=row.valuation_source,
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def build_fmv_intelligence_dashboard(session: Session, *, owner_user_id: int) -> P90FmvIntelligenceDashboardRead:
    from app.services.p90_safe_reads import p90_safe_call

    def _build() -> P90FmvIntelligenceDashboardRead:
        now = datetime.now(timezone.utc)
        snaps = latest_snapshots_for_owner(session, owner_user_id=owner_user_id, limit=500)
        reads = [_snap_read(s) for s in snaps]
        return P90FmvIntelligenceDashboardRead(
            portfolio=build_portfolio_fmv_v2(session, owner_user_id=owner_user_id),
            highest_value=sorted(reads, key=lambda r: r.market_value, reverse=True)[:12],
            largest_movers=sorted(reads, key=lambda r: abs(r.trend_score), reverse=True)[:12],
            strongest_uptrends=sorted(reads, key=lambda r: r.trend_score, reverse=True)[:12],
            strongest_downtrends=sorted(reads, key=lambda r: r.trend_score)[:12],
            highest_confidence=sorted(
                reads,
                key=lambda r: ({"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(r.valuation_confidence, 0), r.market_value),
                reverse=True,
            )[:12],
            lowest_confidence=sorted(
                reads,
                key=lambda r: ({"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(r.valuation_confidence, 0), -r.market_value),
            )[:12],
            generated_at=now,
        )

    empty = P90FmvIntelligenceDashboardRead(
        status="EMPTY",
        portfolio=build_portfolio_fmv_v2(session, owner_user_id=owner_user_id),
        highest_value=[],
        largest_movers=[],
        strongest_uptrends=[],
        strongest_downtrends=[],
        highest_confidence=[],
        lowest_confidence=[],
        generated_at=datetime.now(timezone.utc),
    )
    return p90_safe_call(session, _build, default=empty, label="fmv_intelligence_dashboard")


def build_fmv_diagnostics(session: Session, *, owner_user_id: int) -> P90FmvDiagnosticsRead:
    now = datetime.now(timezone.utc)
    snaps = latest_snapshots_for_owner(session, owner_user_id=owner_user_id, limit=2000)
    conf: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    src: dict[str, int] = {"MARKETPLACE": 0, "HYBRID": 0, "LEGACY": 0}
    trend: dict[str, int] = {"UP": 0, "FLAT": 0, "DOWN": 0}
    for s in snaps:
        conf[s.valuation_confidence] = conf.get(s.valuation_confidence, 0) + 1
        src[s.valuation_source] = src.get(s.valuation_source, 0) + 1
        trend[s.trend_direction] = trend.get(s.trend_direction, 0) + 1
    total_rows = int(
        session.exec(
            select(func.count()).select_from(P90FmvSnapshot).where(P90FmvSnapshot.owner_user_id == owner_user_id)
        ).one()
        or 0
    )
    return P90FmvDiagnosticsRead(
        snapshot_count=total_rows,
        identity_coverage=len(snaps),
        confidence_distribution=conf,
        source_distribution=src,
        trend_distribution=trend,
        generated_at=now,
    )


def fmv_v2_for_inventory_copy(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> P90FmvV2CopyRead:
    from fastapi import HTTPException

    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or int(copy.user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    display = lookup_fmv_v2_for_copy(session, owner_user_id=owner_user_id, copy=copy)
    if display is None:
        raise HTTPException(status_code=404, detail="No FMV V2 data for this copy")
    legacy = float(copy.current_fmv or 0) if copy.current_fmv else None
    return P90FmvV2CopyRead(
        inventory_copy_id=inventory_copy_id,
        legacy_fmv=legacy,
        quick_sale_value=display.quick_sale_value,
        market_value=display.market_value,
        premium_value=display.premium_value,
        valuation_confidence=display.valuation_confidence,
        trend_direction=display.trend_direction,
        trend_score=display.trend_score,
        sales_velocity=display.sales_velocity,
    )
