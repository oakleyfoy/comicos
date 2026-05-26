# Liquidity Engine Architecture

## Purpose

`P36-04` teaches ComicOS how inventory moves through the market using deterministic, evidence-backed snapshots derived from the listing registry and realized sales ledger.

This layer is descriptive only. It measures movement, staleness, and relist behavior, but it does not predict future performance, recommend actions, repricing, or auto-close stale listings.

## Models

- `InventoryLiquiditySnapshot` stores append-only inventory-level liquidity snapshots.
- `InventoryLiquidityEvidence` stores the evidence rows that explain a snapshot.
- `ListingVelocitySnapshot` stores per-listing movement metrics.
- `ListingStalenessEvent` stores append-only stale-threshold events.

Inventory rows are keyed by owner, inventory item, canonical issue, channel, evaluation window, and snapshot date so reruns stay idempotent for the same signature.

## Deterministic Liquidity Math

All calculations use Decimal-safe arithmetic and stable rounding.

- `days_active = sold_at - activated_at` for completed listings, or `snapshot_date - activated_at` for active listings.
- `sell_through_rate_pct = successful_sales / total_completed_listing_cycles`
- `relist_rate_pct = relisted_listings / total_listing_cycles`
- `stale_listing_rate_pct = stale_listings / active_or_completed_listings`

The engine stores the summary metrics and also preserves evidence rows so each snapshot can be explained after the fact.

## Stale Thresholds

Listings become stale by deterministic age bands:

- `30+ days` -> `STALE_WARNING`
- `60+ days` -> `STALE_CONFIRMED`
- `120+ days` -> `LONG_RUNNING`

The phase is observational only. No listing is auto-closed.

## Liquidity Classifications

The current snapshot status buckets are intentionally simple constants:

- `HIGH` — strong sell-through, low stale rate, low relist rate
- `MODERATE` — balanced performance
- `LOW` — weak sell-through or elevated stale behavior
- `ILLIQUID` — very low sell-through with very high stale behavior
- `INSUFFICIENT_DATA` — too few completed cycles for a reliable classification

Confidence buckets are also deterministic:

- `HIGH`
- `MEDIUM`
- `LOW`

## Evidence Model

Evidence rows preserve the reason a snapshot exists:

- `SALE`
- `ACTIVE_LISTING`
- `FAILED_LISTING`
- `RELIST`
- `STALE`

Each evidence row points back to the source listing and/or sale when available. The snapshot checksum is derived from the snapshot signature plus its evidence rows.

## Replay Behavior

Generating the same snapshot signature twice returns the existing row instead of creating a duplicate.

This keeps the ledger append-safe:

- no destructive recalculation
- no duplicate evidence for the same snapshot signature
- no hidden mutation of listing state

## Owner vs Ops API Split

Owner routes are scoped to the authenticated owner and may materialize the current deterministic snapshot set:

- `GET /liquidity`
- `GET /liquidity/{id}`
- `GET /liquidity/evidence`
- `GET /listing-velocity`
- `GET /listing-staleness-events`
- `GET /liquidity/dashboard-summary`

Ops routes are read-only mirrors:

- `GET /ops/liquidity`
- `GET /ops/liquidity/{id}`
- `GET /ops/liquidity-evidence`
- `GET /ops/listing-velocity`
- `GET /ops/listing-staleness-events`
- `GET /ops/liquidity/dashboard-summary`

## Non-Goals

- Predictive liquidity scoring
- Forecasting
- Automated repricing
- Recommendations or sell/hold guidance
- Marketplace-wide prediction layers
- ML-based sell-through inference
- Dynamic threshold tuning
- Automatic listing closure or inventory mutation
