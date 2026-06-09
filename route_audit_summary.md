# Route audit summary

- **Visible nav routes:** 51
- **API probes:** 63
- **Failing probes:** 0
- **Failing routes (any probe):** 0
- **Unique backend root causes:** 0

## Failure types


## Missing tables / relations

- (none in raw error text; see MISSING_MIGRATION envelopes below)

## Failing routes


## Root causes (grouped)

- No failures in this run.

## Recommended fix order (smallest backend set)

1. No backend failures in this run; re-run against production `ROUTE_AUDIT_BASE_URL` before deploy.

## Audit method

- API probes via `apps/api/scripts/production_route_audit.py` (page-load GETs from `config/route-page-primary-apis.json`).
- **JS_ERROR** not measured in this run (no Playwright/browser pass). Re-run with browser tooling for full nav + console errors.
- Live production: set `ROUTE_AUDIT_BASE_URL` + auth env vars and re-run the script.
