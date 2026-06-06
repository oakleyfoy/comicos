"""P74-02 quantity recommendations (advisory; no auto-ordering)."""

from __future__ import annotations

from app.services.purchase_priority_score import (
    P74_ACTION_BUY,
    P74_ACTION_MUST_BUY,
    P74_ACTION_PASS,
    P74_ACTION_WATCH,
)


def recommend_quantity(
    *,
    purchase_action: str,
    priority_score: int,
    owned_quantity: int,
    ordered_quantity: int,
    is_number_one: bool,
    demand_score: float,
    foc_days: int | None,
) -> tuple[int, str]:
    action = purchase_action.upper()
    if action == P74_ACTION_PASS:
        return 0, "Priority below preorder threshold; pass on additional copies."

    base = 0
    if action == P74_ACTION_WATCH:
        base = 1
    elif action == P74_ACTION_BUY:
        base = 2
    elif action == P74_ACTION_MUST_BUY:
        base = 3

    qty = base
    if action in {P74_ACTION_BUY, P74_ACTION_MUST_BUY} and priority_score >= 75:
        qty = max(qty, 2)

    if is_number_one and demand_score >= 65 and action != P74_ACTION_WATCH:
        qty = min(4, qty + 1)
    if demand_score >= 75 and foc_days is not None and foc_days <= 7:
        qty = min(4, qty + 1)

    if priority_score < 60:
        qty = min(qty, 1)

    inventory = owned_quantity + ordered_quantity
    if inventory >= qty:
        qty = max(0, qty - 1)
    if inventory >= 4:
        qty = 0

    if qty >= 4:
        label = "4+"
        reason = (
            f"Strong preorder signal (priority {priority_score}); default strong-buy strategy suggests "
            f"{label} copies after owned={owned_quantity} ordered={ordered_quantity}."
        )
        return 4, reason

    parts: list[str] = [f"Action {action}", f"priority {priority_score}"]
    if foc_days is not None and foc_days <= 7:
        parts.append("FOC approaching")
    if demand_score >= 70:
        parts.append("elevated demand")
    if is_number_one:
        parts.append("#1 issue boost")
    if inventory:
        parts.append(f"adjusted for owned={owned_quantity} ordered={ordered_quantity}")
    return qty, "; ".join(parts) + "."
