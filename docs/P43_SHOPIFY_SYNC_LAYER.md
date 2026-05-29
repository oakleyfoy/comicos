# P43-08 Shopify / Storefront Sync Layer

This phase establishes ComicOS-side Shopify synchronization infrastructure without calling Shopify APIs or publishing anything externally.

## What It Models

- `ShopifyStorefront`: an organization-owned storefront registry row linked to a marketplace account.
- `ShopifyProductMapping`: a deterministic mapping between an inventory item, a listing draft, and a storefront product identifier.
- `ShopifySyncState`: the latest recorded sync payload for a storefront.
- `ShopifySyncEvent`: immutable lineage for storefront creation, projection generation, mapping changes, snapshots, and deny-path attempts.

## Lifecycle

1. A storefront is registered for a marketplace account.
2. Product mappings are created or updated for inventory / draft pairs.
3. A storefront projection is generated from backend-authoritative data.
4. A sync snapshot is registered with a replay-safe payload and current sync status.

## State Semantics

- `Publication Status`: `draft`, `ready`, `published_internal`, `unpublished_internal`
- `Sync Status`: `pending`, `completed`, `failed`
- `Mapping Status`: `mapped`, `unmapped`, `invalid`

## Guarantees

- Organization ownership is enforced on every route and service entry point.
- List ordering is deterministic and uses stable timestamp/id ordering.
- Sync state writes are replay-safe and do not call external Shopify APIs.
- Events are append-only and capture the important internal transitions, including unauthorized access attempts and invalid mapping detection.
- No Shopify publishing, inventory mutation, order ingestion, webhook processing, or checkout logic is introduced in this phase.

## Future Dependencies

This layer is intentionally structured so future Shopify API integrations can consume the storefront registry, mappings, and sync snapshots without changing the deterministic ComicOS-side contracts.
