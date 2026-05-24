# Inventory intelligence architecture (P33)

P33 closes the **read-only Inventory Intelligence layer**. This document summarizes boundaries, deterministic behavior, and how reporting surfaces relate to dashboards.

## Principles

1. **Deterministic only.** Rollups, exports, timelines, risks, duplicate ownership clustering, order/arrival labels, action-center items, and run gaps are reproducible from persisted state and documented sort keys (no sampled randomness, no “confidence scores” repurposed as value or pricing).
2. **No intelligence mutation.** Listing or exporting intelligence projections must never write canonical metadata, cover relationships, inventory rows, OCR outcomes, conflicts, duplicates, or financial fields as a side effect of the read path.
3. **No pricing or speculation.** FMV/gain dashboards are deliberately separated from deterministic intelligence UX. Portfolio performance uses explicit FMV assignments; intelligence endpoints and exports omit `current_fmv` / `gain_loss` wherever schema allows.
4. **No canonical mutation.** Suggestions and conflicts remain review-first surfaces; reconciliation behavior is summarized in [`RECONCILIATION_ARCHITECTURE.md`](./RECONCILIATION_ARCHITECTURE.md).

## Ownership and preorder normalization

Ownership states used in projections are derived deterministically from order status, release status, and receipt timestamps (see `normalize_ownership_state`):

- **`in_hand`** — received or fulfilled.
- **`preorder`** — not released yet or explicitly preordered prior to fulfillment.
- **`ordered_not_received`** — ordered/shipped pending receipt without conflicting signals.
- **`cancelled`** — cancelled orders.
- **`unknown_state`** — rare bucket when inputs disagree or are incomplete (surfaced explicitly instead of silently coercing).

Preorder vs release calendar cues feed **risk lanes** (`preorder_missing_release_date`) and **order/arrival classifications** independently of valuation.

## Surfaces covered by P33

| Area | Role |
| --- | --- |
| Inventory summaries & health | Owner/Ops rollup counts (scans, OCR, unresolved conflicts/suggestions/clusters). |
| Duplicate ownership | Groups overlap within an owner footprint; classifications are heuristic labels backed by deterministic keys. |
| Run detection | Series progress and missing-issue rows from canonical spine + inventory ownership snapshots. |
| Collection analytics | Publisher and quality fractions; aligns with deterministic intelligence signals only. |
| Inventory risks | Priority-sorted actionable cards from conflicts, OCR, scans, preorder gaps, duplication, run gaps. |
| Workflow action center | Mirrors risk priority scale; merges risk-derived items plus duplicate/scan/variant/order-arrival derived keys. |
| Order / arrival | Labels from dates and statuses — logistics overlay, never FMV. |
| Timeline / history | Persisted ledger events sorted by `(occurred_at, event_type, stable_id)`. |
| Reports / exports | CSV with stable column order & `\n` line endings; JSON with recursively sorted keys; ASCII-safe primary filenames plus RFC 5987 `filename*=UTF-8''…` duplicates. |

## Reporting & export guarantees

- **Stable columns** — tuples in `reports_export.py` (`INVENTORY_OWNER_CSV_COLUMNS`, action center, timeline, …) define export order exactly.
- **Stable rows** — inventory exports sort by deterministic inventory list ordering (publisher/title/issue as implemented in inventory listing hooks); timelines sort as above.
- **Filter echo** — JSON inventory documents encode `filters` with `sort_keys=True` after JSON round-trip so nested keys serialize in lexical order alongside top-level sorted keys from `dumps_report_json`.
- **Scope** — `/reports/*` is owner-bound; `/ops/reports/*` requires ops admin email and attaches `owner_user_id` columns where applicable.
- **UTF-8** — payloads are emitted as UTF-8 bytes; filename stems sanitize control characters and non-ASCII to safe ASCII fragments before attachment headers are emitted.

## Performance hygiene (within P33 constraints)

Heavy analytics (`analyze_collection_summary`) already computes intelligence rollups once per call; downstream collection summaries in exports reuse that tuple instead of issuing a redundant `compute_inventory_intelligence(include_signals=False)` pass. Avoid introducing caches that reorder or hide rows, background mutation, or weakened filters.

## Local testing expectations

Automated suites use `fakeredis` for RQ/Redis stubs — production Redis wiring is orthogonal to intelligence deterministic outputs.
