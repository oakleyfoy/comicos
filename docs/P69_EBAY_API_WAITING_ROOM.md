# P69 — eBay API Waiting Room

Live eBay sold listings are **not** implemented in P69.

## Current behavior

- `P68_EBAY_PROVIDER_ENABLED` defaults to **false**.
- The eBay adapter (`EbaySoldListingsProvider`) only returns deterministic **fixtures** when the flag is on.
- **No scraping** and **no storage** of eBay OAuth tokens or app secrets in the database.

## Readiness signal

`GET /api/v1/market-pricing/providers/health` reports:

| Field | Meaning |
|--------|---------|
| `configured` | `true` only when `EBAY_API_CLIENT_ID` is present in environment (read once at runtime; never written to DB) |
| `health_status` | `NOT_CONFIGURED`, `DISABLED`, or `READY` |
| `enabled` | Requires both credentials and `P68_EBAY_PROVIDER_ENABLED=true` |

## Until eBay access

Use **CSV_IMPORT**, **MANUAL**, and **INTERNAL_SALE** observations, then run snapshot build. FMV blends these sources in P68 without treating stub data as live market pricing.

## When eBay is available (future)

1. Set `EBAY_API_CLIENT_ID` (and related env vars) on the API host.
2. Enable `P68_EBAY_PROVIDER_ENABLED`.
3. Replace fixture fetch with authenticated sold-listings API calls behind the same `EbaySoldListingsProvider` interface.
