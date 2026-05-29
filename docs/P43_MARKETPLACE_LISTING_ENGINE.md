# P43 Marketplace Listing Engine

P43-02 establishes internal marketplace listing draft infrastructure for ComicOS dealer organizations. It projects organization-owned inventory into deterministic, public-safe marketplace payload shells without calling external marketplace APIs.

## Scope

This phase includes:

- organization-scoped listing drafts tied to marketplace accounts and inventory copies
- deterministic validation with stable error codes
- replay-safe listing lineage events
- marketplace payload projection records for `ebay`, `whatnot`, and `shopify`
- listing management APIs and frontend workspace shells

This phase does **not** publish listings, sync live inventory, ingest orders, process webhooks, or store marketplace API secrets.

## Listing draft lifecycle

Listing statuses:

- `draft` — editable internal draft
- `ready` — validated and eligible for projection generation
- `archived` — immutable terminal state (`archived_at` set)

Validation statuses:

- `pending` — required fields present but draft not marked ready
- `valid` — fail-closed checks passed while status is `ready`
- `invalid` — deterministic validation errors present

Typical flow:

1. Create draft (`marketplace_listing_draft_created`)
2. Update fields / mark ready (`marketplace_listing_draft_updated`)
3. Generate projection when `validation_status=valid` (`marketplace_listing_projection_generated`)
4. Archive when no longer needed (`marketplace_listing_draft_archived`)

Failed projection attempts emit `marketplace_listing_validation_failed` without mutating prior lineage rows.

## Inventory-to-listing projection

- `inventory_item_id` references `inventory_copy.id`
- eligibility uses existing organization inventory membership rules (`validate_org_inventory_membership`)
- projections include public inventory metadata only (title, publisher, issue, grade, release year)
- acquisition cost and internal workflow metadata are excluded from payload shells

## Marketplace payload shells

Projection service generates deterministic JSON shells:

- **eBay** — `{ marketplace, listing, inventory, schema_version }`
- **Whatnot** — `{ marketplace, show_listing, inventory, schema_version }`
- **Shopify** — `{ marketplace, product, inventory, schema_version }`

Payloads are normalized with sorted keys and stable serialization. Each new projection supersedes prior `current` rows while retaining append-only history.

## Validation system

Validation ordering is deterministic and fail-closed:

- organization ownership
- marketplace account connected and in-org
- inventory membership
- title / price / currency / quantity checks
- archived status compatibility

Stable error codes include `listing_title_required`, `listing_price_required`, `marketplace_account_disconnected`, and `inventory_out_of_scope`.

## Authorization

Listing visibility and management reuse P43-01 marketplace organization permissions:

- view — `organization:view` (manage implies view)
- manage — `organization:update`

Unauthorized attempts append `unauthorized_marketplace_listing_access_attempt` listing events.

## Replay-safe listing lineage

`marketplace_listing_events` is append-only. Supported event types:

- `marketplace_listing_draft_created`
- `marketplace_listing_draft_updated`
- `marketplace_listing_draft_archived`
- `marketplace_listing_projection_generated`
- `marketplace_listing_validation_failed`
- `unauthorized_marketplace_listing_access_attempt`

Events store deterministic JSON payloads and stable `(created_at, id)` ordering.

## Future publishing and sync dependencies

Downstream phases can depend on:

- validated `ready` drafts as publish candidates
- `marketplace_listing_projections.projection_payload_json` as outbound contract input
- append-only listing lineage for replay audits
- marketplace account foundation (`P43-01`) for credential-backed publish workers

No external API clients belong in P43-02 services or tests.

## API surface

Organization routes (v1 envelope):

- `GET /organizations/{id}/marketplace-listings`
- `GET /organizations/{id}/marketplace-listings/{listing_id}`
- `GET /organizations/{id}/marketplace-listings/{listing_id}/projections`
- `POST /organizations/{id}/marketplace-listings`
- `PATCH /organizations/{id}/marketplace-listings/{listing_id}`
- `POST /organizations/{id}/marketplace-listings/{listing_id}/projection`
- `POST /organizations/{id}/marketplace-listings/{listing_id}/archive`

Engine version key: `marketplace_listing_engine: P43-02`.
