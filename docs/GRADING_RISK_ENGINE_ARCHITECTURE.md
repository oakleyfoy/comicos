# Grading Risk Engine Architecture

## Purpose

`P37-07` adds deterministic grading risk and confidence infrastructure for ComicOS.

This layer formalizes uncertainty analysis around grading economics and recommendation quality using persisted operational history only. It does not perform scan AI, defect prediction, probabilistic ML, or autonomous grading decisions.

Questions this layer answers:

- how reliable grading recommendations are
- where grading economics are unstable
- where FMV and liquidity assumptions are weak
- where grader performance is volatile
- where confidence should be reduced
- where risk-adjusted economics become unattractive

## Inputs

Risk and confidence snapshots are built from existing deterministic ledgers:

- grading recommendations
- grading ROI snapshots and history
- grading spread snapshots and history
- liquidity snapshots
- reconciliation history
- grader performance snapshots
- listing intelligence snapshots
- market FMV snapshots
- market trend snapshots
- realized sale and market sale evidence when available

No external AI, live grader APIs, or hidden models are consulted.

## Models

- `GradingRiskSnapshot` stores the current risk / confidence rollup.
- `GradingRiskEvidence` stores the evidence rows explaining the rollup.
- `ConfidenceFactorSnapshot` stores deterministic factor scores and fixed weightings.
- `RiskHistory` stores append-safe historical signatures.

Risk levels:

- `LOW`
- `MEDIUM`
- `HIGH`
- `EXTREME`

Confidence levels:

- `LOW`
- `MEDIUM`
- `HIGH`

## Deterministic Weighting

Each confidence factor is scored on a `0-100` scale where higher values mean more stability or stronger evidence.

Fixed weightings:

- `liquidity_stability`: `0.20`
- `spread_stability`: `0.15`
- `roi_stability`: `0.20`
- `grader_consistency`: `0.15`
- `market_depth`: `0.10`
- `evidence_volume`: `0.10`
- `reconciliation_history`: `0.10`

Confidence weight:

`confidence_weight = weighted_factor_score / 100`

Risk-adjusted ROI:

`risk_adjusted_roi = estimated_roi * confidence_weight`

The estimated ROI comes from the linked recommendation when available, otherwise the latest ROI snapshot.

## Factor Logic

### Liquidity stability

Derived from:

- liquidity status bucket
- liquidity confidence bucket
- sell-through rate
- stale listing rate

High liquidity with strong confidence produces a high factor score. Low or illiquid markets with stale signals reduce the factor.

### Spread stability

Derived from:

- latest spread snapshot status / confidence
- recent `GradingSpreadHistory` range

Thin or highly variable spread history reduces confidence.

### ROI stability

Derived from:

- latest ROI snapshot status / confidence
- recent `GradingRoiHistory` range

Negative or highly variable ROI assumptions reduce confidence.

### Grader consistency

Derived from:

- grader submission count
- above / below expectation ratios

Thin grader history or poor below-expectation ratios reduce confidence.

### Reconciliation history

Derived from:

- reconciliation history count
- ROI delta range
- repeated below-expectation outcomes

### Market depth

Derived from:

- market FMV confidence bucket
- FMV volatility bucket
- stale-data flags
- comp count
- market trend volatility score

### Evidence volume

Derived from:

- number of available evidence sources
- available history row count

Thin evidence volume reduces confidence.

## Risk Scoring

The engine stores a mix of direct risk scores and direct stability/strength scores:

- `liquidity_risk_score`
- `spread_volatility_score`
- `roi_volatility_score`
- `grader_variability_score`
- `reconciliation_variance_score`
- `market_stability_score`
- `evidence_strength_score`

Overall risk score is a deterministic weighted combination of:

- direct risk / volatility components
- inverse market stability
- inverse evidence strength

## Classification Thresholds

Confidence level:

- `HIGH`: confidence weight `>= 0.75`
- `MEDIUM`: confidence weight `>= 0.50` and `< 0.75`
- `LOW`: confidence weight `< 0.50`

Risk level:

- `LOW`: weighted risk score `< 25`
- `MEDIUM`: `25-49.99`
- `HIGH`: `50-74.99`
- `EXTREME`: `>= 75`

Additional guard:

- very weak evidence plus already-elevated weighted risk can also promote to `EXTREME`

## Recommendation Integration

Risk generation does not change recommendation action or strength.

Instead, recommendations can expose the latest linked risk snapshot metadata:

- risk snapshot id
- overall risk level
- overall confidence level
- confidence weight
- risk-adjusted ROI

This is additive intelligence only.

## Replay Safety And History

Generation is replay-safe and append-safe:

- replay keys reuse the same risk snapshot for the owner
- identical checksum payloads reuse the same snapshot
- `RiskHistory` appends signature rows instead of rewriting old rows
- checksums use sorted-key stable JSON payloads

## Owner vs Ops APIs

Owner routes:

- `GET /grading-risk`
- `GET /grading-risk/{id}`
- `GET /grading-risk/evidence`
- `GET /grading-risk/history`
- `GET /grading-confidence-factors`
- `GET /grading-risk/dashboard-summary`
- `POST /grading-risk/generate`

Ops routes:

- `GET /ops/grading-risk`
- `GET /ops/grading-risk/{id}`
- `GET /ops/grading-risk-evidence`
- `GET /ops/grading-risk-history`
- `GET /ops/grading-confidence-factors`
- `GET /ops/grading-risk/dashboard-summary`

Ops routes are read-only and support explicit `owner_user_id` filtering.

## Non-Goals

- probabilistic ML
- Monte Carlo simulation
- scan AI
- defect prediction
- image grading
- predictive forecasting
- live grader APIs
- automatic FMV mutation
- automatic inventory mutation
- automatic recommendation action changes
- autonomous grading decisions
