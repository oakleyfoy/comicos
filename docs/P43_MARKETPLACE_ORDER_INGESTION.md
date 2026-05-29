# P43 Marketplace Order Ingestion

P43-04 establishes a deterministic marketplace order ingestion foundation for ComicOS organizations. This phase captures imported marketplace orders, imported line items, imported transaction records, reconciliation reports, and append-only order lineage without making marketplace API calls or mutating inventory.

## Lifecycle

Marketplace order imports are organization-scoped and marketplace-account scoped. Each order is uniquely identified by `(marketplace_account_id, marketplace_order_identifier)`, which gives replay-safe duplicate detection across repeated imports. Initial imports create a `marketplace_order_imported` event; replayed imports create `marketplace_duplicate_order_detected` and `marketplace_order_updated` events while reusing the same order identity.

Transaction imports are idempotent within an order via `(marketplace_order_id, transaction_reference)`. Replayed imports do not duplicate existing transaction rows, and only newly observed transaction references produce `marketplace_transaction_imported` lineage events.

## Transaction Model

The order registry is split into four append-only friendly tables:

- `marketplace_orders`: external order identity, buyer identifier, lifecycle state, currency, ordered/imported timestamps
- `marketplace_order_line_items`: imported item-level quantities and pricing, with optional local inventory linkage
- `marketplace_transactions`: imported gross/fee/net financial records and stable transaction references
- `marketplace_order_events`: immutable lineage for imports, updates, reconciliation runs, duplicates, and deny-path audits

No destructive cascades are introduced. Foreign keys remain stable and preserve replay-safe history.

## Reconciliation Model

Transaction reconciliation is deterministic and read-only. Reports scan imported orders and transactions in stable order and emit mismatch codes instead of mutating financial state.

Supported mismatch codes:

- `amount_mismatch`
- `missing_transaction`
- `duplicate_transaction`
- `fee_mismatch`
- `currency_mismatch`

Reconciliation reports are recorded with `marketplace_reconciliation_generated` lineage events so downstream accounting or fulfillment layers can consume the same deterministic history later.

## Duplicate Detection

Duplicate order detection is stable because order identity is marketplace-account scoped. A repeated import of the same external order identifier does not create a second order record. Instead, ComicOS refreshes the stored order snapshot, imports only unseen transaction references, and records duplicate/update events so the ingest history remains auditable.

## Replay-Safe Guarantees

- Order identity is deterministic and unique per marketplace account.
- Transaction identity is deterministic and unique per imported order.
- Lists are returned in stable timestamp/id order.
- Unauthorized visibility and management attempts are logged as immutable order events.
- Validation is fail-closed: invalid states, mismatched currencies, bad arithmetic, and out-of-scope inventory references are rejected before persistence.
- This phase introduces no marketplace API calls, no webhook endpoints, no payment execution, and no automatic inventory updates.

## Future Dependencies

This foundation is intentionally limited so later phases can build on it safely:

- webhook ingestion can map into the same order and transaction identities
- accounting integrations can consume reconciliation reports and order events
- fulfillment workflows can attach shipment state without changing the existing order lineage contract
- marketplace analytics can query the imported registry without changing ingestion semantics
