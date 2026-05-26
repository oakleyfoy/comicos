# Portfolio liquidity allocation engine (P38-03)

## Philosophy

ComicOS treats **portfolio liquidity** as a deterministic **capital allocation intelligence layer**, not trading advice:

- Roll up **item-level liquidity engine** posture plus **FMV**, **sales ledger**, **listing registry**, **portfolio allocation checksums**, and **convention activity** into one explainable snapshot per generation scope and date.
- Surfaces **liquidity-weighted value**, **liquid vs illiquid FMV**, **efficiency / drag / concentration scores**, **dead capital estimate**, and a **balance status** — all from fixed formulas and thresholds.
- **Append-only history** and **evidence** rows make the rollup auditable; **checksums** stabilize replay.

### Non-goals (explicitly out of scope)

- Sell/hold recommendations, autonomous liquidation, or portfolio auto-rebalancing.
- Predictive market timing, ML allocation, or probabilistic liquidity forecasting.
- Mutating `InventoryCopy`, FMV fields, listings, portfolios, or sales ledgers from this engine.
- Tax-aware optimization or treasury automation.

---

## Models

| Model | Role |
| --- | --- |
| `PortfolioLiquiditySnapshot` | One deterministic rollup per `(owner_user_id, generation_scope_key, snapshot_date, replay_key)` with money + score fields and `checksum`. |
| `PortfolioLiquidityBucket` | Four rows per snapshot: `HIGH`, `MEDIUM`, `LOW`, `ILLIQUID` with counts, FMV, weighted liquidity value, `% of portfolio`. |
| `PortfolioLiquidityEvidence` | FMV, liquidity engine, sales, listings, convention, portfolio registry evidence JSON (plus optional `source_id` / `source_table`). |
| `PortfolioLiquidityHistory` | Append row each time a **new** checksum is committed for a generation tuple (replay with identical inputs does not duplicate history). |

**Scope keys**

- `ALL_INVENTORY` — full owner inventory.
- `PORTFOLIO_{id}` — inventory rows with active `PortfolioItem` membership in that portfolio.

Stable ordering for checksums and persistence:

- Inventory iteration: ascending `InventoryCopy.id`.
- Bucket rows: written in fixed order `HIGH`, `MEDIUM`, `LOW`, `ILLIQUID`; list APIs order buckets by `liquidity_bucket` ascending.

---

## Liquidity bucket mapping (engine → portfolio)

Latest `InventoryLiquiditySnapshot` per item (by `snapshot_date` desc, `id` desc) supplies `liquidity_status`:

| Engine `liquidity_status` | Portfolio bucket | Liquidity weight |
| --- | --- | ---: |
| `HIGH` | HIGH | 1.00 |
| `MODERATE` | MEDIUM | 0.70 |
| `LOW` | LOW | 0.40 |
| `ILLIQUID` | ILLIQUID | 0.10 |

**Missing or unknown engine snapshot**

- Treated as **MEDIUM** bucket with weight **0.55** (explicit neutral fallback).

**Liquid vs illiquid FMV on snapshot**

- `liquid_portfolio_value` — FMV tallied in **HIGH** only (highly liquid inventory FMV).
- `illiquid_portfolio_value` — FMV tallied in **ILLIQUID** only.

---

## Scores (0–100, deterministic, no hidden blending)

All scores are `Decimal`, quantized to `0.01`, clamped to `[0, 100]`. If total scope FMV is zero, money-ratio scores are omitted (`null`).

### `liquidity_efficiency_score`

\[
\text{efficiency} = 100 \times \frac{\sum_i (\text{fmv}_i \times \text{weight}_i)}{\sum_i \text{fmv}_i}
\]

where `weight_i` is the portfolio bucket weight for that item (see table above). Null FMV contributes `0` to numerator and denominator.

### `liquidity_drag_score`

\[
\text{drag} = \Big(\frac{\text{illiq\_fmv}}{\text{total\_fmv}} \times 100 \times 1.85\Big)
+ \Big(\frac{\text{low\_fmv}}{\text{total\_fmv}} \times 100 \times 0.72\Big)
+ (\overline{\text{stale\_listing\_rate\_pct}} \times 0.027)
\]

- `illiq_fmv` / `low_fmv` — FMV sums in **ILLIQUID** and **LOW** buckets.
- `average_stale_listing_rate_pct` — mean of `stale_listing_rate_pct` over items that have a liquidity engine row (0 if none).

### `concentration_risk_score`

Let \(p_k\) be the share of total FMV in bucket \(k \in \{HIGH, MEDIUM, LOW, ILLIQUID\}\). Herfindahl \(H = \sum p_k^2\).

