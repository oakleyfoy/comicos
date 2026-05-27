# Market signal architecture (P39-04)

## Philosophy

ComicOS market signals are a deterministic interpretation layer over persisted P39-03 acquisition scores.

Hard boundaries:

- no score recomputation
- no ML, AI inference, or probabilistic classification
- no external data, sentiment, or prediction
- no mutation of scoring, normalization, or ingestion ledgers

This layer exists to translate score outputs into explainable signal categories that remain stable across reruns when the underlying score snapshot is unchanged.

## Dependency chain

Signal generation reads only:

- `MarketAcquisitionScoreSnapshot`
- `MarketAcquisitionScore`
- `MarketAcquisitionScoreEvidence`

The full dependency chain is therefore:

`ingestion -> normalization -> scoring -> signals`

Signals never reach backward to edit or regenerate any prior layer.

## Ledger

The signal system persists four tables:

- `MarketAcquisitionSignalSnapshot`
- `MarketAcquisitionSignal`
- `MarketAcquisitionSignalEvidence`
- `MarketAcquisitionSignalHistory`

Each signal snapshot is tied directly to a single `MarketAcquisitionScoreSnapshot` for exact traceability.

## Taxonomy

Primary signal types:

- `VALUE_DISLOCATION`
- `LIQUIDITY_OPPORTUNITY`
- `PORTFOLIO_GAP_FILL`
- `CONCENTRATION_REDUCTION`
- `GRADING_UPSIDE`
- `REDUNDANT_ASSET`
- `HIGH_RISK_ASSET`

Signal strength is a direct deterministic mapping from `final_rank_score`:

- `85..100` -> `ELITE`
- `70..84.99` -> `HIGH`
- `50..69.99` -> `MEDIUM`
- `<50` -> `LOW`

`signal_score` mirrors the persisted rank score so downstream consumers can compare scoring and signal layers without translation loss.

## Deterministic mapping rules

Signals are selected from persisted score rows plus their evidence bundle:

- `VALUE_DISLOCATION`: high score plus normalized price materially below normalized FMV
- `LIQUIDITY_OPPORTUNITY`: strong liquidity score plus strong demand proxy from the scoring layer
- `PORTFOLIO_GAP_FILL`: high portfolio-fit and diversification scores
- `CONCENTRATION_REDUCTION`: high concentration-reduction score with an overexposed upstream category
- `GRADING_UPSIDE`: strong grading-upside score with favorable normalized condition band
- `REDUNDANT_ASSET`: duplicate overlap already detected in the scoring evidence
- `HIGH_RISK_ASSET`: elevated risk penalty, weak liquidity, or high risk band

When multiple rule candidates match, the winner is chosen deterministically by:

1. highest rule driver score
2. fixed signal priority ordering

That tie-break ordering is explicit and stable, so identical score/evidence inputs always produce the same primary signal.

## Evidence

Each signal emits:

- `SOURCE_SCORE`
- `SCORING_FACTORS`
- `TRACEABILITY`

These rows capture:

- source score id and score-snapshot id
- source score checksum and score-snapshot checksum
- contributing component values such as liquidity, fit, concentration reduction, grading upside, and duplicate overlap
- the selected signal rule and its reason payload

This gives ops and dashboard surfaces score-to-signal traceability without re-deriving the scoring engine.

## Replay safety

- Per-signal checksum hashes the source score checksum, source score snapshot checksum, selected signal type, strength, and reason payload.
- Snapshot checksum hashes the ordered set of signal rows for one owner and one source scoring snapshot.
- Replaying `POST /market-signals/generate` against an unchanged scoring snapshot returns the existing signal snapshot and does not duplicate signal, evidence, or history rows.
- If the upstream scoring snapshot changes, a new signal snapshot is produced cleanly and history appends.

## API surface

### Owner routes

- `POST /market-signals/generate`
- `GET /market-signals`
- `GET /market-signals/{id}`
- `GET /market-signal-snapshots`
- `GET /market-signal-evidence`
- `GET /market-signal-history`

### Ops routes

- `GET /ops/market-signals`
- `GET /ops/market-signals/{id}`
- `GET /ops/market-signal-snapshots`
- `GET /ops/market-signal-evidence`
- `GET /ops/market-signal-history`

Owner and ops reads share the same schema contract, with ops adding optional owner scoping.

## UI surfaces

- `DashboardPage`: signal-layer summary counts by key signal types
- `OperationsPage`: dense signal table, evidence traceability, checksum inspection
- `InventoryDetailPage`: top signal badge only

These remain read-only summary surfaces over persisted signal snapshots.

## Non-goals

- ML-based signal classification
- predictive signal evolution
- real-time streaming classification
- external sentiment or marketplace feeds
- AI-driven weighting or autonomous actioning
