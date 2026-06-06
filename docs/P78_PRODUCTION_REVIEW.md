# P78 Sell Workflow & Marketplace — Production Review

## Architecture summary

P78 closes the collector selling loop: P78-01 prepares what to sell (queue, drafts, bundles, pricing); P78-02 publishes to marketplaces (eBay first), reserves inventory, syncs status, records sales, realizes ROI, and feeds P73 recommendation outcomes.

| Phase | Role | API prefix |
|-------|------|------------|
| P78-01 | Sell queue, listing drafts, bundles | `/api/v1/sell-queue`, `/api/v1/listing-drafts` |
| P78-02 | Listings, publish/sync, sales, analytics, certification | `/api/v1/listings`, `/api/v1/sales`, `/api/v1/selling-*` |

Web routes: `/sell-queue`, `/listing-drafts`, `/bundle-opportunities`, `/listings`, `/selling-analytics`.

Core services:

- `p78_sell_queue_service.py`, `p78_listing_draft_service.py`, `p78_bundle_service.py` (P78-01)
- `p78_listing_lifecycle_service.py` — publish, reservations, sync, sold processing
- `p78_selling_analytics_service.py` — aggregates and dashboard sections
- `selling_certification.py` — end-to-end production gate

Persistence: `p78_listing_draft`, `p78_listing`, `p78_inventory_reservation`, `p78_sale_record`, `p78_selling_analytics_snapshot`.

## Listing lifecycle

ComicOS owns lifecycle state independent of marketplace:

```text
CANDIDATE → DRAFT → READY → LISTED → SOLD → SHIPPED → COMPLETED
```

Publication flow:

```text
Draft (P78ListingDraft) → POST /listings/{draft_id}/publish → LISTED + EBAY sim export
```

Sync states on the listing row: `ACTIVE`, `SOLD`, `ENDED`, `CANCELLED`. Initial eBay integration is simulated (`SIM-EBAY-{id}`) with an export payload ready for a future live API adapter.

## Inventory reservation model

When a draft is published, `suggested_sell_quantity` copies on the same `variant_id` are reserved:

- Rows in `p78_inventory_reservation` (active until sale completes)
- Matching `inventory_copy.hold_status` set to `listed`
- Available pool excludes active reservations and copies already `listed` / `sold`

On sale (sync or manual processing path), reserved copies move to `sold`, reservations are released, and quantities drop from active sellable inventory.

## ROI realization

Per sale:

```text
profit = sale_price - fees (12% sim) - shipping ($5 default) - cost_basis (sum acquisition_cost of reserved copies)
roi_pct = profit / cost_basis × 100
```

Each sale inserts a `P73RecommendationOutcome` with `recommendation_type=SELL` for recommendation feedback (accuracy, profitability, time-to-sell inputs for analytics).

## Analytics

`GET /api/v1/selling-analytics` persists snapshots with revenue, profit, ROI, listings created/sold, sell conversion rate, average days to sell, and optional sell-recommendation accuracy.

`GET /api/v1/selling-dashboard` powers `/listings`: active, sold, draft sections plus recent completed sales.

## Certification

Service: `apps/api/app/services/selling_certification.py`  
Endpoint: `GET /api/v1/selling-certification`

Validates sell queue build, draft generation, eBay publish simulation, inventory reservation, listing sync, sales/ROI, and analytics/dashboard.

### Production readiness checklist

| Area | Status |
|------|--------|
| Sell Queue | PASS |
| Drafts | PASS |
| Marketplace Publishing | PASS |
| Inventory Reservation | PASS |
| Sales Tracking | PASS |
| ROI Tracking | PASS |
| Analytics | PASS |

## Test coverage

- `apps/api/tests/test_p78_sell_workflow.py` — P78-01 queue, drafts, bundles
- `apps/api/tests/test_sell_queue.py`, `test_listing_generation.py` — spec aliases
- `apps/api/tests/test_marketplace_sync.py` — publish, sync, reservation
- `apps/api/tests/test_sales_tracking.py` — sales APIs, ROI, P73 linkage
- `apps/api/tests/test_selling_analytics.py` — analytics and dashboard
- `apps/api/tests/test_selling_certification.py` — API and service certification

## Exit criteria

P78 is complete when ComicOS can generate listing drafts, publish listings (simulated eBay), track listing status, reserve inventory, record sales, calculate realized ROI, feed P73 outcomes, expose selling analytics, and pass `selling-certification` with all checklist areas PASS.