\[
\text{concentration} = \frac{H - 0.25}{0.75} \times 60 + \frac{\text{illiq\_fmv}}{\text{total\_fmv}} \times 40
\]

(clamped 0–100).

---

## Dead capital estimate (observational)

Base (FMV sums):

\[
\text{dead\_base} = 0.45 \times \text{low\_fmv} + 0.90 \times \text{illiq\_fmv}
\]

Additive **stale listing floor** (when average engine stale rate ≥ **70%** and total FMV &gt; 0):

\[
\text{stale\_floor} = 0.04 \times \text{total\_fmv}
\]

**Weak sales** floor (when average sell-through &lt; **18%**, at least **3** engine-backed items, total FMV &gt; 0):

\[
\text{weak\_sales} = 0.025 \times \text{total\_fmv}
\]

\[
\text{dead\_capital} = \text{round\_money}(\text{dead\_base} + \text{stale\_floor} + \text{weak\_sales})
\]

(persisted only if &gt; 0). This does **not** trigger any sale or listing change.

---

## Liquidity balance status

Let `n_items` = inventories in scope, `n_with_snap` = items with a liquidity engine row, `coverage_pct = 100 * n_with_snap / max(n_items, 1)`.

**INSUFFICIENT_DATA** if `n_items <= 0` **or** `coverage_pct < 25` (COV_INSUFFICIENT × 100).

Otherwise, when total FMV &gt; 0:

- `illiq_share = illiq_fmv / total_fmv`
- `low_share = low_fmv / total_fmv`
- `combo = illiq_share + low_share`
- `dead_share = dead_capital / total_fmv` (when denominator &gt; 0)

When total FMV is zero, the same shares use **item counts** in LOW and ILLIQUID buckets over `n_items`.

| Status | Rule |
| --- | --- |
| **CRITICAL** | `illiq_share ≥ 0.42` **or** `dead_share ≥ 0.38` (when FMV basis exists) |
| **IMBALANCED** | else `combo ≥ 0.52` |
| **WATCH** | else `combo ≥ 0.28` |
| **HEALTHY** | else |

Constants: `RULE_CRITICAL_ILLIQ = 0.42`, `RULE_CRITICAL_DEAD_SHARE = 0.38`, `RULE_IMBALANCED_COMBO = 0.52`, `RULE_WATCH_COMBO = 0.28`, `COV_INSUFFICIENT = 0.25`.

---

## Replay safety & checksum

- **Idempotency key**: `(owner_user_id, generation_scope_key, snapshot_date, replay_key)`.
- **Checksum**: SHA-256 of a canonical JSON payload (`algorithm: portfolio_liquidity_p38_03_v1`) including ordered per-item fingerprints, coverage, totals, activity block, explicit formula strings, and threshold constants — keys sorted, decimals stringified consistently.
- If an existing row matches the checksum → **replay** (HTTP 200 on generate); buckets re-read; **no** new history row.
- If inputs change for the same tuple → previous snapshot’s buckets and evidence **delete-replace**; **new** history row with the new checksum.

---

## APIs

### Owner (authenticated owner)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/portfolio-liquidity` | Filters: `portfolio_id`, `liquidity_balance_status`, date range, `latest_only`. |
| GET | `/portfolio-liquidity/{id}` | Snapshot + buckets. |
| GET | `/portfolio-liquidity-evidence` | Optional `portfolio_liquidity_snapshot_id`, `evidence_type`. |
| GET | `/portfolio-liquidity-history` | Append-only history for owner. |
| POST | `/portfolio-liquidity/generate` | Body: optional `portfolio_id`, `replay_key`, `snapshot_date`. `201` new, `200` replay. |

### Ops (ops admin; read-only)

Mirrors under `/ops/portfolio-liquidity*`, `include_in_schema=False`. All list endpoints accept **`owner_user_id`** to narrow cross-owner inspection.

---

## Inventory detail teaser

`GET /inventory/{id}` includes optional `portfolio_liquidity`:

- Item’s mapped **portfolio bucket** and engine status.
- Latest **ALL_INVENTORY** snapshot id (if any) with portfolio-level efficiency, dead capital estimate, balance status.
- Short **dead capital teaser** when bucket is LOW or ILLIQUID (observational copy only).

---

## Implementation reference

- Service: `apps/api/app/services/portfolio_liquidity.py`
- Models: `apps/api/app/models/portfolio_liquidity.py`
- Tests: `apps/api/tests/test_portfolio_liquidity.py`
