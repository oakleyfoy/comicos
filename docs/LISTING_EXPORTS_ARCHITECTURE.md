# Listing exports architecture (P36-02)

## Purpose

Listing exports turn **canonical listing rows** into **offline, channel-shaped CSV artifacts** suitable for uploading to retailer tooling. This layer is deliberately **deterministic**: same inputs plus the same template and listing snapshots should yield the same file checksum where the spec guarantees stability.

Exports are **not** marketplace posting, **not** OAuth or REST integration with channels, and **not** pricing or liquidity intelligence. ComicOS persists an **append-style ledger** (`listing_export_run` and children) so every attempt is replay-inspectable.

## Models

| Model | Role |
| --- | --- |
| `ListingExportTemplate` | Per-owner channel template (`column_map_json`, `rules_json`, `template_version`). Seeded defaults for starter channels (`name="default"`). |
| `ListingExportRun` | One synchronous export execution: status lifecycle, counters, optional `replay_key`, SHA-256 checksum of the emitted CSV payload. |
| `ListingExportRunItem` | One row per requested listing slot: `EXPORTED` / `SKIPPED` / `FAILED`, `skip_reason`, `row_number`, deterministic `row_checksum` for exported rows. `listing_id` may be null for missing/unowned placeholders. |
| `ListingExportFile` | Persisted CSV file metadata (`file_name`, `storage_path`, `checksum`, `row_count`). Stored under `LISTING_EXPORTS_STORAGE_ROOT`. |

## Supported starter channels

Default templates ship for:

- `generic_csv`
- `ebay` (starter columns plus static placeholder headers: category, format, duration, shipping/return/payment policy)
- `whatnot`
- `shopify`
- `hipcomic`, `shortboxed` — minimal seeded maps for forward compatibility without deep channel semantics.

Starter column maps converge on catalogue fields (`listing_id`, `title`, `description`, pricing, quantity, status, `source_type`, ordered image tokens, timestamps). Channels do **not** call external validation APIs in this phase.

## Deterministic rules

- **Listing order**: Requested IDs are deduplicated then sorted ascending by integer `listing_id`.
- **Image tokens**: Resolved from registry helpers, primary role preferred, sibling gallery tokens sorted lexically for deterministic `additional_images`.
- **CSV layout**: Stable header order follows the template’s `column_map_json.columns`; body rows align to sorted listing IDs; CSV text is UTF-8; file checksum covers the canonical UTF-8 byte string emitted by shared `render_csv`.
- **File naming**: `comic_os_{channel}_export_run_{run_id}_{created_date}.csv` (channel segment sanitized).

## `replay_key` behavior

Optional `replay_key` is unique per `(owner_user_id, replay_key)` when supplied. Duplicate POSTs return **HTTP 200** with the **existing completed run payload** instead of cloning work. Omitting `replay_key` intentionally creates distinct ledger rows — checksum still matches whenever listing snapshots match.

Concurrent conflicts surface as HTTP 409 with a generic collision detail.

## Eligibility rules

Export generation is **read-only** against listings. Eligible statuses: `READY`, `ACTIVE`. Others are emitted as `SKIPPED` with stable machine reasons (`SKIP_STATUS_DRAFT`, `SKIP_STATUS_SOLD`, etc.). Rows that fail owner scope checks use `SKIP_NOT_OWNED_OR_MISSING`. Listing statuses are never updated by the export runner.

## API split

### Owner-authenticated routes

- `GET /listing-export-templates` — list seeded templates for the signed-in collector.
- `POST /listing-export-runs` — body includes `listing_ids`; exactly one of `template_id` **or** `channel`; optional `replay_key`. Executes synchronously and returns populated run detail (including items/files).
- `GET /listing-export-runs`, `GET /listing-export-runs/{id}`, `GET /listing-export-runs/{id}/download` — owner-scoped list/detail/FileResponse download.

### Ops routes (read-only + cross-owner download)

Ops admins may list/filter runs, inspect cross-owner detail, enumerate file rows, and download CSV payloads via mirrored `/ops/listing-export-runs*` routes (credentials via `OPS_ADMIN_EMAILS`). Ops surfaces intentionally avoid mutating canonical listing data.

## UI notes

The dashboard summarizes recent runs, totals, checksums, and links into the ops explorer. Detailed multi-select workflows for assembling `listing_ids` are **intentionally deferred** until the SPA grows a workbook-style selection primitive; until then collectors can POST via scripted clients without losing ledger fidelity.

## Non-goals

- Live marketplace credential management or posting adapters.
- Auto pricing, recommendations, liquidation scoring, or sales accounting bridges.
- Async worker offload (exports run inline today).
- Rich binary image packaging separate from deterministic token exports.
- AI-generated listing prose.
