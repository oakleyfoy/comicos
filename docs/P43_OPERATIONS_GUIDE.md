# P43 Operations Guide

## Purpose

This guide is written for operators and administrators who need to work with the completed P43 marketplace platform layer. It describes what each workflow does and what it does not do.

## Common Workflows

### Connect Marketplace Account

Use the marketplace account routes to create or verify an organization-owned account record.

Operator outcome:

- a stable marketplace account row is created or reactivated
- credential references are recorded, not raw secrets
- connection lineage is appended

### Create Listing Draft

Create a listing draft against a connected marketplace account and inventory item.

Operator outcome:

- a draft row is created
- validation runs deterministically
- projection data can be generated later

### Generate Listing Projection

Use the listing engine to materialize the current projection and validation state for a draft.

Operator outcome:

- projection content is backend-authoritative
- repeated generation is replay-safe

### Run Inventory Reconciliation

Use the inventory sync layer to inspect reconciliation state and conflicts.

Operator outcome:

- sync state rows are created
- conflicts are surfaced explicitly
- no automatic inventory mutation occurs

### Import Marketplace Order

Use the order ingestion routes to record an imported order and its transactions.

Operator outcome:

- the order is stored internally
- duplicate imports resolve to the same record
- transaction lineage is preserved

### Reconcile Transactions

Use the reconciliation route to compare imported orders and transaction state.

Operator outcome:

- reconciliation reports are generated
- mismatches remain visible for follow-up

### Track Pricing Recommendations

Use pricing rules and offer tracking to inspect internal recommendation state.

Operator outcome:

- rule evaluations are deterministic
- offers can be reviewed internally
- no external negotiation action is triggered

### Ingest Marketplace Events

Use event ingestion to record marketplace events for processing or audit.

Operator outcome:

- events are stored append-only
- duplicates resolve deterministically
- processing runs are recorded separately

### Plan Live Sale

Use live-sale routes to create a session and queue items for the session.

Operator outcome:

- session, queue, and claim state are tracked internally
- queue ordering is deterministic

### Map Shopify Storefront Products

Use Shopify sync routes to map inventory items and listing drafts to storefront products.

Operator outcome:

- storefront records are created internally
- mappings are deterministic and organization-scoped

### Use Ops Dashboard

Use the ops dashboard to review health, metrics, diagnostics, and snapshots.

Operator outcome:

- summaries are derived from internal state
- diagnostics are read-only signals

### Generate Analytics

Use the analytics layer to inspect KPIs, trends, and snapshots.

Operator outcome:

- metrics and trends are deterministic
- snapshot generation is append-only

## Operational Guardrails

- do not expect live vendor publishing in P43
- do not expect automatic remediation in P43
- do not treat dashboard health as external service health
- do not bypass organization-scoped permissions
- do not assume mutable history; lineage is append-only

## Recommended Operator Sequence

1. connect the marketplace account
2. create and validate listing drafts
3. run inventory sync or reconciliation
4. import orders and review transactions
5. manage pricing recommendations and offers
6. ingest events and review processing runs
7. plan live-sale sessions and queue items
8. map Shopify storefront products
9. review ops diagnostics
10. generate analytics snapshots

## Out of Scope

This guide does not describe live eBay, Whatnot, or Shopify publishing, webhook hosting, payment processing, shipping-provider integration, or future P44 mobile/offline workflows.
