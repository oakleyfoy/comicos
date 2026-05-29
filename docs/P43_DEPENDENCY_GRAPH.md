# P43 Dependency Graph

## Purpose

This document describes the authoritative relationship graph for the P43 marketplace layer. All entities are organization-scoped unless explicitly noted otherwise.

## Core Hierarchy

### 1. Organizations

Organizations are the root ownership boundary. Every marketplace object in P43 hangs from a single organization.

Downstream objects:

- marketplace accounts
- listing drafts
- inventory sync states
- orders and transactions
- pricing rules and offers
- marketplace events
- live-sale workflows
- Shopify mappings and storefronts
- ops diagnostics and snapshots
- analytics metrics, trends, and snapshots

### 2. Marketplace Accounts

Marketplace accounts bind an organization to a marketplace identity and credential reference.

Upstream inputs:

- organization membership
- registry entry

Downstream consumers:

- listing drafts
- inventory sync
- order ingestion
- event ingestion
- live-sale workflows
- Shopify sync
- ops summaries
- analytics summaries

### 3. Listing Drafts and Projections

Listing drafts are the canonical source for marketplace publication intent.

Upstream inputs:

- marketplace account
- inventory copy
- listing validation rules

Downstream consumers:

- inventory reconciliation
- pricing recommendations
- offers
- live-sale queues
- Shopify mappings
- analytics

### 4. Inventory Sync States and Conflicts

Inventory sync states represent reconciliation outcomes between local inventory and marketplace-facing state.

Upstream inputs:

- listing drafts
- organization inventory

Downstream consumers:

- ops diagnostics
- analytics
- follow-on reconciliation reports

### 5. Orders and Transactions

Orders are imported into internal lineage, then paired with transaction history for reconciliation.

Upstream inputs:

- marketplace account
- listing context
- external order identifiers

Downstream consumers:

- pricing
- ops diagnostics
- analytics

### 6. Pricing Rules and Offers

Pricing rules produce recommendations. Offers are tracked internally and updated only through internal workflow actions.

Upstream inputs:

- listing drafts
- orders
- organization-owned pricing policies

Downstream consumers:

- ops diagnostics
- analytics
- future external negotiation contracts

### 7. Marketplace Events

Events are append-only ingestion records with optional processing runs.

Upstream inputs:

- marketplace account
- event identifier
- event payload

Downstream consumers:

- ops diagnostics
- analytics
- future webhook/replay contracts

### 8. Live-Sale Workflows

Live-sale sessions depend on marketplace accounts, listings, and inventory items.

Upstream inputs:

- marketplace account
- listing drafts
- inventory items

Downstream consumers:

- ops diagnostics
- analytics
- future live-sale integration contracts

### 9. Shopify Mappings and Storefronts

Shopify sync records map inventory and listings to storefront products.

Upstream inputs:

- marketplace account
- listing drafts
- inventory copies

Downstream consumers:

- ops diagnostics
- analytics
- future Shopify publishing contracts

### 10. Ops Diagnostics and Analytics Snapshots

Ops diagnostics and analytics snapshots are derived, append-only summaries of the subsystems above.

Upstream inputs:

- all prior P43 marketplace entities

Downstream consumers:

- dashboard views
- operational reporting
- production readiness review

## Deterministic Relationship Rules

- organization ownership is always the top-level boundary
- list ordering uses stable timestamp-plus-id tie breaks
- duplicate detection is replay-safe and does not create divergent histories
- derived snapshots append new rows rather than rewriting prior rows
- unauthorized access is denied by default and recorded in lineage

## Future Integration Points

Future live integrations should attach only at the documented boundaries:

- marketplace publishing from listing drafts
- vendor event ingestion from marketplace accounts
- fulfillment handoff from imported orders
- live-sale vendor synchronization from live-sale sessions
- Shopify product publication from mappings and storefronts
- webhook delivery from event lineage

These are contracts for later phases, not P43 behavior.
