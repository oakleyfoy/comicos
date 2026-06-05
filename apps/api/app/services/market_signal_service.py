"""P63-04 Market Signal Intelligence."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.market_intelligence_platform import (
    MarketSignalItem,
    MarketSignalSnapshot,
    utc_now,
)
from app.services.portfolio_performance_service import get_latest_portfolio_snapshot, list_portfolio_items
from app.services.sell_signal_service import get_latest_sell_signal_snapshot, list_sell_signal_items
from app.services.p63_acquisition_opportunity_service import get_latest_acquisition_snapshot, list_acquisition_items


SIGNAL_RISING = "RISING_DEMAND"
SIGNAL_COOLING = "COOLING_DEMAND"
SIGNAL_SELL_WINDOW = "SELL_WINDOW"
SIGNAL_SPEC = "SPEC_OPPORTUNITY"
SIGNAL_HOLD = "HOLD_STRENGTH"
SIGNAL_UNDERPRICED = "UNDERPRICED"


def get_latest_market_signal_snapshot(session: Session, *, owner_user_id: int) -> MarketSignalSnapshot | None:
    return session.exec(
        select(MarketSignalSnapshot)
        .where(MarketSignalSnapshot.owner_user_id == owner_user_id)
        .where(MarketSignalSnapshot.scope == "OWNER")
        .order_by(MarketSignalSnapshot.generated_at.desc(), MarketSignalSnapshot.id.desc())
    ).first()


def list_market_signal_items(
    session: Session,
    *,
    snapshot_id: int,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[MarketSignalItem], int]:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    rows = session.exec(
        select(MarketSignalItem)
        .where(MarketSignalItem.snapshot_id == snapshot_id)
        .order_by(MarketSignalItem.market_score.desc(), MarketSignalItem.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(session.exec(select(MarketSignalItem).where(MarketSignalItem.snapshot_id == snapshot_id)).all())
    return rows, total


def build_market_signals(session: Session, *, owner_user_id: int) -> MarketSignalSnapshot:
    today = date.today()
    snap = MarketSignalSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        scope="OWNER",
        metadata_json={},
    )
    session.add(snap)
    session.flush()

    signals: list[MarketSignalItem] = []

    port = get_latest_portfolio_snapshot(session, owner_user_id=owner_user_id)
    if port:
        items, _ = list_portfolio_items(session, snapshot_id=int(port.id or 0), limit=100)
        for p in items:
            if p.unrealized_gain_pct >= 25:
                sig_type = SIGNAL_SELL_WINDOW
                reason = "portfolio_strong_gain"
                market_score = min(100.0, 60 + p.unrealized_gain_pct * 0.5)
            elif p.unrealized_gain_pct <= -10:
                sig_type = SIGNAL_COOLING
                reason = "portfolio_down"
                market_score = 40.0
            else:
                sig_type = SIGNAL_HOLD
                reason = "portfolio_stable"
                market_score = 52.0
            signals.append(
                MarketSignalItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    inventory_copy_id=p.inventory_copy_id,
                    title=p.title,
                    publisher=p.publisher,
                    issue_number=p.issue_number,
                    market_score=round(market_score, 2),
                    demand_score=p.demand_score,
                    velocity_score=p.velocity_score,
                    price_score=55.0,
                    liquidity_score=50.0,
                    opportunity_score=p.recommendation_score,
                    risk_score=max(0.0, 50.0 - p.unrealized_gain_pct),
                    signal_type=sig_type,
                    signal_reason=reason,
                    confidence="MEDIUM",
                    notes_json={"performance_tier": p.performance_tier},
                )
            )

    sell_snap = get_latest_sell_signal_snapshot(session, owner_user_id=owner_user_id)
    if sell_snap:
        sell_items, _ = list_sell_signal_items(session, snapshot_id=int(sell_snap.id or 0), limit=30)
        for s in sell_items:
            if s.recommended_action not in ("SELL_NOW", "CONSIDER_SELLING"):
                continue
            signals.append(
                MarketSignalItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    inventory_copy_id=s.inventory_copy_id,
                    title=s.title,
                    publisher=s.publisher,
                    issue_number=s.issue_number,
                    market_score=s.sell_score,
                    demand_score=s.demand_score,
                    velocity_score=s.velocity_score,
                    price_score=60.0,
                    liquidity_score=55.0,
                    opportunity_score=s.sell_score,
                    risk_score=35.0,
                    signal_type=SIGNAL_SELL_WINDOW,
                    signal_reason=s.sell_reason[:240],
                    confidence=s.confidence,
                    notes_json={"recommended_action": s.recommended_action},
                )
            )

    acq_snap = get_latest_acquisition_snapshot(session, owner_user_id=owner_user_id)
    if acq_snap:
        acq_items, _ = list_acquisition_items(session, snapshot_id=int(acq_snap.id or 0), limit=30)
        for a in acq_items:
            sig_type = SIGNAL_SPEC if a.spec_score >= 70 else SIGNAL_RISING if a.velocity_score >= 65 else SIGNAL_UNDERPRICED
            signals.append(
                MarketSignalItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    external_catalog_issue_id=a.external_catalog_issue_id,
                    title=a.title,
                    publisher=a.publisher,
                    issue_number=a.issue_number,
                    market_score=a.opportunity_score,
                    demand_score=a.demand_score,
                    velocity_score=a.velocity_score,
                    price_score=50.0,
                    liquidity_score=52.0,
                    opportunity_score=a.opportunity_score,
                    risk_score=45.0,
                    signal_type=sig_type,
                    signal_reason=a.reason,
                    confidence="HIGH" if a.opportunity_score >= 75 else "MEDIUM",
                    notes_json={"action": a.action},
                )
            )

    signals.sort(key=lambda r: (-r.market_score, r.title))
    for row in signals[:120]:
        session.add(row)

    snap.total_items = min(len(signals), 120)
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
