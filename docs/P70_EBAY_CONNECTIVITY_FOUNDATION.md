# P70-01 eBay Connectivity Foundation

This change enables eBay production OAuth connectivity and provider health only.

## What is implemented

- `EBAY_API_CLIENT_ID`
- `EBAY_API_CLIENT_SECRET`
- `EBAY_ENVIRONMENT=production`
- OAuth client-credentials token acquisition against eBay production auth
- Read-only provider health reporting at `GET /api/v1/market-pricing/providers/health`

## What is explicitly out of scope

- Sold listings ingestion
- FMV generation
- Inventory mutation or sync
- Credential storage in the database

## Health behavior

The eBay provider health entry is marked `AUTHENTICATED` only after the API can fetch an OAuth access token from eBay. No credentials are logged or persisted.

## Deployment notes

1. Set `EBAY_API_CLIENT_ID` and `EBAY_API_CLIENT_SECRET` in the API environment.
2. Keep `EBAY_ENVIRONMENT=production` for the live keyset.
3. Deploy the API and confirm `GET /api/v1/market-pricing/providers/health` reports `EBAY_SOLD` as `AUTHENTICATED`.
