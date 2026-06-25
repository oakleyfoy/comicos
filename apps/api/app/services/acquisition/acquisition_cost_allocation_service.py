"""P98-12 cost allocation engine.

total_acquisition_cost = total_paid + shipping_paid + tax_paid

Even allocation distributes the total across every inventory copy in the
acquisition, spreading rounding remainder cents deterministically so the
allocated total always equals the acquisition total. Manual allocation accepts
an explicit per-copy map. FMV-weighted allocation is reserved for the future.
"""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import Acquisition, InventoryCopy
from app.models.acquisition import ALLOCATION_MODE_EVEN, ALLOCATION_MODE_MANUAL

CENT = Decimal("0.01")


def quantize_money(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENT)


def even_allocation_amounts(total_cost: Decimal, count: int) -> list[Decimal]:
    """Split total_cost into `count` amounts summing exactly to total_cost."""
    if count <= 0:
        return []
    total_cents = int((quantize_money(total_cost) * 100).to_integral_value())
    base = total_cents // count
    remainder = total_cents - (base * count)
    amounts: list[Decimal] = []
    for index in range(count):
        cents = base + (1 if index < remainder else 0)
        amounts.append((Decimal(cents) / 100).quantize(CENT))
    return amounts


def _copies_for_acquisition(session: Session, acquisition_id: int) -> list[InventoryCopy]:
    return list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.acquisition_id == acquisition_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )


def apply_even_allocation(session: Session, acquisition: Acquisition) -> list[InventoryCopy]:
    copies = _copies_for_acquisition(session, int(acquisition.id or 0))
    amounts = even_allocation_amounts(acquisition.total_acquisition_cost, len(copies))
    for copy, amount in zip(copies, amounts):
        copy.acquisition_cost = amount
        session.add(copy)
    return copies


def apply_manual_allocation(
    session: Session,
    acquisition: Acquisition,
    manual_map: dict[int, Decimal],
) -> list[InventoryCopy]:
    copies = _copies_for_acquisition(session, int(acquisition.id or 0))
    for copy in copies:
        if copy.id in manual_map:
            copy.acquisition_cost = quantize_money(manual_map[int(copy.id)])
            session.add(copy)
    return copies


def recalc_if_even(session: Session, acquisition: Acquisition) -> None:
    """Recalculate even allocation after items are added/removed (P98-12)."""
    if acquisition.allocation_mode == ALLOCATION_MODE_EVEN:
        apply_even_allocation(session, acquisition)


def allocation_summary(session: Session, acquisition: Acquisition) -> tuple[Decimal, bool]:
    """Return (allocated_total, fully_allocated) for an acquisition."""
    copies = _copies_for_acquisition(session, int(acquisition.id or 0))
    allocated = sum((quantize_money(c.acquisition_cost) for c in copies), Decimal("0.00"))
    fully_allocated = quantize_money(allocated) == quantize_money(acquisition.total_acquisition_cost)
    return quantize_money(allocated), fully_allocated


__all__ = [
    "ALLOCATION_MODE_EVEN",
    "ALLOCATION_MODE_MANUAL",
    "allocation_summary",
    "apply_even_allocation",
    "apply_manual_allocation",
    "even_allocation_amounts",
    "quantize_money",
    "recalc_if_even",
]
