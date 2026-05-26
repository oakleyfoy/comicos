# Portfolio registry & exposure engine (P38-01)

## Philosophy

ComicOS **portfolio intelligence** is a deterministic **truth layer**:

- Observational grouping (`Portfolio`, `PortfolioItem`).
- Explainable concentration via **exposure snapshots** (`PortfolioExposureSnapshot`) plus append-only **evidence** (`PortfolioExposureEvidence`).
- Descriptive **allocation posture** (`PortfolioAllocationSnapshot`) from inventory FMV/cost, sales ledger lines, liquidity snapshots, grading candidates, listings, duplicates, and convention assignments.

Non-goals (explicitly **not implemented**):

- Sell/hold recommendations, acquisition advice, predictive strategy, automated rebalancing, automated FMV changes, automated inventory mutation, destructive portfolio history.

Append-safe behavior:

- Items **soft-remove** with `removed_at`; portfolios **archive** (`ARCHIVED`); lifecycle events append (`PortfolioLifecycleEvent`).
- Engines **never** mutate `InventoryCopy`, listings, FMV, or orders.

---

## Models

| Model | Purpose |
| --- | --- |
| `Portfolio` | Owner-scoped grouping with `portfolio_type`, `status`, optional `replay_key`. |
| `PortfolioItem` | Membership + `allocation_role` (+ optional allocated value/source). |
| `PortfolioExposureSnapshot` | Deterministic rollup per `(exposure_type, exposure_key)` batch. |
| `PortfolioExposureEvidence` | INVENTORY / FMV / SALES_LEDGER evidence rows tying back to a snapshot. |
| `PortfolioAllocationSnapshot` | Whole-scope descriptive posture counts + FMV/cost/sales totals checksum. |
| `PortfolioLifecycleEvent` | Audit spine (create/update/items/archived/snapshot). |

**Scope keys**

- `ALL_INVENTORY` — full owner inventory universe.
- `PORTFOLIO_{id}` — items with active `PortfolioItem` rows in that portfolio only.

**Dimensional coverage**

- Reliable today: `publisher`, `title` (slug of `"{series}::{issue_number}"`), `grade_status`, `liquidity_status`, `value_band`, `acquisition_source` (slug of `"{order.source_type}:{order.retailer}"`), `era` (from `InventoryCopy.release_year`, else issue dates when present).
- **Best-effort / placeholder**: `character`, `creator` — always keyed as `unknown` until canonical attribution exists in ComicOS inventory graph.

Unique constraints:

- `Portfolio`: `(owner_user_id, replay_key)` when replayed.
- `PortfolioExposureSnapshot`: `(owner_user_id, generation_scope_key, snapshot_date, replay_key, exposure_type, exposure_key)` — guarantees idempotent replay per dimension.
- `PortfolioAllocationSnapshot`: `(owner_user_id, generation_scope_key, snapshot_date, replay_key)` — one allocation row per generation scope.

Batch identity:

- Exposure rows emitted together share **`generation_batch_checksum`** (deterministic SHA-256 of ordered per-row fingerprints).

---

## Portfolio item rules

- One inventory row may appear in multiple portfolios.
- **At most one** *active* `PortfolioItem` per `(portfolio_id, inventory_item_id)` — enforced in service logic (`409` on duplicate adds).
- Soft remove only (`removed_at` timestamp).

---

## Exposure engine

Deterministic grouping across nine exposure families (see dimensional coverage).

**Exposure status thresholds** — evaluated on **portfolio value % when total FMV > 0**, otherwise **inventory count %**:

| Bucket | Threshold (inclusive ceiling for lower bands) |
| --- | ---: |
| BALANCED | &lt; 15% |
| WATCH | 15% – &lt; 25% |
| CONCENTRATED | 25% – &lt; 40% |
| OVEREXPOSED | ≥ 40% |
| INSUFFICIENT_DATA | missing basis |

Percentages persisted with high precision (`NUMERIC`); UI generally presents rounded values.

Liquidity rollup:

- Latest `InventoryLiquiditySnapshot` per inventory item wins (ordering: `snapshot_date DESC`, `id DESC`).
- Exposure bucket uses liquidity status verbatim (`HIGH`, `MODERATE`, `LOW`, `ILLIQUID`, `INSUFFICIENT_DATA`, `unknown` when absent).

Evidence:

- Every exposure row emits at minimum `INVENTORY` (sorted id list JSON) plus `FMV` scope rollups (per bucket localized FMV totals), and optionally `SALES_LEDGER` when realized subtotals participate.

Replay:

- Matching `(owner_user_id, generation_scope_key, snapshot_date, replay_key)` returns the prior batch without mutation.

---

## Allocation engine

Counts + optional monetary totals for the active inventory universe in scope:

- **Graded vs raw** — `grade_status != "raw"` vs `== "raw"`.
- **Listed** — any non-archived `Listing` in `READY` or `ACTIVE`.
- **Sold** — listing `SOLD` **or** `SaleRecordLineItem` with parent `SaleRecord.status == RECORDED`.
- **Liquidity splits** — `HIGH`/`MODERATE` vs everything else/absent (**unknown/absent counted as low posture** deliberately conservative).
- **Grading candidate** — `GradingCandidate.status ∈ {CANDIDATE, REVIEWING, READY_FOR_SUBMISSION, SUBMITTED}`.
- **Sale candidate** — `InventoryCopy.hold_status == "sell"`.
- **Duplicate posture** — active `PortfolioItem` rows with `allocation_role == duplicate` honoring scope (portfolio filter vs owner-wide duplicates for `ALL_INVENTORY`).
- **Convention assigned** — `ConventionInventoryAssignment` still active (`removed_at IS NULL`).

Checksum:

- SHA-256 over sorted JSON-safe payload keyed by enumerated fields (`generation_scope_key`, counts, totals, structural integers).

Replay identical to exposures for allocation rows (`replay_key` + scope + snapshot date).

---

## Checksum behavior

Row-level checksums hash canonical JSON (decimals coerced to quantised strings).

Batch checksum for exposures hashes sorted list `{row_checksum}` fragments to avoid nondeterministic ordering issues.

Changing any upstream deterministic input (inventory ordering, attribution slugs, sale inclusion rules) intentionally produces new checksum values — signalling drift for ops review rather than silently mutating history.

---

## APIs

Owner (authenticated):

- `/portfolios` CRUD + `/portfolios/{id}/archive`
- `/portfolios/{id}/items` list/add + `/remove`
- `/portfolio-intelligence/summary` dashboard rollup
- `/portfolio-exposures` (+ `/generate`) + `/portfolio-exposure-evidence`
- `/portfolio-allocations` (+ `/generate`)

Ops (read-only + `ensure_ops_admin_access`):

- `/ops/portfolios`, `/ops/portfolios/{id}`
- `/ops/portfolio-items`
- `/ops/portfolio-exposures`, `/ops/portfolio-exposure-evidence`, `/ops/portfolio-allocations`

All ops list routes accept optional `owner_user_id` filtering.

---

## UI surfaces

- **Dashboard** — lightweight cards + refresh action (calls generate endpoints with ephemeral replay keys, then reloads summary).
- **Operations** — tabular telescope with evidence counts and checksum abbreviations.
- **Inventory detail** — membership chips + optional publisher exposure teaser when latest `ALL_INVENTORY` batch exists.

---

## Deferred / follow-ups

See `docs/TECH_DEBT.md` for portfolio-specific backlog (duplicate optimization, recommendation engines, tax awareness, etc.).
