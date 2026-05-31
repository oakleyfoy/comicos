# Marketplace Platform Runbook

Operational guide for ComicOS marketplace connectors, canonical listings, publish engine, inventory sync, and order import (P46).

## Connector lifecycle

1. **Seed** — Marketplace definitions and capabilities are seeded via `marketplace_seed.py` (read-only at runtime except enablement).
2. **Connect** — Owner links a marketplace account (`MarketplaceAccount` + encrypted credentials). Whatnot and Shopify validate tokens before activation.
3. **Enable** — Successful connect enables the marketplace definition for that deployment context.
4. **Execute** — Connector operations record append-only `MarketplaceExecution` rows (CONNECT, VALIDATE, PUBLISH, etc.).
5. **Disconnect** — Disables the account and records DISCONNECT; does not delete historical executions or orders.

### Troubleshooting connectors

| Symptom | Likely cause | Recovery |
|--------|----------------|----------|
| 422 on connect | Invalid credentials | Re-enter token; confirm stub prefix (`whatnot_valid_`, `shopify_valid_`) in non-production |
| 404 active account | No ACTIVE account for marketplace | Connect again or check disabled accounts |
| Executions FAILED | Connector or upstream validation | Review `/whatnot/executions` or `/shopify/executions`; re-validate account |

## Listing lifecycle

1. Create canonical `MarketplaceListing` (owner-scoped).
2. Enrich prices, images, mappings as needed (P46-02).
3. Move to `READY_TO_PUBLISH` before marketplace publish.
4. Publish via publish engine or integration API; mapping stores external IDs.

### Recovery

- **Publish validation failed** — Fix listing fields; check publish job validation issues; retry publish.
- **Missing mapping** — Publish again or create mapping through publish flow; do not write external IDs by hand in production.

## Publish lifecycle

1. `create_publish_job` → validate → plan → ready → connector publish → complete job.
2. Targets track per-marketplace outcomes in `MarketplacePublishTarget`.
3. Events and validation issues are append-only audit for the job.

### Recovery

- **FAILED job** — Inspect validation issues; reset listing status if needed; create a new publish job.
- **Partial targets** — Review target statuses; update or retry failed targets only through publish engine services.

## Sync lifecycle

1. Availability is derived via reservation/allocation services (no direct stock mutation from connectors).
2. Sync plans (`MarketplaceInventorySyncPlan`) describe intended quantity changes.
3. Connector `sync_inventory` applies marketplace-side quantity from planned available counts.

### Recovery

- **Negative available in validation** — Reconcile reservations and availability; never bypass allocation services.
- **FAILED sync plan** — Regenerate plan; sync per listing via integration API.

## Order lifecycle

1. Connector `import_orders` fetches external orders (stub or live).
2. Import service maps to `MarketplaceOrder` / items / events via `marketplace_orders.create_order`.
3. Duplicate protection: same `owner_id`, `marketplace_account_id`, `external_order_id`.

### Recovery

- **Duplicate skipped** — Expected on re-import; verify order in marketplace orders UI/API.
- **Missing items** — Check external payload mapping; re-import does not duplicate.

## Platform readiness (P46-08)

- **Validation** — `GET /api/v1/marketplace-dashboard/validation` (PASS / WARNING / FAIL).
- **Health** — `GET /api/v1/marketplace-dashboard/health` (on-demand, no background jobs).
- **Certification** — `platform_certified` is true when overall validation status is PASS.

## Escalation

- Framework bypass or inventory oversell risk: stop connector sync, run validation, fix reservations before re-enabling sync.
- Document incident with execution IDs and publish job UUIDs for audit.
