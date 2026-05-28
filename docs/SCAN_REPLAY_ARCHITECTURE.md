# Scan Replay Architecture

## Purpose

P40-18 adds a deterministic replay and verification ledger for the full P40 scan intelligence pipeline. The replay layer does not create new scan intelligence, assign grades, certify authenticity, estimate FMV, or mutate upstream ledgers. It audits whether stored P40 outputs remain reproducible, checksum-stable, lineage-complete, and immutable.

## Replay philosophy

- Replay is an audit over immutable upstream records, manifests, histories, and artifacts.
- Replay stores append-only verification evidence in its own ledger.
- Replay never rewrites upstream checksums, manifests, artifacts, or histories.
- Replay records discrepancies and issues instead of suppressing them.
- Repeated identical replay input must produce the same `replay_checksum`.

## Data model

The replay layer persists seven append-only tables:

- `scan_replay_runs`: one verification run per deterministic replay manifest.
- `scan_replay_steps`: stable phase-by-phase lineage rows for P40-01 through P40-17.
- `scan_replay_checks`: checksum, artifact, ordering, immutability, owner-isolation, history, and route-read-only verification rows.
- `scan_replay_discrepancies`: durable mismatch records such as checksum drift, lineage gaps, ordering drift, missing artifacts, and immutability violations.
- `scan_replay_artifacts`: replay-only exports such as manifests, audit exports, discrepancy reports, and debug previews.
- `scan_replay_issues`: deterministic reliability issues derived from the replay outcome.
- `scan_replay_history`: append-only replay events describing the verification lifecycle.

## Deterministic verification model

Replay verification follows a stable ordered pipeline:

1. Load the requested replay scope and immutable upstream context.
2. Collect the full P40 lineage chain in fixed phase order.
3. Compare expected lineage checksums against observed stage checksums.
4. Verify artifact presence and immutable checksum integrity.
5. Verify stable ordering for replay steps and persisted feed/review ordering surfaces.
6. Verify append-only history and owner-isolation contracts.
7. Build a stable replay manifest and derive `replay_checksum`.
8. Persist replay steps, checks, discrepancies, issues, artifacts, and history.

## Checksum audit model

Replay preserves a deterministic checksum chain:

`original_scan_checksum` -> stage checksums across P40 -> `feed_checksum` when present -> `replay_checksum` -> replay artifact checksums

The replay layer does not regenerate or rewrite upstream checksums. It validates the stored checksum lineage and records `CHECKSUM_MISMATCH` discrepancies if the observed stage checksum diverges from the expected lineage reference.

## Lineage validation model

Replay collects lineage for:

- ingestion
- normalization
- boundary
- OCR
- reconciliation
- defect foundation
- spine ticks
- corner / edge wear
- surface defects
- structural damage
- defect aggregation
- grading assistance
- visual evidence
- review
- historical comparison
- authentication
- scan intelligence feed

Missing optional stages are recorded as `SKIPPED`. Missing required sources are recorded as `MISSING_SOURCE` plus a discrepancy or issue rather than hidden.

## Discrepancy model

Replay discrepancy types include:

- `CHECKSUM_MISMATCH`
- `MANIFEST_MISMATCH`
- `ARTIFACT_MISSING`
- `LINEAGE_GAP`
- `ORDERING_DRIFT`
- `NONDETERMINISTIC_OUTPUT`
- `IMMUTABILITY_VIOLATION`
- `HISTORY_MUTATION`
- `SOURCE_RECORD_MISSING`
- `REPLAY_EXCEPTION`

Severities remain operational only: `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.

## Immutability contract

Replay verifies that:

- the original scan artifact still exists and still hashes to the stored scan checksum
- persisted stage artifacts still exist and still hash to their stored artifact checksums
- append-only histories remain ordered and unique
- owner isolation remains intact across replayed stage rows

Replay never repairs or overwrites upstream data. If immutability drift is detected, replay records a `CRITICAL` discrepancy and preserves it for audit review.

## Replay artifacts

Each replay run emits replay-owned exports under deterministic paths:

`scan-replay/{owner_user_id}/{scan_image_id_or_global}/{replay_run_id}/{artifact_type}.{ext}`

Current replay artifact types:

- `REPLAY_REPORT`
- `CHECKSUM_AUDIT_EXPORT`
- `LINEAGE_AUDIT_EXPORT`
- `DISCREPANCY_REPORT`
- `REPLAY_MANIFEST`
- `REPLAY_DEBUG_PREVIEW`

These artifacts are append-only and do not overwrite upstream intelligence artifacts.

## Ops diagnostics model

Ops surfaces expose:

- replay run status rollups
- critical discrepancies
- failure discrepancies
- lineage gap summaries
- non-determinism alerts

Ops routes are diagnostic and read-only. They do not trigger destructive repairs or mutate upstream records.

## Non-goals

P40-18 does not:

- create new intelligence
- assign official grades
- certify authenticity
- estimate FMV
- mutate immutable artifacts
- rewrite manifests
- repair missing artifacts
- auto-heal histories
- suppress discrepancies or critical failures
