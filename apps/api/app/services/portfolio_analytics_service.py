"""P67-01 Portfolio Analytics — performance snapshots."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlmodel import Session, select

from app.models.portfolio_analytics_platform import (
    P67PortfolioPerformanceItem,
    P67PortfolioPerformanceSnapshot,
    utc_now,
)
from app.services.p67_inventory_bridge import enrich_row_value, fmv_lookup_by_title, load_p67_inventory_context


def get_latest_portfolio_analytics_snapshot(session: Session, *, owner_user_id: int) -> P67PortfolioPerformanceSnapshot | None:
    return session.exec(
        select(P67PortfolioPerformanceSnapshot)
        .where(P67PortfolioPerformanceSnapshot.owner_user_id == owner_user_id)
        .order_by(P67PortfolioPerformanceSnapshot.generated_at.desc(), P67PortfolioPerformanceSnapshot.id.desc())
    ).first()


def list_portfolio_analytics_items(session: Session, *, snapshot_id: int, limit: int = 200) -> list[P67PortfolioPerformanceItem]:
    return list(
        session.exec(
            select(P67PortfolioPerformanceItem)
            .where(P67PortfolioPerformanceItem.snapshot_id == snapshot_id)
            .order_by(P67PortfolioPerformanceItem.unrealized_gain_pct.desc(), P67PortfolioPerformanceItem.id.asc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


def build_portfolio_analytics_snapshot(session: Session, *, owner_user_id: int) -> P67PortfolioPerformanceSnapshot:
    today = date.today()
    rows = load_p67_inventory_context(session, owner_user_id=owner_user_id)
    fmv_map = fmv_lookup_by_title(session, owner_user_id=owner_user_id)

    snap = P67PortfolioPerformanceSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
    )
    session.add(snap)
    session.flush()

    total_cost = 0.0
    total_value = 0.0
    total_realized = 0.0
    roi_samples: list[float] = []
    items: list[P67PortfolioPerformanceItem] = []
    best = ("", -1e9)
    worst = ("", 1e9)
    largest = ("", -1.0)

    for row in rows:
        est = enrich_row_value(row, fmv_map)
        cost = row.cost_basis
        unreal = est - cost if est > 0 else 0.0
        unreal_pct = (unreal / cost * 100.0) if cost > 0 and est > 0 else 0.0
        realized = 0.0
        realized_pct = 0.0
        roi = unreal_pct
        total_cost += cost
        total_value += est
        total_realized += realized
        if est > 0:
            roi_samples.append(roi)
        label = f"{row.title} #{row.issue_number}".strip()
        if unreal_pct > best[1]:
            best = (label, unreal_pct)
        if unreal_pct < worst[1]:
            worst = (label, unreal_pct)
        if est > largest[1]:
            largest = (label, est)
        items.append(
            P67PortfolioPerformanceItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=row.copy_id,
                title=row.title,
                publisher=row.publisher,
                series=row.title,
                issue_number=row.issue_number,
                cost_basis=cost,
                estimated_value=est,
                unrealized_gain=unreal,
                unrealized_gain_pct=round(unreal_pct, 2),
                realized_gain=realized,
                realized_gain_pct=realized_pct,
                roi_pct=round(roi, 2),
                notes_json={"grade_status": row.grade_status, "identity_key": row.identity_key},
            )
        )

    for item in items:
        session.add(item)

    total_unreal = total_value - total_cost
    unreal_pct = (total_unreal / total_cost * 100.0) if total_cost > 0 else 0.0
    realized_pct = (total_realized / total_cost * 100.0) if total_cost > 0 else 0.0
    avg_roi = sum(roi_samples) / len(roi_samples) if roi_samples else 0.0

    pub_roi: dict[str, list[float]] = defaultdict(list)
    series_roi: dict[str, list[float]] = defaultdict(list)
    for item in items:
        if item.estimated_value > 0 and item.cost_basis > 0:
            pub_roi[item.publisher].append(item.roi_pct)
            series_roi[item.series].append(item.roi_pct)

    snap.total_cost_basis = round(total_cost, 2)
    snap.total_estimated_value = round(total_value, 2)
    snap.total_unrealized_gain = round(total_unreal, 2)
    snap.total_unrealized_gain_pct = round(unreal_pct, 2)
    snap.total_realized_gain = round(total_realized, 2)
    snap.total_realized_gain_pct = round(realized_pct, 2)
    snap.average_roi_pct = round(avg_roi, 2)
    snap.portfolio_cagr_pct = round(avg_roi * 0.25, 2) if roi_samples else None
    snap.best_performer_title = best[0]
    snap.worst_performer_title = worst[0]
    snap.largest_position_title = largest[0]
    snap.metadata_json = {
        "book_roi_top": sorted(
            [{"title": i.title, "roi_pct": i.roi_pct} for i in items if i.estimated_value > 0],
            key=lambda x: x["roi_pct"],
            reverse=True,
        )[:15],
        "publisher_roi": {k: round(sum(v) / len(v), 2) for k, v in pub_roi.items() if v},
        "series_roi": {k: round(sum(v) / len(v), 2) for k, v in list(series_roi.items())[:25] if v},
        "item_count": len(items),
    }
    session.add(snap)
    session.flush()
    return snap
