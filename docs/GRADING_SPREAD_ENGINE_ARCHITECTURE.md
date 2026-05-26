# Grading Spread Engine Architecture

P37-02 adds a deterministic raw-vs-graded spread ledger. The goal is explainable grading economics, not prediction or recommendation.

## Philosophy

- Treat every spread record as an append-safe snapshot.
- Keep calculations Decimal-safe and reproducible.
- Use only current evidence and deterministic joins.
- Never mutate FMV, inventory, or liquidity source tables.
- Keep owner writes separate from ops read-only visibility.

## Tables

- `grading_spread_snapshot`: the generated spread ledger row.
- `grading_spread_evidence`: append-only evidence used to explain the snapshot.
- `grading_spread_band`: optional deterministic status band configuration.
- `grading_spread_history`: append-safe historical spread observations.

## Deterministic formulas

- `estimated_spread_amount = graded_fmv_amount - raw_fmv_amount`
- `estimated_spread_pct = estimated_spread_amount / raw_fmv_amount`
- `estimated_net_upside = estimated_spread_amount - grading_cost_amount`
- `liquidity_adjusted_upside = estimated_net_upside * liquidity_modifier_weight`

All values are quantized with Decimal rounding before checksum generation.

## Liquidity adjustments

Liquidity is a multiplier only:

- `HIGH` -> `1.00`
- `MEDIUM` -> `0.85`
- `LOW` -> `0.65`

The engine does not forecast future liquidity or alter liquidity state. It only applies the current deterministic snapshot as a weighting factor.

## Spread classification

Current status rules:

- `INSUFFICIENT_DATA` when raw, graded, or liquidity evidence is missing.
- `NEGATIVE` when net upside is below zero.
- `WEAK` for low-positive upside or very small spread percentage.
- `MODERATE` for positive spread with usable evidence.
- `STRONG` for healthier upside with good liquidity and confidence.
- `ELITE` for exceptional upside with high liquidity and high confidence.

The code keeps the exact thresholds close to the classifier so tests and review can trace them without hunting through routing code.

## Replay safety and checksums

Snapshot and history payloads are serialized with stable key ordering and hashed with SHA-256.

- Same inputs produce the same checksum.
- Same replay key returns the same snapshot instead of creating a duplicate.
- History rows are append-only and are not rewritten in place.

## APIs

Owner routes:

- `GET /grading-spreads`
- `GET /grading-spreads/{id}`
- `GET /grading-spreads/evidence`
- `GET /grading-spread-history`
- `POST /grading-spreads/generate`

Ops routes:

- `GET /ops/grading-spreads`
- `GET /ops/grading-spreads/{id}`
- `GET /ops/grading-spread-evidence`
- `GET /ops/grading-spread-history`

## Non-goals

- Grade prediction
- AI grading
- Recommendation engines
- Dynamic forecasting
- Grader API integrations
- Hidden mutation of FMV, inventory, or liquidity systems

