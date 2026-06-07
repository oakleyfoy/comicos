"""P89-04 profit calculation for managed listings."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session

from app.models.asset_ledger import InventoryCopy
from app.models.p89_managed_listing import P89ManagedListing


@dataclass(frozen=True)
class ListingProfitBreakdown:
    gross_sale: float
    total_costs: float
    net_profit: float | None
    profit_margin: float | None
    cost_basis: float | None
    cost_basis_known: bool


def _float(value: float | None) -> float:
    return float(value or 0.0)


def inventory_cost_basis(session: Session, *, inventory_copy_id: int) -> float | None:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None:
        return None
    cost = copy.acquisition_cost
    if cost is None:
        return None
    try:
        amount = float(cost)
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    return round(amount, 2)


def calculate_listing_profit(
    session: Session,
    *,
    listing: P89ManagedListing,
    cost_basis_override: float | None = None,
) -> ListingProfitBreakdown:
    sale = _float(listing.sale_price)
    shipping_in = _float(listing.shipping_charged)
    gross_sale = round(sale + shipping_in, 2)
    fees = _float(listing.marketplace_fees)
    ship_cost = _float(listing.shipping_cost)
    basis = cost_basis_override
    if basis is None:
        basis = inventory_cost_basis(session, inventory_copy_id=int(listing.inventory_copy_id))
    cost_basis_known = basis is not None
    variable_costs = fees + ship_cost
    if cost_basis_known:
        total_costs = round(variable_costs + float(basis), 2)
        net_profit = round(gross_sale - total_costs, 2)
        margin = round((net_profit / gross_sale * 100.0) if gross_sale > 0 else 0.0, 2)
        return ListingProfitBreakdown(
            gross_sale=gross_sale,
            total_costs=total_costs,
            net_profit=net_profit,
            profit_margin=margin,
            cost_basis=float(basis),
            cost_basis_known=True,
        )
    total_costs = round(variable_costs, 2)
    return ListingProfitBreakdown(
        gross_sale=gross_sale,
        total_costs=total_costs,
        net_profit=None,
        profit_margin=None,
        cost_basis=None,
        cost_basis_known=False,
    )


def apply_profit_to_listing(session: Session, *, listing: P89ManagedListing) -> ListingProfitBreakdown:
    breakdown = calculate_listing_profit(session, listing=listing)
    if breakdown.cost_basis_known and breakdown.net_profit is not None:
        listing.net_profit = breakdown.net_profit
    else:
        listing.net_profit = None
    return breakdown
