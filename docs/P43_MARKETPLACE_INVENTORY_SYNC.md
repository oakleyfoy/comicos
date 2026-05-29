# P43 Marketplace Inventory Sync

P43-03 establishes deterministic marketplace inventory synchronization infrastructure for ComicOS organizations. This phase introduces internal state tracking, reconciliation, conflict detection, and append-only sync lineage without calling external marketplace APIs or mutating inventory automatically.

## Scope

Included:

- marketplace inventory state registry per account + listing draft
- append-only sync runs and sync events
- deterministic reconciliation and conflict detection
- sync diagnostics and operator-facing workspace shells
- future publish/sync dependency contracts

Excluded:

- live marketplace API polling
- publish or unpublish workflows
- pricing updates
- order ingestion, webhook handling, or sales flows
- automatic conflict resolution

## Core model

### `MarketplaceInventoryState`

Current tracked external-facing inventory state for a marketplace listing draft:

- organization + marketplace account ownership
- deterministic `marketplace_listing_identifier`
- local quantity vs marketplace quantity
- sync status and last sync timestamp

State rows are idempotent per `(marketplace_account_id, marketplace_listing_draft_id)`.

### `MarketplaceInventorySyncRun`

Append-only run history for manual or future automated sync passes:

- run type
- status
- processed record count
- detected conflict count
- started/completed timestamps

### `MarketplaceInventoryConflict`

Detected reconciliation gap between local and marketplace-tracked state:

- `quantity_mismatch`
- `missing_local_inventory`
- `missing_marketplace_inventory`
- `stale_marketplace_state`
- `stale_local_state`

Conflict statuses:

- `detected`
- `reviewed`
- `resolved`

### `MarketplaceInventorySyncEvent`

Append-only lineage for sync activity:

- `marketplace_sync_started`
- `marketplace_sync_completed`
- `marketplace_sync_failed`
- `marketplace_conflict_detected`
- `marketplace_reconciliation_generated`
- `unauthorized_marketplace_sync_access_attempt`

Events are immutable and ordered by `(created_at, id)`.

## Sync lifecycle

1. User triggers sync run
2. Service registers or updates marketplace inventory state rows from listing drafts
3. Reconciliation compares local listing quantity against marketplace-tracked quantity
4. Deterministic conflicts are upserted for active differences
5. Sync run completes with processed counts and conflict totals
6. Reconciliation reports summarize tracked states and active issues

No local inventory or external marketplace quantities are auto-mutated in P43-03.

## Reconciliation rules

The reconciliation layer is fail-closed and deterministic:

- archived or missing local drafts become `missing_local_inventory`
- zero / absent marketplace quantity against positive local quantity becomes `missing_marketplace_inventory`
- non-zero quantity mismatch becomes `quantity_mismatch`
- newer local updates than last sync become `stale_marketplace_state`
- newer marketplace-tracked sync timestamp with differing non-zero quantities becomes `stale_local_state`

Conflict ordering is stable and code-driven.

## Sync status model

Sync statuses:

- `pending`
- `running`
- `completed`
- `failed`

Newly tracked states begin pending and then settle into completed or failed based on reconciliation output.

## Authorization

Sync access follows marketplace organization permissions:

- view requires `organization:view`
- manage requires `organization:update`

Unauthorized sync access attempts produce dedicated sync lineage events rather than reusing listing/account lineage.

## API surface

Organization-scoped v1 endpoints:

- `GET /organizations/{id}/marketplace-sync`
- `GET /organizations/{id}/marketplace-sync/runs`
- `GET /organizations/{id}/marketplace-sync/conflicts`
- `GET /organizations/{id}/marketplace-sync/states`
- `POST /organizations/{id}/marketplace-sync/run`
- `POST /organizations/{id}/marketplace-sync/reconcile`

## Future dependencies

Later marketplace publishing and live-sync phases can depend on:

- current `MarketplaceInventoryState` rows as the internal registry
- append-only `MarketplaceInventorySyncRun` history for replay diagnostics
- deterministic `MarketplaceInventoryConflict` records for operator review
- sync diagnostics for workflow gating and health reporting

Engine version key: `marketplace_inventory_sync: P43-03`.
