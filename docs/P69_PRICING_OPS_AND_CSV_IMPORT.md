# P69 — Pricing Ops + CSV Sold Comps Import

P69 makes P68 FMV usable before live eBay by importing sold comps from CSV and exposing provider readiness.

## CSV import

- **Endpoint:** `POST /api/v1/market-pricing/import/csv` (multipart `file`)
- **Provider:** `CSV_IMPORT` observations in `p68_market_price_observation`
- **Flag:** `P69_CSV_IMPORT_ENABLED` (default `true`)

### Required columns

`title`, `publisher`, `issue_number`, `sold_price`, `sale_date`

### Optional columns

`variant_label`, `printing_number`, `grade`, `raw_or_graded`, `shipping_price`, `source_url`, `provider` (stored as `source_provider_label` in metadata only)

Invalid rows are skipped; the response includes `skipped_rows` with reasons.

Identity warnings (facsimile in title, printing mismatch) and optional inventory match scores are stored in `metadata_json`. Matching uses the same P68/P66 identity matcher as snapshot builds.

## Provider health

- **Endpoint:** `GET /api/v1/market-pricing/providers/health`
- **eBay:** `NOT_CONFIGURED` until `EBAY_API_CLIENT_ID` is set and `P68_EBAY_PROVIDER_ENABLED=true`. No secrets are persisted.
- **CSV / internal / manual:** configured and enabled per flags.

## FMV flow

1. Import CSV (and/or internal sales / manual comps)
2. `POST /api/v1/market-pricing/snapshots/build`
3. P67 reads `p68_inventory_computed_fmv` via the inventory bridge (does not overwrite `inventory_copy.current_fmv` unless `P68_AUTO_OVERWRITE_INVENTORY_FMV=true`)

## Certification

`GET /api/v1/market-pricing/certification/p69` imports the fixture CSV, builds snapshots, and verifies auto-overwrite is off.

## UI

Portfolio Analytics includes a CSV upload panel, provider health summary, and latest `CSV_IMPORT` comps alongside P68 FMV snapshots.
