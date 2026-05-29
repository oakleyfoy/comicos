# P43-05 Marketplace Pricing / Offer Engine

This phase adds ComicOS marketplace pricing infrastructure without changing any live marketplace prices.

## What It Models

- `MarketplacePriceRecommendation` records deterministic price suggestions for an organization-owned marketplace listing.
- `MarketplaceOffer` records inbound offers for later internal review.
- `MarketplacePricingRule` stores organization-scoped pricing rules with replay-safe JSON payloads.
- `MarketplacePricingEvent` captures append-only lineage for pricing generation, review, rule changes, and offer lifecycle events.

## Rule Lifecycle

Rules are evaluated deterministically in priority order and then by stable timestamps and IDs. Supported rule types are:

- `fixed_margin`
- `minimum_floor`
- `maximum_ceiling`
- `round_to_ending`
- `marketplace_fee_buffer`

Rules are validated fail-closed and remain internal-only. They do not publish prices externally.

## Recommendation Model

Recommendations are generated from the current listing price plus the active organization rules. Each record stores:

- the suggested price
- the current listing price
- optional floor and ceiling bounds
- the recommendation reason
- generation and review timestamps

Recommendations can be reviewed internally as `reviewed`, `applied_internal`, or `dismissed`.

## Offer Tracking Model

Offers are ingested deterministically and deduplicated by marketplace account plus marketplace offer identifier. Offer status remains internal-only and supports:

- `received`
- `reviewed`
- `accepted_internal`
- `rejected_internal`
- `expired`

Duplicate offers generate lineage events instead of creating duplicate records.

## Replay-Safe Guarantees

- organization-scoped visibility and management checks are fail-closed
- all user-facing lists use stable ordering
- pricing events are append-only
- no automatic repricing jobs are introduced
- no external marketplace APIs are called

## Future Dependencies

This foundation is intended to support future repricing workflows and marketplace analytics, but those capabilities are intentionally out of scope here.
