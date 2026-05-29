# P43-07 Whatnot / Live-Sale Workflows

P43-07 establishes ComicOS internal live-sale workflow infrastructure for organizations that run Whatnot-style sessions without connecting to external Whatnot APIs.

## Scope

This phase covers:

- live-sale session planning
- run-of-show queue ordering
- item status transitions
- buyer claim tracking
- append-only live-sale lineage
- organization-scoped visibility and management

This phase does not:

- connect to Whatnot APIs
- stream video
- process payments
- manage shipping
- ingest real Whatnot orders
- implement chat or barcode automation

## Data Model

### LiveSaleSession

Sessions capture the operational unit for a planned or live Whatnot sale.

Key fields:

- `organization_id`
- `marketplace_account_id`
- `session_name`
- `session_status`
- `planned_start_at`
- `planned_end_at`
- `started_at`
- `ended_at`
- `created_by_user_id`
- `created_at`
- `updated_at`

### LiveSaleQueueItem

Queue items define the deterministic run-of-show order for inventory and listing drafts.

Key fields:

- `live_sale_session_id`
- `inventory_item_id`
- `marketplace_listing_draft_id`
- `queue_position`
- `item_status`
- `planned_price`
- `actual_sale_price`

### LiveSaleClaim

Claims track buyer intent and internal claim state.

Key fields:

- `live_sale_session_id`
- `live_sale_queue_item_id`
- `buyer_identifier`
- `claim_status`
- `claimed_price`
- `claimed_at`

### LiveSaleEvent

The live-sale history is append-only.

Recorded events include:

- `live_sale_session_created`
- `live_sale_session_started`
- `live_sale_session_ended`
- `live_sale_queue_item_added`
- `live_sale_queue_reordered`
- `live_sale_item_active`
- `live_sale_item_sold`
- `live_sale_item_passed`
- `live_sale_claim_created`
- `live_sale_claim_status_updated`
- `duplicate_live_sale_claim_detected`
- `unauthorized_live_sale_access_attempt`

## Status Semantics

Session statuses:

- `planned`
- `live`
- `ended`
- `cancelled`

Queue item statuses:

- `queued`
- `active`
- `sold`
- `passed`
- `removed`

Claim statuses:

- `claimed`
- `confirmed`
- `cancelled`

## Workflow Guarantees

- queue ordering is deterministic through explicit `queue_position` updates
- timestamps are replay-safe and UTC-aware
- organization ownership is enforced on every read and write
- unauthorized attempts are written to live-sale lineage before the request fails closed
- duplicate claims are detected deterministically and return the existing claim record
- no destructive cascades are used for the workflow tables

## Future Integrations

The current implementation leaves room for future integration contracts with Whatnot and other live-commerce platforms, but it intentionally stops at internal operational planning and lineage tracking.
