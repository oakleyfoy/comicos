"""P70-06 scheduled market refresh (not on page load)."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy
from app.models.p70_market_refresh import P70MarketRefreshRun, utc_now
from app.models.sell_intelligence_platform import P71ExitQueueItem, P71ExitQueueSnapshot
from app.services.authoritative_fmv_service import get_authoritative_fmv
from app.services.market_pricing_engine_service import build_market_price_snapshots, list_observations
from app.services.market_trend_history_service import record_trend_points_from_snapshots
from app.services.p67_inventory_bridge import enrich_row_value, fmv_lookup_by_title, load_p67_inventory_context, p68_computed_fmv_for_copy


def p70_market_refresh_enabled() -> bool:
    return get_settings().p70_market_refresh_enabled


def select_refresh_target_copy_ids(session: Session, *, owner_user_id: int, limit: int = 50) -> set[int]:
    rows = load_p67_inventory_context(session, owner_user_id=owner_user_id)
    fmv_map = fmv_lookup_by_title(session, owner_user_id=owner_user_id)
    ranked: list[tuple[int, float]] = []
    for row in rows:
        p68 = p68_computed_fmv_for_copy(session, owner_user_id=owner_user_id, copy_id=row.copy_id)
        est = enrich_row_value(row, fmv_map, p68_computed=p68)
        ranked.append((row.copy_id, est))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    targets: set[int] = {cid for cid, est in ranked[: max(1, limit // 2)] if est > 0}
    if not targets and ranked:
        targets = {ranked[0][0]}

    queue_snap = session.exec(
        select(P71ExitQueueSnapshot)
        .where(P71ExitQueueSnapshot.owner_user_id == owner_user_id)
        .order_by(P71ExitQueueSnapshot.generated_at.desc(), P71ExitQueueSnapshot.id.desc())
    ).first()
    if queue_snap is not None:
        for item in session.exec(
            select(P71ExitQueueItem)
            .where(P71ExitQueueItem.snapshot_id == int(queue_snap.id or 0))
            .order_by(P71ExitQueueItem.priority.asc())
            .limit(25)
        ).all():
            targets.add(int(item.inventory_copy_id))

    try:
        from app.services.buy_queue_service import get_latest_buy_queue_snapshot, list_buy_queue_items

        bq = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
        if bq is not None:
            items, _ = list_buy_queue_items(session, snapshot_id=int(bq.id or 0), limit=25)
            copies = {
                int(c.id or 0): c
                for c in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
            }
            for bqi in items:
                title = (bqi.title or "").strip().lower()
                for cid, copy in copies.items():
                    key = (copy.metadata_identity_key or "").lower()
                    if title and title in key:
                        targets.add(cid)
                        break
    except Exception:
        pass

    if len(targets) < limit:
        for cid, _est in ranked:
            targets.add(cid)
            if len(targets) >= limit:
                break
    return set(list(targets)[:limit])


def get_latest_refresh_run(session: Session, *, owner_user_id: int) -> P70MarketRefreshRun | None:
    return session.exec(
        select(P70MarketRefreshRun)
        .where(P70MarketRefreshRun.owner_user_id == owner_user_id)
        .order_by(P70MarketRefreshRun.started_at.desc(), P70MarketRefreshRun.id.desc())
    ).first()


def list_refresh_runs(session: Session, *, owner_user_id: int, limit: int = 20) -> list[P70MarketRefreshRun]:
    return list(
        session.exec(
            select(P70MarketRefreshRun)
            .where(P70MarketRefreshRun.owner_user_id == owner_user_id)
            .order_by(P70MarketRefreshRun.started_at.desc(), P70MarketRefreshRun.id.desc())
            .limit(min(max(limit, 1), 100))
        ).all()
    )


def run_market_refresh_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    trigger_type: str = "SCHEDULED",
) -> P70MarketRefreshRun:
    settings = get_settings()
    limit = max(5, int(settings.p70_market_refresh_top_holdings_limit))
    targets = select_refresh_target_copy_ids(session, owner_user_id=owner_user_id, limit=limit)
    run = P70MarketRefreshRun(
        owner_user_id=owner_user_id,
        trigger_type=trigger_type,
        status="RUNNING",
        started_at=utc_now(),
        target_copy_count=len(targets),
        metadata_json={"target_copy_ids": sorted(targets)},
    )
    session.add(run)
    session.flush()

    comps_before = len(list_observations(session, owner_user_id=owner_user_id, limit=5000))
    try:
        snaps = build_market_price_snapshots(
            session,
            owner_user_id=owner_user_id,
            inventory_copy_ids=targets,
        )
        trend_count = record_trend_points_from_snapshots(session, owner_user_id=owner_user_id, snapshots=snaps)
        comps_after = len(list_observations(session, owner_user_id=owner_user_id, limit=5000))
        run.status = "COMPLETED"
        run.completed_at = utc_now()
        run.books_refreshed = len(targets)
        run.fmv_snapshots_generated = len(snaps)
        run.comps_fetched = max(0, comps_after - comps_before)
        run.metadata_json = {
            **dict(run.metadata_json or {}),
            "trend_points_recorded": trend_count,
            "snapshots_built": len(snaps),
        }
    except Exception as exc:
        run.status = "FAILED"
        run.completed_at = utc_now()
        run.failure_count = 1
        run.error_message = str(exc)
    session.add(run)
    session.flush()
    return run


def list_owner_ids_with_inventory(session: Session) -> list[int]:
    rows = session.exec(select(InventoryCopy.user_id).distinct()).all()
    return sorted({int(r) for r in rows if r is not None})


def run_nightly_market_refresh_scan(session: Session) -> dict[str, int]:
    if not p70_market_refresh_enabled():
        return {"owners": 0, "completed": 0, "failed": 0}
    owners = list_owner_ids_with_inventory(session)
    completed = 0
    failed = 0
    for owner_id in owners:
        result = run_market_refresh_for_owner(session, owner_user_id=owner_id, trigger_type="SCHEDULED")
        if result.status == "COMPLETED":
            completed += 1
        else:
            failed += 1
    session.flush()
    return {"owners": len(owners), "completed": completed, "failed": failed}


def authoritative_fmv_consistent_for_copy(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> bool:
    """True when P67 bridge and authoritative resolver agree on display FMV."""
    rows = [r for r in load_p67_inventory_context(session, owner_user_id=owner_user_id) if r.copy_id == inventory_copy_id]
    if not rows:
        return True
    row = rows[0]
    fmv_map = fmv_lookup_by_title(session, owner_user_id=owner_user_id)
    p68 = p68_computed_fmv_for_copy(session, owner_user_id=owner_user_id, copy_id=inventory_copy_id)
    bridge_val = enrich_row_value(row, fmv_map, p68_computed=p68)
    auth = get_authoritative_fmv(session, owner_user_id=owner_user_id, inventory_copy_id=inventory_copy_id)
    if auth is None:
        return bridge_val <= 0 or row.current_value == bridge_val
    return abs(bridge_val - auth.authoritative_fmv) < 0.02
