# P42 Storefront Architecture

## Objective

P42-06 establishes deterministic dealer profile and organization storefront foundation for ComicOS dealer organizations: public identity rendering, visibility controls, public inventory projection, featured inventory selection, and append-only storefront lineage. It does not implement checkout, payments, marketplace sync, public accounts, or custom storefront builders.

## Core Model

- `dealer_profiles`: one profile per organization with globally unique `public_slug`, branding metadata, and lifecycle `profile_status`.
- `dealer_storefront_settings`: visibility mode, public inventory toggle, featured inventory cap/sort mode, and manual featured ID list.
- `dealer_storefront_events`: append-only lineage for profile/settings changes and unauthorized access attempts.

## Storefront Visibility Rules

Visibility modes:

- `PUBLIC`: slug-resolvable storefront; public inventory allowed when enabled.
- `UNLISTED`: direct slug access only (still requires public inventory enabled for inventory endpoints).
- `PRIVATE`: all public storefront endpoints fail closed with `404`.

Public access requires:

- active profile (`profile_status=ACTIVE`)
- visibility not `PRIVATE`
- `public_inventory_enabled=true` for inventory/featured endpoints

Inventory scope is limited to copies owned by active organization members. Operational workflow metadata (assignments, reviews, acquisition costs, etc.) is excluded from public projection.

## Public Inventory Projection

Public items expose only:

- `inventory_copy_id`
- title / publisher / issue metadata
- `grade_status`
- optional `current_fmv` and `release_year`

Deterministic ordering for list pagination uses ascending inventory id within the visible set.

## Featured Inventory System

Supported sort modes:

- `newest`
- `recently_updated`
- `highest_value`
- `manually_selected`

Featured output is capped by `featured_inventory_limit` (1–100) and always intersected with the public-visible inventory set. Manual mode preserves caller-provided ID order filtered to visible IDs.

## Storefront Lineage

Append-only events:

- `storefront_created`
- `storefront_updated`
- `storefront_visibility_changed`
- `featured_inventory_updated`
- `storefront_disabled`
- `unauthorized_storefront_access_attempt`

Payloads use sorted-key JSON serialization for replay-safe comparisons.

## API Surface

Public (no auth):

- `GET /api/v1/storefronts/{public_slug}`
- `GET /api/v1/storefronts/{public_slug}/inventory`
- `GET /api/v1/storefronts/{public_slug}/featured`

Organization management (`organization:update`):

- `POST /api/v1/organizations/{organization_id}/storefront/profile`
- `POST /api/v1/organizations/{organization_id}/storefront/settings`

## Storefront Invariants

- Slugs are normalized deterministically (`normalize_storefront_slug`).
- Hidden/private storefronts never leak inventory through public routes.
- Storefront events and review decisions are never mutated.
- One profile row and one settings row per organization.

## Future Marketplace Expansion

- Checkout and payment flows can attach to public inventory IDs without changing projection tables.
- Marketplace sync can consume storefront visibility + featured modes as publication gates.
- SEO and custom themes can layer on top of the stable public slug + profile contract.
