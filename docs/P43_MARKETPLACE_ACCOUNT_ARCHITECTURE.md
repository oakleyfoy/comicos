# P43 Marketplace Account Architecture

## Objective

P43-01 establishes the organization-owned marketplace account foundation for ComicOS: marketplace identity mapping, credential references, connection lifecycle state, authorization enforcement, and immutable connection lineage. It does not sync inventory, create listings, ingest orders, process webhooks, or call live marketplace APIs.

## Core Ownership Model

- `marketplace_accounts`: one stable row per globally unique marketplace identity (`marketplace_type` + `marketplace_account_id`), bound to exactly one organization.
- `marketplace_credentials`: credential references only; no raw OAuth tokens, API keys, or secrets are stored in ComicOS tables.
- `marketplace_connection_events`: append-only lifecycle and unauthorized-access history ordered by `created_at`, then `id`.

This keeps foreign keys stable across reconnect, verification, and disconnect transitions while preserving a replay-safe lineage trail.

## Marketplace Registry

Supported registry entries are centralized in `app/services/marketplace_registry.py`:

- `ebay`
- `whatnot`
- `shopify`

Each definition includes:

- `marketplace_key`
- `display_name`
- `status`
- `capability_flags`

The registry is deterministic, serialized in a fixed order, and reserved for future marketplace-specific sync contracts without introducing live integration logic in this phase.

## Lifecycle States

Account status values:

- `connected`
- `disconnected`
- `suspended`

Verification status values:

- `pending`
- `verified`
- `failed`

Transitions are backend-authoritative and replay-safe:

- connect creates or reactivates a stable account row
- verify manually marks the account `verified` or `failed`
- disconnect marks the account `disconnected` and records immutable lineage

Repeated identical connect or verify requests are idempotent and do not create duplicate lineage for the same already-realized state.

## Credential Handling

Credential rows store only:

- `credential_type`
- `credential_reference`
- `credential_status`
- rotation timestamps

References are intended to point at an external vault, secret manager, or future secure connector. When a new reference replaces an active one, the prior active reference is marked rotated or revoked without deleting historical rows.

## Authorization Model

Marketplace access reuses organization membership and permission context:

- visibility requires `organization:view`
- management requires `organization:update`
- evaluation is deny-by-default and fail-closed
- cross-organization account access is rejected

Unauthorized requests append `unauthorized_marketplace_access_attempt` events so connection lineage captures both legitimate lifecycle changes and blocked access attempts.

## Immutable Lineage Events

Current lifecycle events:

- `marketplace_connected`
- `marketplace_disconnected`
- `marketplace_verified`
- `marketplace_verification_failed`
- `unauthorized_marketplace_access_attempt`

Payloads are serialized with sorted keys to keep event comparisons deterministic for tests, replay, and future audit tooling.

## API Surface

Organization-scoped v1 endpoints:

- `GET /api/v1/organizations/{organization_id}/marketplaces`
- `GET /api/v1/organizations/{organization_id}/marketplaces/{account_id}`
- `POST /api/v1/organizations/{organization_id}/marketplaces/connect`
- `POST /api/v1/organizations/{organization_id}/marketplaces/disconnect`
- `POST /api/v1/organizations/{organization_id}/marketplaces/verify`

Responses use the existing v1 envelope format and deterministic list ordering.

## Future Dependencies

This foundation is intentionally upstream of later marketplace phases:

- inventory sync can depend on stable organization-owned marketplace identities
- listing publication can depend on verified connection state
- order ingestion can depend on credential references and account ownership
- webhook ingestion can bind to immutable marketplace lineage and organization isolation

Those workflows should layer on top of these contracts rather than redefining marketplace ownership or credential storage.
