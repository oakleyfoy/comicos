# P43 API Reference

## Purpose

This is the authoritative v1 API inventory for the completed P43 marketplace layer. Endpoints are grouped by subsystem and described with their permission and visibility behavior.

## Marketplace Accounts

- `GET /api/v1/organizations/{organization_id}/marketplaces`
  - Permissions: organization view
  - Response: returns the organization-owned account list and registry metadata
  - Visibility: deny-by-default for non-members and cross-org access
- `GET /api/v1/organizations/{organization_id}/marketplaces/{account_id}`
  - Permissions: organization view
  - Response: returns a single account and its lineage
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplaces/connect`
  - Permissions: organization update
  - Response: creates or reactivates an account connection
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplaces/verify`
  - Permissions: organization update
  - Response: updates verification state and records lineage
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplaces/disconnect`
  - Permissions: organization update
  - Response: marks the account disconnected and appends lineage
  - Visibility: org-scoped

## Marketplace Listings

- `GET /api/v1/organizations/{organization_id}/marketplace-listings`
  - Permissions: organization view
  - Response: deterministic draft list and summary
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}`
  - Permissions: organization view
  - Response: returns draft and projection state
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-listings`
  - Permissions: organization update
  - Response: creates a listing draft
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}`
  - Permissions: organization update
  - Response: updates a draft deterministically
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-listings/{listing_id}/archive`
  - Permissions: organization update
  - Response: archives the draft and records lineage
  - Visibility: org-scoped

## Inventory Sync

- `GET /api/v1/organizations/{organization_id}/marketplace-sync`
  - Permissions: organization view
  - Response: current sync overview
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-sync/runs`
  - Permissions: organization view
  - Response: sync run history
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-sync/conflicts`
  - Permissions: organization view
  - Response: conflict history
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-sync/states`
  - Permissions: organization view
  - Response: reconciliation state rows
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-sync/run`
  - Permissions: organization update
  - Response: creates a reconciliation run
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-sync/reconcile`
  - Permissions: organization update
  - Response: generates a reconciliation report
  - Visibility: org-scoped

## Marketplace Orders

