"""P63-02 Sell Signal Intelligence."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.market_intelligence_platform import (
    SELL_ACTION_CONSIDER,
    SELL_ACTION_GRADE_FIRST,
    SELL_ACTION_HOLD,
    SELL_ACTION_SELL_NOW,
    SELL_ACTION_WATCH,
    SELL_STATUS_NEW,
    SellSignalItem,
    SellSignalSnapshot,
    utc_now,
)
from app.services.market_intelligence_inventory import count_identity_copies, load_owner_inventory_rows
from app.services.sell_candidate_engine import REC_HOLD, REC_SELL, REC_STRONG_SELL, evaluate_sell_candidate_for_copy
from app.models.asset_ledger import InventoryCopy


def get_latest_sell_signal_snapshot(session: Session, *, owner_user_id: int) -> SellSignalSnapshot | None:
    return session.exec(
        select(SellSignalSnapshot)
        .where(SellSignalSnapshot.owner_user_id == owner_user_id)
        .order_by(SellSignalSnapshot.generated_at.desc(), SellSignalSnapshot.id.desc())
    ).first()


def list_sell_signal_items(
    session: Session,
    *,
    snapshot_id: int,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[SellSignalItem], int]:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    rows = session.exec(
        select(SellSignalItem)
        .where(SellSignalItem.snapshot_id == snapshot_id)
        .order_by(SellSignalItem.sell_score.desc(), SellSignalItem.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(session.exec(select(SellSignalItem).where(SellSignalItem.snapshot_id == snapshot_id)).all())
    return rows, total


def update_sell_signal_item_status(session: Session, *, item_id: int, owner_user_id: int, status: str) -> SellSignalItem:
    row = session.get(SellSignalItem, item_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("sell_signal_item_not_found")
    row.status = status.strip().upper()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _map_action(rec: str, *, grade_status: str, fmv: float) -> tuple[str, float, float, str]:
    hold_score = 50.0
    sell_score = 50.0
    reason = rec.lower()
    if rec == REC_STRONG_SELL:
        return SELL_ACTION_SELL_NOW, 88.0, 15.0, "strong_sell_candidate"
    if rec == REC_SELL:
        return SELL_ACTION_CONSIDER, 72.0, 28.0, "sell_candidate"
    if grade_status == "raw" and fmv >= 75.0:
        return SELL_ACTION_GRADE_FIRST, 35.0, 65.0, "grade_before_sell"
    if rec == REC_HOLD:
        return SELL_ACTION_HOLD, 25.0, 75.0, "hold_recommended"
    return SELL_ACTION_WATCH, 40.0, 60.0, reason or "review"


def build_sell_signals(session: Session, *, owner_user_id: int) -> SellSignalSnapshot:
    today = date.today()
    inv_rows = load_owner_inventory_rows(session, owner_user_id=owner_user_id)
    copy_counts = count_identity_copies(session, owner_user_id=owner_user_id)
    snap = SellSignalSnapshot(owner_user_id=owner_user_id, snapshot_date=today, generated_at=utc_now(), metadata_json={})
    session.add(snap)
    session.flush()

    strong = consider = hold = 0
    scored: list[tuple[float, SellSignalItem]] = []
    for row in inv_rows:
        copy = session.get(InventoryCopy, row.copy_id)
        if copy is None:
            continue
        key = (row.publisher.lower(), row.title.lower(), row.issue_number.lower())
        group_size = copy_counts.get(key, 1)
        copy_index = 0
        is_excess = group_size > 2 and copy_index < group_size - 1
        fmv = row.current_value if row.current_value > 0 else 10.0
        rec, conf, rationale = evaluate_sell_candidate_for_copy(
            copy=copy,
            copy_index_in_group=copy_index,
            group_size=group_size,
            is_excess=is_excess,
            concentration_score=0.05,
            fmv=fmv,
            grading=None,
            liquidity_score=0.5,
        )
        action, sell_score, hold_score, reason = _map_action(rec, grade_status=row.grade_status, fmv=fmv)
        if action == SELL_ACTION_SELL_NOW:
            strong += 1
        elif action == SELL_ACTION_CONSIDER:
            consider += 1
        else:
            hold += 1
        velocity = 45.0
        demand = 50.0
        if rec in (REC_SELL, REC_STRONG_SELL) and row.unrealized_gain_pct > 30:
            demand = 55.0
        item = SellSignalItem(
            snapshot_id=int(snap.id or 0),
            owner_user_id=owner_user_id,
            inventory_copy_id=row.copy_id,
            title=row.title,
            publisher=row.publisher,
            issue_number=row.issue_number,
            sell_score=sell_score,
            hold_score=hold_score,
            current_value=row.current_value,
            cost_basis=row.cost_basis,
            unrealized_gain=row.unrealized_gain,
            unrealized_gain_pct=row.unrealized_gain_pct,
            demand_score=demand,
            velocity_score=velocity,
            quantity_owned=group_size,
            grade_status=row.grade_status,
            sell_reason=rationale or reason,
            recommended_action=action,
            confidence="HIGH" if conf >= 0.75 else "MEDIUM" if conf >= 0.5 else "LOW",
            status=SELL_STATUS_NEW,
        )
        scored.append((sell_score, item))

    scored.sort(key=lambda t: (-t[0], t[1].inventory_copy_id))
    for _, item in scored:
        session.add(item)

    snap.total_items = len(scored)
    snap.strong_sell_count = strong
    snap.consider_sell_count = consider
    snap.hold_count = hold
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
