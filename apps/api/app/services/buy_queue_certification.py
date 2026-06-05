"""P62 Buy Queue certification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.models.buy_queue_intelligence import BUY_QUEUE_ITEM_WATCH
from app.services.buy_queue_service import (
    build_buy_queue,
    get_latest_buy_queue_snapshot,
    list_buy_queue_items,
    update_buy_queue_item_status,
)
from app.services.purchase_budgets import get_purchase_budget_row


def certify_buy_queue(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    snapshot = build_buy_queue(session, owner_user_id=owner_user_id)
    items, total = list_buy_queue_items(session, snapshot_id=int(snapshot.id or 0), limit=500, offset=0)

    ok_build = snapshot.total_items == total and total >= 0
    if not ok_build:
        notes.append("Snapshot row count mismatch.")
    else:
        notes.append(f"Built snapshot {snapshot.id} with {total} items.")

    ok_order = True
    if len(items) >= 2:
        for prev, cur in zip(items, items[1:], strict=False):
            if cur.priority_score > prev.priority_score:
                ok_order = False
                break
    if not ok_order:
        notes.append("Items not ordered by priority_score descending.")
    else:
        notes.append("Priority ordering verified.")

    ok_budget = True
    cap = 0.0
    if budget.is_active:
        cap = float(budget.weekly_budget or 0) or float(budget.monthly_budget or 0)
    if cap > 0:
        buy_cost = sum(i.estimated_cost for i in items if i.status not in (BUY_QUEUE_ITEM_WATCH,))
        demoted = [i for i in items if "budget_demoted" in (i.buy_reason or "")]
        if buy_cost > cap + 0.01 and not demoted:
            ok_budget = False
            notes.append("Budget exceeded without demotions.")
        else:
            notes.append(f"Budget cap={cap:.2f}; demoted={len(demoted)}.")
    else:
        notes.append("Budget inactive or zero cap; skip budget gate.")

    ok_qty = all(i.quantity_recommended >= 1 for i in items)
    if not ok_qty:
        notes.append("Missing quantity_recommended.")
    else:
        notes.append("Quantities present on all items.")

    ok_status = False
    if items:
        test_item = items[0]
        updated = update_buy_queue_item_status(
            session,
            item_id=int(test_item.id or 0),
            owner_user_id=owner_user_id,
            status="ORDERED",
        )
        ok_status = updated.status == "ORDERED"
        update_buy_queue_item_status(
            session,
            item_id=int(test_item.id or 0),
            owner_user_id=owner_user_id,
            status=test_item.status,
        )
    if ok_status:
        notes.append("Status PATCH round-trip OK.")
    elif items:
        notes.append("Status update failed.")

    certified = ok_build and ok_order and ok_budget and ok_qty and ok_status and total > 0
    latest = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
    if latest is None:
        certified = False
        notes.append("No latest non-archived snapshot.")

    return {
        "component": "P62-02_BUY_QUEUE",
        "certified": certified,
        "status": "PASS" if certified else "NOT_READY",
        "summary": "Buy queue certified" if certified else "Buy queue not certified",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
