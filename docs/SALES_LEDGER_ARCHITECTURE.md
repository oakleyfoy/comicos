# Sales Ledger Architecture

## Purpose

`P36-03` adds the internal realized-sales truth layer for ComicOS. It records actual sold outcomes, fee and shipping adjustments, acquisition-cost linkage, and realized profit or loss without posting to marketplaces or mutating inventory balances.

## Models

- `SaleRecord` is the sale header row and current state row.
- `SaleRecordLineItem` stores item-level sale truth and supports future lot-based sales.
- `SaleFinancialAdjustment` stores auditable fee and cost rows.
- `SaleLifecycleEvent` stores append-only lifecycle history.

Money fields are stored as Decimal-backed database columns and serialized as strings in JSON responses.

## Deterministic Sale Math

The service derives sale totals from line items and financial adjustments using Decimal-only arithmetic and cent rounding.

- `item_subtotal_amount = sum(line_subtotal_amount)`
- `gross_sale_amount = item_subtotal_amount + shipping_charged_amount + tax_collected_amount - discount - refund`
- `net_proceeds_amount = gross_sale_amount - platform_fee_amount - payment_fee_amount - shipping_cost_amount - other_cost_amount`
- `realized_profit_amount = net_proceeds_amount - acquisition_cost_basis_amount`
- `realized_margin_pct = realized_profit_amount / gross_sale_amount`

The math is deterministic for the same sale input, listing state, and currency. Metadata snapshots use JSON-safe stringified Decimal values.

## Lifecycle Rules

- `POST /sales` creates a `DRAFT` sale row and appends a `CREATED` event.
- `PATCH /sales/{id}` is limited to draft-state header updates.
- `POST /sales/{id}/record` transitions the sale to `RECORDED` and appends a `RECORDED` event.
- `POST /sales/{id}/void` transitions the sale to `VOIDED` and appends a `VOIDED` event.

Lifecycle rows are append-only. Reads never mutate lifecycle state.

## Listing Integration

When a sale is recorded and it is linked to a listing, the linked listing is transitioned to `SOLD` if it is currently `READY` or `ACTIVE`.

- `listing.sold_at` is set when the sale is recorded.
- A `ListingLifecycleEvent` with type `SOLD` is appended.
- Replay-safe create requests do not duplicate sale rows or SOLD events.
- Inventory decrementing is intentionally deferred.

## Replay Key Behavior

`POST /sales` accepts an optional `replay_key`.

- The same `owner_user_id + replay_key` returns the existing sale row.
- The replay path does not create duplicate sale lifecycle events.
- The replay path does not duplicate financial adjustments or line items.

## Owner vs Ops API Split

Owner routes are scoped to the authenticated user:

- `GET /sales`
- `POST /sales`
- `GET /sales/{id}`
- `PATCH /sales/{id}`
- `POST /sales/{id}/record`
- `POST /sales/{id}/void`
- `GET /sales/{id}/events`
- `GET /sales/dashboard-summary`

Ops routes are read-only and can inspect all sales data with filters:

- `GET /ops/sales`
- `GET /ops/sales/{id}`
- `GET /ops/sale-events`
- `GET /ops/sale-financial-adjustments`

## Non-Goals

- Live marketplace payment or posting integrations
- Tax filing logic
- Liquidity scoring or recommendations
- Grading ROI or sell/hold advice
- Inventory decrementing
- Accounting exports or settlement reconciliation

