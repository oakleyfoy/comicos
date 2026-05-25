# Listing registry architecture (P36-01)

## Purpose

The listing registry is the **canonical truth layer** for ComicOS listings: what is offered, at what headline price, under which deterministic lifecycle flag, tied to inventory and optional canonical issue metadata.

It deliberately excludes marketplace automation (no posting feeds, repricing bots, liquidity heuristics, or inventory decrementing from reads).

## Persistence

| Table | Role |
| ----- | ---- |
| `listing` | Current row keyed by lifecycle `status`; carries headline price and copy linkage via `inventory_copy_id`. Unique `(owner_user_id, replay_key)` supports idempotent creates. |
| `listing_lifecycle_event` | Append-only audit spine: `prior_status`, `new_status`, `event_type`, `metadata_json`. Optional `(listing_id, replay_key)` uniqueness suppresses duplicates on retries. |
| `listing_price_history` | Append-only snapshots of headline price moves (never overwritten). Optional replay keys align with PATCH retries. |
| `listing_image` | Gallery linkage to `cover_image` or `scan_session_item` with deterministic read order `(display_order ASC, id ASC)`. |
| `listing_inventory_link` | Future-safe allocation surface (`quantity_allocated`); current flows establish one link per listing at creation. |

## Lifecycle (explicit, explainable)

Allowed transitions:

- `DRAFT` → `READY` (PATCH)
- `READY` → `ACTIVE` (**POST** `/listings/{id}/activate`; PATCH to `ACTIVE` is rejected with 400)
- `ACTIVE` → `SOLD` or `CANCELLED` (PATCH)
- `CANCELLED` → `ARCHIVED` (**POST** `/listings/{id}/archive`; cancel via **POST** `/listings/{id}/cancel`)

Terminal states forbid silent recovery paths (e.g. `SOLD` → `ACTIVE`); no implicit “un-sold” semantics.

Lifecycle metadata persisted in events always uses JSON-safe scalars for money (decimals serialized as strings in structured snapshots).

## API surface

- **Owner** — scoped by authenticated user (`GET /listings`, `POST /listings` returns **201** on first create and **200** when repeating the same `(owner,replay_key)`), `PATCH` for constrained updates, lifecycle POST helpers.
- **Ops** — `GET /ops/listings*` and audit feeds guarded by configured `OPS_ADMIN_EMAILS`; when unset, non-production environments fall back to the historical open-ops semantics used elsewhere in ComicOS (`is_ops_admin_user`).

## Invariants checklist

Deterministic sorting on list reads, append-only audits, replay-key idempotency for hot paths (create, price PATCH, scripted lifecycle events where keys are supplied), and read routes that skip side-effecting metadata bookkeeping.
