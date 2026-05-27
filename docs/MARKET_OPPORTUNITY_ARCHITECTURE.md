# Market acquisition opportunity snapshots (P39-05)

## Aggregation philosophy

P39-05 is an **explainable rollup layer**. It consumes **immutable** artefacts from upstream engines:

| Input | Produced by |
| --- | --- |
| Persisted `market_acquisition_signal` rows (+ signal snapshot checksum) | P39-04 |
| Persisted score fields referenced by signals (`MarketAcquisitionScore`) | P39-03 |
| Normalized candidate IDs carried on score rows | P39-02 |
| Lightweight read-only portfolio context (e.g. latest liquidity snapshot id for evidence anchoring only) | P38 |

Opportunity snapshots **never** INSERT/UPDATE/DLETE into scoring, normalization, ingestion, ingestion candidates, signals, or market signal snapshots. Aggregation is deterministic, append-only outside the dedicated opportunity ledger tables (`market_acquisition_opportunity_*`).

## Signal-to-opportunity mapping

Each opportunity **item** is a 1:1 row keyed by **`market_acquisition_signal_id`** (unique per snapshot). Items store:

- The signal’s **`signal_type`** and **`signal_strength`** verbatim (no reclassification).
- The linked score’s **`final_rank_score`**, **`confidence_level`**, and **`risk_level`** as persisted (no recomputation).
- **`contribution_weight`**: deterministic micro-weight vector across the snapshot, derived from stable type/strength precedence and quantized so the vector sums exactly to **`1.000000`**.

Portfolio-level **`opportunity_classification`** (`ELITE_OPPORTUNITY` / `STRONG_OPPORTUNITY` / `MODERATE_OPPORTUNITY` / `LOW_OPPORTUNITY`) is derived only from deterministic counts/averages harvested from persisted signal + score reads.

## Portfolio impact modeling (explicitly non‑ML)

All impact columns are deterministic formulas clamped/stepped decimals:

| Field | Derived from |
| --- | --- |
| `estimated_portfolio_gap_coverage` | Count of `PORTFOLIO_GAP_FILL` × fixed uplift factor capped at **100**. |
| `estimated_liquidity_gain` | Sum of persisted `liquidity_score` on `LIQUIDITY_OPPORTUNITY` signals with fixed liquidity weights + capped. |
| `estimated_diversification_gain` | Counts (`CONCENTRATION_REDUCTION`, `PORTFOLIO_GAP_FILL`) plus aggregated persisted `concentration_reduction_score` means with fixed coefficients, capped at **100**. |
| `estimated_risk_adjustment` | Negative blend of HIGH_RISK signal counts plus mean persisted `risk_penalty_score` on those signals. |

None of these are forecasts; they normalize observed counts/scores onto an interpretability scale **only for portfolio storytelling**.

## Deterministic ordering & replay safety

- Signals are iterated in a **stable comparator**: `(signal type priority ascending, signal strength ordinal ascending, signal id ascending)`.
- Snapshot **`snapshot_checksum`** is a SHA‑256 hex digest over a canonical JSON envelope including the upstream **`market_acquisition_signal_snapshot.checksum`**, deterministic totals, canonical item tuple `(signal id, persisted signal checksum, candidate id, contribution weight string)`.

If an identical checksum already exists for the tuple `(owner_user_id, market_acquisition_signal_snapshot_id, snapshot_checksum)` the generator **replays**: no new snapshot rows/items/evidence/history are written.

Stable history rows record the subset of rollup fields required by P39‑05 QA plus `snapshot_checksum` for append auditing.

### Evidence layering

Evidence rows annotate traceability (`SIGNAL_LAYER`, `SCORING_LAYER`, `NORMALIZATION_LAYER`, `PORTFOLIO_CONTEXT`, `CONCENTRATION_RISK`) referencing primary keys + checksums/metadata only—they do not duplicate scoring math.

## Non-goals (guardrails)

- No ML / predictive enrichment.
- No auto buying or execution integrations.
- No mutation of upstream P39 artefacts.
- No external feeds or probabilistic forecasting.
