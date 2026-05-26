# Grading ROI Engine Architecture

P37-03 adds a deterministic grading ROI ledger. The goal is explainable grading economics, not prediction, recommendation, forecasting, or AI grading.

## Philosophy

- Treat each ROI snapshot as an append-safe economic artifact.
- Keep all math Decimal-safe, quantized, and reproducible.
- Use only deterministic inputs and current evidence rows.
- Never mutate inventory, FMV, grading candidates, or downstream ledgers.
- Keep owner-write paths and ops-read paths separated.

## Tables

- `grading_roi_snapshot`: the generated ROI ledger row.
- `grading_roi_evidence`: append-only evidence for the snapshot.
- `grading_roi_scenario`: pessimistic, baseline, and optimistic deterministic scenarios.
- `grading_roi_history`: append-safe historical ROI observations.

## Deterministic formulas

- `estimated_total_cost = grading_fee_amount + shipping_cost_amount + insurance_cost_amount`
- `estimated_net_profit = graded_fmv_amount - raw_fmv_amount - estimated_total_cost`
- `estimated_roi_pct = estimated_net_profit / estimated_total_cost`
- `liquidity_adjusted_roi = estimated_roi_pct * liquidity_weight`

All values are quantized before checksum generation.

## Fee assumptions

The engine uses fixed deterministic fee assumptions:

- `PSA`: grading fee `25.00`, shipping `18.00`, insurance rate `1.25%`, turnaround `75` days
- `CGC`: grading fee `30.00`, shipping `20.00`, insurance rate `1.50%`, turnaround `90` days
- `CBCS`: grading fee `28.00`, shipping `19.00`, insurance rate `1.40%`, turnaround `85` days

Insurance is calculated from the graded FMV estimate with a small floor so the total cost stays explicit.

## Liquidity adjustments

Liquidity is a multiplier only:

- `HIGH` -> `1.00`
- `MEDIUM` -> `0.85`
- `LOW` -> `0.65`

The engine does not forecast future liquidity. It only weights the current deterministic snapshot.

## Status classification

Current rules are intentionally simple:

- `INSUFFICIENT_DATA` when raw FMV, graded FMV, liquidity, or fee evidence is missing.
- `NEGATIVE` when net profit is below zero.
- `WEAK` when ROI is low or liquidity-adjusted ROI is weak.
- `MODERATE` when ROI is positive but not strong enough for the upper tiers.
- `STRONG` when ROI is strong and liquidity/confidence are healthy.
- `ELITE` when ROI is exceptional, liquidity is strong, and confidence is high.

## Break-even logic

Break-even is deterministic. The engine computes the minimum grade step needed to offset the total cost using a fixed grade-step assumption per grader.

This is an economics helper only. It is not grade prediction and does not attempt to infer slabbed-grade outcomes.

## Scenario modeling

The engine produces three deterministic scenarios:

- `pessimistic`
- `baseline`
- `optimistic`

Each scenario uses a simple value multiplier plus a one-step grade adjustment where a numeric grade is available. No Monte Carlo or probabilistic forecasting is involved.

## Replay safety and checksums

Snapshot, scenario, and history payloads are serialized with stable key ordering and hashed with SHA-256.

- Same inputs produce the same checksum.
- Same replay key returns the same snapshot instead of creating a duplicate.
- History rows are append-only and are never rewritten in place.

## APIs

Owner routes:

- `GET /grading-roi`
- `GET /grading-roi/{id}`
- `GET /grading-roi/evidence`
- `GET /grading-roi/history`
- `POST /grading-roi/generate`

Ops routes:

- `GET /ops/grading-roi`
- `GET /ops/grading-roi/{id}`
- `GET /ops/grading-roi/evidence`
- `GET /ops/grading-roi/history`

## Non-goals

- Grade prediction
- AI grading
- Recommendation engines
- Dynamic forecasting
- Monte Carlo modeling
- Grader API integrations
- Hidden mutation of FMV, inventory, grading candidates, or liquidity systems

