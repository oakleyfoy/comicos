# Grading Recommendation Engine Architecture

## Purpose

`P37-06` adds deterministic grading recommendation intelligence for ComicOS.

This is the first decision-support layer in the grading stack. It consumes existing deterministic ledgers and turns them into explainable recommendations without hidden scoring, AI model calls, probabilistic ML, or automatic mutation.

Questions this layer answers:

- should this book be graded
- which grader is preferred
- which grading candidates are strongest
- which books should stay raw
- which books are too risky
- where grading economics are compelling

## Inputs

Recommendations are assembled from persisted deterministic evidence only:

- grading candidates
- grading ROI snapshots
- grading spread snapshots
- liquidity snapshots
- grading reconciliation history
- grader performance snapshots
- listing intelligence snapshots
- realized sale / market sale evidence when available

No external grader APIs, scan AI, or hidden heuristics are consulted.

## Models

- `GradingRecommendation` stores the current recommendation snapshot and checksum.
- `GradingRecommendationEvidence` stores the evidence rows that explain the snapshot.
- `GradingRecommendationScenario` stores pessimistic / baseline / optimistic deterministic scenarios.
- `GradingRecommendationHistory` stores append-safe historical recommendation signatures.

Recommendation actions:

- `GRADE`
- `HOLD_RAW`
- `REVIEW_MANUALLY`
- `NOT_RECOMMENDED`

Recommendation strength:

- `WEAK`
- `MODERATE`
- `STRONG`
- `ELITE`

Risk levels:

- `LOW`
- `MEDIUM`
- `HIGH`

Recommendation status:

- `ACTIVE`
- `SUPERSEDED`
- `ARCHIVED`

## Deterministic Formulas

The engine picks the best available ROI snapshot for the target candidate or inventory scope, preferring the highest liquidity-adjusted ROI and then highest raw ROI. That choice determines the candidate grading path used for the recommendation.

Base recommendation inputs:

- expected ROI from `GradingRoiSnapshot.estimated_roi_pct` or candidate fallback
- liquidity-adjusted ROI from `GradingRoiSnapshot.liquidity_adjusted_roi`
- estimated net profit and total cost from the selected ROI path

Deterministic modifiers then adjust the outlook:

- liquidity:
  - `HIGH`: `+0.15`
  - `MODERATE`: `+0.05`
  - `LOW` / `ILLIQUID`: `-0.20`
- listing intelligence:
  - `STRONG`: `+0.05`
  - `ADEQUATE`: `+0.02`
  - `WEAK` / `INCOMPLETE` / `INSUFFICIENT_DATA`: risk penalty
  - stale-risk flag: `-0.05` and risk penalty
- reconciliation:
  - `ABOVE_EXPECTATION`: `+0.08`
  - `MET_EXPECTATION`: `+0.03`
  - `BELOW_EXPECTATION`: `-0.10`
  - `INSUFFICIENT_DATA`: `-0.03`
- grader performance:
  - strong above-expectation ratio: `+0.08`
  - neutral / mixed history: `+0.03` to `-0.04`
  - poor history: `-0.10`

Checksums are derived from a stable JSON payload with sorted keys. The same inputs yield the same checksum.

## Recommendation Rules

The recommendation action is deterministic:

- `NOT_RECOMMENDED`
  - negative expected ROI
  - negative liquidity-adjusted ROI
  - negative estimated net profit
- `HOLD_RAW`
  - weak or negative spread evidence
  - expected ROI below `0.25`
  - liquidity-adjusted ROI below `0.25`
- `REVIEW_MANUALLY`
  - missing core evidence
  - conflicting evidence
  - high risk with insufficient confidence
- `GRADE`
  - expected ROI at least `0.35`
  - liquidity-adjusted ROI at least `0.35`
  - risk not high
  - stronger grade recommendations appear when expected ROI reaches `0.75+`

Strength classification:

- `ELITE`: grade recommendation with expected ROI at least `1.50`, confidence at least `80`, and low risk
- `STRONG`: clear grade opportunity or confident negative call
- `MODERATE`: usable but less decisive
- `WEAK`: low-confidence or manual-review outputs

## Confidence Logic

Confidence is a deterministic numeric score from `0` to `100`.

Base score starts at `25` and adds evidence coverage:

- ROI evidence: `+20`
- spread evidence: `+15`
- liquidity evidence: `+10`
- medium/high liquidity confidence: `+5`
- reconciliation evidence: `+10`
- grader performance with at least 3 submissions: `+10`
- listing intelligence: `+5`
- strong/adequate listing intelligence: `+5`
- realized sale evidence: `+5`
- market sale evidence: `+5`

Risk penalties subtract `8` points per risk point.

Interpretation:

- `LOW`: under `45`
- `MEDIUM`: `45-79.99`
- `HIGH`: `80+`

The current schema stores the numeric score; bands are a presentation concern.

## Risk Modeling

Risk is additive and explainable.

Risk points increase from:

- weak / negative ROI
- weak / negative spread
- low or illiquid market conditions
- stale or weak listing intelligence
- below-expectation reconciliation history
- poor grader performance
- missing candidate or market context
- conflicting evidence

Classification:

- `LOW`: `0-1` points
- `MEDIUM`: `2-3` points
- `HIGH`: `4+` points

Warning flags are persisted directly on the recommendation row so the UI can explain why risk increased.

## Scenario Modeling

Each recommendation writes three deterministic scenarios:

- `pessimistic`: `0.90x` value / ROI and `-15` confidence modifier
- `baseline`: `1.00x` value / ROI and `0` modifier
- `optimistic`: `1.10x` value / ROI and `+10` modifier

Grade targets shift by `-0.2`, `0`, and `+0.2` when a numeric grade target exists.

This is descriptive scenario framing only. There is no Monte Carlo simulation or probabilistic modeling.

## Replay Safety And History

Generation is replay-safe and append-safe:

- replay keys reuse the existing recommendation for that owner
- identical checksum payloads reuse the existing recommendation
- older active recommendations for the same scope are marked `SUPERSEDED`
- recommendation history rows are appended, never destructively rewritten

## Owner vs Ops APIs

Owner routes:

- `GET /grading-recommendations`
- `GET /grading-recommendations/{id}`
- `GET /grading-recommendations/evidence`
- `GET /grading-recommendations/history`
- `GET /grading-recommendations/dashboard-summary`
- `POST /grading-recommendations/generate`

Ops routes:

- `GET /ops/grading-recommendations`
- `GET /ops/grading-recommendations/{id}`
- `GET /ops/grading-recommendation-evidence`
- `GET /ops/grading-recommendation-history`
- `GET /ops/grading-recommendations/dashboard-summary`

Ops routes remain read-only and support explicit `owner_user_id` filtering.

## Non-Goals

- scan AI
- defect prediction
- image grading
- probabilistic ML
- live grader APIs
- automatic FMV mutation
- automatic inventory mutation
- automatic pricing mutation
- automatic grading submission
- autonomous grading decisions without explicit human review
