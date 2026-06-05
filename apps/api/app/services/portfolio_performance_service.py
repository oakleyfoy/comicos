"""P63-01 Portfolio Performance Intelligence."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.market_intelligence_platform import (
    PortfolioPerformanceItem,
    PortfolioPerformanceSnapshot,
    utc_now,
)
from app.services.market_intelligence_inventory import load_owner_inventory_rows, performance_tier


def get_latest_portfolio_snapshot(session: Session, *, owner_user_id: int) -> PortfolioPerformanceSnapshot | None:
    return session.exec(
        select(PortfolioPerformanceSnapshot)
        .where(PortfolioPerformanceSnapshot.owner_user_id == owner_user_id)
        .order_by(PortfolioPerformanceSnapshot.generated_at.desc(), PortfolioPerformanceSnapshot.id.desc())
    ).first()


def list_portfolio_items(
    session: Session,
    *,
    snapshot_id: int,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[PortfolioPerformanceItem], int]:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    rows = session.exec(
        select(PortfolioPerformanceItem)
        .where(PortfolioPerformanceItem.snapshot_id == snapshot_id)
        .order_by(PortfolioPerformanceItem.unrealized_gain_pct.desc(), PortfolioPerformanceItem.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(
        session.exec(select(PortfolioPerformanceItem).where(PortfolioPerformanceItem.snapshot_id == snapshot_id)).all()
    )
    return rows, total


def top_gainers(session: Session, *, snapshot_id: int, limit: int = 10) -> list[PortfolioPerformanceItem]:
    return list(
        session.exec(
            select(PortfolioPerformanceItem)
            .where(PortfolioPerformanceItem.snapshot_id == snapshot_id)
            .where(PortfolioPerformanceItem.unrealized_gain > 0)
            .order_by(PortfolioPerformanceItem.unrealized_gain.desc(), PortfolioPerformanceItem.id.asc())
            .limit(limit)
        ).all()
    )


def top_losers(session: Session, *, snapshot_id: int, limit: int = 10) -> list[PortfolioPerformanceItem]:
    return list(
        session.exec(
            select(PortfolioPerformanceItem)
            .where(PortfolioPerformanceItem.snapshot_id == snapshot_id)
            .where(PortfolioPerformanceItem.unrealized_gain < 0)
            .order_by(PortfolioPerformanceItem.unrealized_gain.asc(), PortfolioPerformanceItem.id.asc())
            .limit(limit)
        ).all()
    )


def build_portfolio_performance_snapshot(session: Session, *, owner_user_id: int) -> PortfolioPerformanceSnapshot:
    today = date.today()
    inv_rows = load_owner_inventory_rows(session, owner_user_id=owner_user_id)
    snap = PortfolioPerformanceSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        total_items=0,
        metadata_json={},
    )
    session.add(snap)
    session.flush()

    total_cost = 0.0
    total_value = 0.0
    gainers = 0
    losers = 0
    items: list[PortfolioPerformanceItem] = []
    for row in inv_rows:
        has_value = row.current_value > 0 or row.unrealized_gain != 0
        tier = performance_tier(gain_pct=row.unrealized_gain_pct, has_value=has_value and row.current_value > 0)
        total_cost += row.cost_basis
        total_value += row.current_value
        if row.unrealized_gain > 0:
            gainers += 1
        elif row.unrealized_gain < 0:
            losers += 1
        items.append(
            PortfolioPerformanceItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=row.copy_id,
                title=row.title,
                publisher=row.publisher,
                issue_number=row.issue_number,
                quantity=row.quantity,
                cost_basis=row.cost_basis,
                current_value=row.current_value,
                unrealized_gain=row.unrealized_gain,
                unrealized_gain_pct=row.unrealized_gain_pct,
                demand_score=50.0,
                velocity_score=50.0,
                recommendation_score=50.0,
                performance_tier=tier,
                notes_json={"grade_status": row.grade_status},
            )
        )

    total_gain = total_value - total_cost
    gain_pct = (total_gain / total_cost * 100.0) if total_cost > 0 else 0.0
    snap.total_items = len(items)
    snap.total_cost_basis = round(total_cost, 2)
    snap.total_current_value = round(total_value, 2)
    snap.total_unrealized_gain = round(total_gain, 2)
    snap.total_unrealized_gain_pct = round(gain_pct, 2)
    snap.top_gainers_count = gainers
    snap.top_losers_count = losers
    session.add(snap)
    for item in items:
        session.add(item)
    session.commit()
    session.refresh(snap)
    return snap
