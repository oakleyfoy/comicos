# Convention / Show Operations Architecture

## Purpose

`P36-05` teaches ComicOS how inventory moves through conventions, live shows, wall books, showcases, bins, and temporary selling windows.

This layer is operational and descriptive only. It tracks placements, movement history, temporary pricing, and sale sessions without payment processing, auto-selling, hidden inventory mutation, or inventory decrementing.

## Models

- `ConventionEvent` stores the event header and lifecycle state.
- `ConventionInventoryAssignment` stores append-safe event inventory placements.
- `ConventionInventoryMovement` stores append-only physical movement history.
- `ConventionPriceSnapshot` stores event-scoped temporary pricing overrides.
- `ConventionSaleSession` stores the active selling window for an event.

The canonical state for each area is always the latest row by stable ordering (`created_at`, then `id`).

## Operational Workflows

Convention events start in `PLANNED`, may be activated for a live show, and can later be completed or cancelled. Assignment and movement rows are append-only so the full physical history stays visible after the event closes.

The system supports:

- event-specific inventory subsets
- wall-book and showcase placement
- temporary pricing separate from default inventory pricing
- lightweight sale-session tracking for active selling windows

## Assignment Rules

Assignments are append-safe and event-scoped.

- Inventory can appear in multiple events historically.
- Only one active assignment may exist for an inventory item inside a single event.
- Removing an item from a display location creates a new movement row instead of deleting history.
- Deterministic ordering uses `priority_rank`, then `assigned_at`, then `id`.

## Pricing Override Rules

Convention prices never overwrite canonical inventory pricing.

- Each price snapshot is event-scoped.
- Latest-price resolution is deterministic and based on `created_at`, then `id`.
- The service can fall back to the underlying inventory value when no event override exists.
- Pricing snapshots are append-only and replay-safe when a `replay_key` is supplied.

## Movement Tracking

Movement rows capture physical changes such as:

- wall -> showcase
- showcase -> reserve
- reserve -> sold
- reserve -> returned

Movement history is append-only. The code never silently mutates the prior row to simulate a move.

## Session Lifecycle

Sale sessions identify the active selling window for a convention event.

- `POST /convention-sale-sessions` opens a session.
- `POST /convention-sale-sessions/{id}/close` closes it explicitly.

No payment processing or automatic sale finalization happens in this phase.

## Owner vs Ops API Split

Owner routes are scoped to the authenticated owner:

- `GET /convention-events`
- `POST /convention-events`
- `GET /convention-events/{id}`
- `PATCH /convention-events/{id}`
- `POST /convention-events/{id}/activate`
- `POST /convention-events/{id}/complete`
- `GET /convention-assignments`
- `POST /convention-assignments`
- `GET /convention-movements`
- `POST /convention-movements`
- `GET /convention-price-snapshots`
- `POST /convention-price-snapshots`
- `GET /convention-sale-sessions`
- `POST /convention-sale-sessions`
- `POST /convention-sale-sessions/{id}/close`

Ops routes are read-only mirrors:

- `GET /ops/convention-events`
- `GET /ops/convention-assignments`
- `GET /ops/convention-movements`
- `GET /ops/convention-price-snapshots`
- `GET /ops/convention-sale-sessions`
- `GET /ops/convention/dashboard-summary`

## Non-Goals

- Payment processing
- POS checkout
- Inventory decrementing
- Auto-selling inventory
- Offline sync
- Barcode scanning
- Staffing workflows
- Convention analytics beyond the current operational ledger