- `GET /api/v1/organizations/{organization_id}/marketplace-orders`
  - Permissions: organization view
  - Response: imported order list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-orders/{order_id}`
  - Permissions: organization view
  - Response: order detail and lineage
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-orders/import`
  - Permissions: organization update
  - Response: imports or deduplicates an order
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-orders/reconcile`
  - Permissions: organization update
  - Response: generates a reconciliation report
  - Visibility: org-scoped

## Marketplace Pricing

- `GET /api/v1/organizations/{organization_id}/marketplace-pricing/rules`
  - Permissions: organization view
  - Response: pricing rule list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-pricing/recommendations`
  - Permissions: organization view
  - Response: price recommendation list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-pricing/offers`
  - Permissions: organization view
  - Response: offer list
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-pricing/rules`
  - Permissions: organization update
  - Response: creates a pricing rule
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-pricing/recommendations/generate`
  - Permissions: organization update
  - Response: creates a recommendation
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-pricing/offers/ingest`
  - Permissions: organization update
  - Response: ingests or deduplicates an offer
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/marketplace-pricing/recommendations/{recommendation_id}/review`
  - Permissions: organization update
  - Response: updates review status
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/marketplace-pricing/offers/{offer_id}/status`
  - Permissions: organization update
  - Response: updates internal offer status
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/marketplace-pricing/rules/{rule_id}`
  - Permissions: organization update
  - Response: updates a pricing rule
  - Visibility: org-scoped

## Marketplace Events

- `GET /api/v1/organizations/{organization_id}/marketplace-events`
  - Permissions: organization view
  - Response: event list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-events/{event_id}`
  - Permissions: organization view
  - Response: event detail
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-events/runs`
  - Permissions: organization view
  - Response: processing run list
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-events/ingest`
  - Permissions: organization update
  - Response: ingests or deduplicates an event
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-events/process`
  - Permissions: organization update
  - Response: creates a processing run
  - Visibility: org-scoped

## Live Sales

- `GET /api/v1/organizations/{organization_id}/live-sales`
  - Permissions: organization view
  - Response: live-sale session list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/live-sales/{session_id}`
  - Permissions: organization view
  - Response: session detail
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/live-sales/{session_id}/queue`
  - Permissions: organization view
  - Response: queue items
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/live-sales/{session_id}/claims`
  - Permissions: organization view
  - Response: claim history
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/live-sales`
  - Permissions: organization update
  - Response: creates a live-sale session
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/live-sales/{session_id}/start`
  - Permissions: organization update
  - Response: starts the session
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/live-sales/{session_id}/end`
  - Permissions: organization update
  - Response: ends the session
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/live-sales/{session_id}/queue`
  - Permissions: organization update
  - Response: adds a queue item
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/live-sales/{session_id}`
  - Permissions: organization update
  - Response: updates session metadata
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/reorder`
  - Permissions: organization update
  - Response: reorders queue items deterministically
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/live-sales/{session_id}/queue/{queue_item_id}/status`
  - Permissions: organization update
  - Response: updates queue item status
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/live-sales/{session_id}/claims`
  - Permissions: organization update
  - Response: creates a claim
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/live-sales/{session_id}/claims/{claim_id}`
  - Permissions: organization update
  - Response: updates claim status
  - Visibility: org-scoped

## Shopify Sync

- `GET /api/v1/organizations/{organization_id}/shopify`
  - Permissions: organization view
  - Response: Shopify sync overview
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/shopify/mappings`
  - Permissions: organization view
  - Response: mapping list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/shopify/sync-states`
  - Permissions: organization view
  - Response: sync state list
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/shopify/storefront`
  - Permissions: organization update
  - Response: creates a storefront record
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/shopify/mappings`
  - Permissions: organization update
  - Response: creates a mapping
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/shopify/snapshot`
  - Permissions: organization update
  - Response: creates a sync snapshot
  - Visibility: org-scoped
- `PATCH /api/v1/organizations/{organization_id}/shopify/mappings/{mapping_id}`
  - Permissions: organization update
  - Response: updates a mapping deterministically
  - Visibility: org-scoped

## Marketplace Ops

- `GET /api/v1/organizations/{organization_id}/marketplace-ops`
  - Permissions: organization view
  - Response: dashboard summary and lineage
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-ops/metrics`
  - Permissions: organization view
  - Response: metric list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-ops/diagnostics`
  - Permissions: organization view
  - Response: diagnostic list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-ops/snapshots`
  - Permissions: organization view
  - Response: snapshot list
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-ops/snapshot`
  - Permissions: organization update
  - Response: creates an ops snapshot
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-ops/diagnostics/generate`
  - Permissions: organization update
  - Response: generates diagnostics and records lineage
  - Visibility: org-scoped

## Marketplace Analytics

- `GET /api/v1/organizations/{organization_id}/marketplace-analytics`
  - Permissions: organization view
  - Response: analytics dashboard summary and lineage
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-analytics/metrics`
  - Permissions: organization view
  - Response: KPI list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-analytics/trends`
  - Permissions: organization view
  - Response: trend list
  - Visibility: org-scoped
- `GET /api/v1/organizations/{organization_id}/marketplace-analytics/snapshots`
  - Permissions: organization view
  - Response: analytics snapshot list
  - Visibility: org-scoped
- `POST /api/v1/organizations/{organization_id}/marketplace-analytics/generate`
  - Permissions: organization update
  - Response: creates an analytics snapshot
  - Visibility: org-scoped

## Reference Rules

- all responses use the v1 envelope pattern
- all list endpoints use deterministic ordering and stable pagination
- all org-scoped routes fail closed on unauthorized access
- no endpoint in P43 performs live external publishing or webhook hosting
