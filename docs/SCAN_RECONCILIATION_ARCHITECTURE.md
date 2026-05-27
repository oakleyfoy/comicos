# P40-05 Scan Reconciliation Architecture

## Philosophy

P40-05 is the first layer that answers the question "what comic is this?" It converts provisional OCR candidates from P40-04 into deterministic canonical comic identity matches using only local reference data, explicit scoring, and append-only evidence.

## Relationship to OCR

- Inputs must originate from a completed P40-04 OCR run.
- The reconciliation layer does not mutate OCR artifacts, normalized artifacts, boundary artifacts, or original scan uploads.
- Lineage chains original scan checksum → normalization checksum → boundary checksum → OCR checksum → reconciliation checksum → reconciliation artifact checksums.

## Canonical dataset model

The canonical dataset is sourced entirely from local ComicOS registry tables:

- `publisher`
- `comic_title`
- `comic_issue`
- `variant`
- `metadata_alias`

The dataset snapshot is ordered deterministically and hashed into a `canonical_dataset_version`. No live marketplace APIs, no remote lookups, and no nondeterministic data sources participate in reconciliation.

## Deterministic identity resolution

The pipeline:

1. Loads OCR candidates and OCR confidence summaries from P40-04
2. Normalizes title, publisher, and issue-number values deterministically
3. Builds a versioned canonical dataset snapshot
4. Scores canonical comic candidates with fixed title / issue / publisher / date / OCR weights
5. Persists every surviving candidate rank and score breakdown
6. Resolves a deterministic decision status
7. Emits append-only issues, artifacts, history rows, and the final manifest

No AI weighting, semantic completion, or speculative inference is used.

## Confidence scoring model

Candidate confidence is a fixed weighted blend of:

- title similarity
- issue similarity
- publisher similarity
- publication-date proximity
- OCR confidence weighting

Decision thresholds are explicit and deterministic:

- `MATCH_CONFIRMED`
- `MATCH_PROBABLE`
- `MATCH_AMBIGUOUS`
- `NO_MATCH_FOUND`
- `MULTIPLE_HIGH_CONFIDENCE_MATCHES`

## Candidate ranking system

Candidate ordering is stable on:

1. descending final confidence
2. descending combined score breakdown
3. publisher
4. title
5. issue number
6. variant description
7. canonical comic id

This guarantees replay-safe ordering even when candidate scores tie.

## Replay-safe checksum lineage

`reconciliation_checksum` hashes:

- upstream scan / normalization / boundary / OCR checksums
- canonical dataset version
- normalized OCR facts
- candidate rankings and score breakdowns
- reconciliation decision
- issue rows
- artifact checksums

Repeated runs on identical inputs with the same dataset version return the existing reconciliation run.

## Non-goals

- grading intelligence
- defect detection
- marketplace valuation
- external API lookups
- AI semantic matching
- hallucinated comic identities
- mutation of immutable upstream evidence
