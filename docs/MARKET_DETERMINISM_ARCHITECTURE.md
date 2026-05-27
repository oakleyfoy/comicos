# Market Determinism Layer (P39-10)

This document describes the deterministic validation ledger that audits the existing P39 market pipeline for checksum lineage, replay safety, stable ordering, and explicit invariant compliance.

---

## Philosophy and boundaries

P39-10 is a hardening layer only.

Rules:

1. Validation reads persisted P39 artifacts and writes only to the P39-10 ledger.
2. No upstream intelligence engine is mutated or re-run as part of validation.
3. Replay checks compare canonical recomputations against persisted checksums.
4. Owner routes remain owner-scoped; ops routes remain read-only inspection surfaces.
5. A repeated validation request with the same owner scope and identical source fingerprint reuses the prior validation run.

---

## Data model

The determinism ledger is append-only except for replay-safe reuse on identical validation signatures:

- `MarketDeterminismValidationRun`
- `MarketDeterminismInvariant`
- `MarketDeterminismChecksumAudit`
- `MarketDeterminismReplayAudit`

`MarketDeterminismValidationRun` stores the run-level status, validation checksum, pipeline checksum, counts, and summary JSON. Child rows preserve explainable findings rather than collapsing them into a single pass/fail bit.

---

## Checksum lineage graph

P39-10 validates the persisted checksum chain in sequence:

1. Ingestion batch checksum
2. Normalization run checksum
3. Score snapshot checksum
4. Signal snapshot checksum
5. Opportunity snapshot checksum
6. Coupling snapshot checksum
7. Feed snapshot checksum

The validation service also fingerprints underlying row-level checksums and stable identifiers so silent drift inside a stage still produces a fresh validation run instead of incorrectly reusing a prior result.

---

## Replay validation rules

Replay audits recompute deterministic outputs in memory and compare them to stored originals:

- ingestion batch payload hash
- normalization run checksum
- score snapshot checksum
- signal snapshot checksum
- opportunity snapshot checksum
- coupling snapshot checksum
- feed event checksums and feed snapshot checksum

Replay validation never persists reconstructed upstream artifacts. Only the P39-10 ledger receives writes.

---

## Invariant system

Invariant rows are explicit and explainable. Current rules cover:

- ingestion raw-hash uniqueness and raw-hash determinism
- normalization canonical-key stability
- scoring checksum-group consistency
- signal checksum-group consistency
- opportunity grouping stability
- coupling edge ordering and alignment metric stability
- feed event ordering and replay reconstruction stability

Each invariant stores expected and actual JSON payloads when useful so ops can inspect the exact source of drift.

---

## Audit guarantees

The determinism layer guarantees:

- stable default ordering on validation lists
- replay-safe owner-triggered validation
- append-only child finding rows
- owner and ops read separation through `/api/v1/market`
- checksum and replay evidence suitable for UI drill-down

The web UI surfaces this as:

- a compact dashboard integrity summary
- an ops drill-down section with runs, invariant rows, replay audits, and raw detail
- a lightweight inventory integrity badge

---

## Non-goals

P39-10 intentionally does not add:

- new scoring, signals, opportunity logic, or recommendations
- predictive ranking, ML inference, or probabilistic validation
- auto-remediation or write-back into upstream P39 artifacts
- real-time streaming or background orchestration beyond explicit validation calls
- cross-owner shared validation state
