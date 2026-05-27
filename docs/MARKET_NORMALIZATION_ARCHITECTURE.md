# Market normalization architecture (P39-02)

## Philosophy

ComicOS market normalization is **purely deterministic structuring**: it translates ingestion-layer candidate rows (`MarketAcquisitionCandidate`) into canonical fields suitable for downstream P39 scoring tiers.

Hard boundaries:

- no external APIs, no AI/ML inference, no fuzzy similarity search
- no mutation of ingestion batches, raw sources, ingestion events, or candidate rows
- no ranking, prioritization, or portfolio recommendations inside this lane
- `normalized_liquidity_hint` and `normalized_grade_potential` remain **NULL** unless a future explicitly deterministic rule set is defined — P39-02 does not speculate

Normalization is repeatable: identical inputs snapshot the same fingerprints and therefore replay the same `run_checksum`.

## Layers

Four tables form the normalization ledger:

| Model | Role |
| --- | --- |
| `MarketAcquisitionNormalizationRun` | One execution envelope per `(ingestion_batch_id, run_checksum)` with deterministic counters (`successful`, `partial`, `failed`) plus lifecycle timestamps. |
| `MarketAcquisitionNormalizedCandidate` | One stable row per `ingestion_candidate_id` capturing canonical fields plus `canonical_key`. |
| `MarketAcquisitionNormalizationIssue` | Append-only deterministic issue classifications per `(run, ingestion_candidate_id)`. |
| `MarketAcquisitionNormalizationEvent` | Append-only audit timeline (`RUN_STARTED`, `RECORD_*`, `RUN_COMPLETED`). |

Reads always join normalization rows back to ingestion batches via the run FK to preserve owner/ops scopes.

## Canonicalization rules

1. **Titles** — lowercase, strip punctuation to spaces, squash whitespace, deterministic prefix stripping ordered longest-first (`the amazing spider-man`, `spectacular spider-man`, `the …`, articles, etc.).
2. **Publishers** — deterministic exact alias map (`marvel comics` → `Marvel`, `dc comics` → `DC`, canonical lowercase keys). Anything else retains trimmed surface form (no probabilistic guesses).
3. **Issues** — pull digit groups via regex; a single deterministic integer token wins; multiple digit groups collapse to deterministic ambiguous handling (issue flagged `AMBIGUOUS_MATCH`).
4. **Variants** — explicit synonym table only (`cover a`→`A`, `newsstand`→`Newsstand`, ...). Missing entries produce `VARIANT_CONFLICT` issues when variant text was supplied.
5. **Condition bands** — ordered substring lookups map text to enumerated bands `{UNKNOWN, POOR, GOOD, VERY_GOOD, FINE, VF, NM}`; unrecognized text with payload keeps `UNKNOWN` plus `CONDITION_PARSE_ERROR`.
6. **Money** — ingestion already validates decimal columns; normalization re-quantizes to `Decimal` with deterministic rounding (`ROUND_HALF_UP` to cents). Parsing helpers mark `INVALID_PRICE` if a rogue string slips through isolated tests — production ingestion keeps decimals clean.

Canonical key:

```
sha256(utf8(canonical_title + canonical_publisher + canonical_issue_number + canonical_variant))
```

Empty optional components contribute empty string segments concatenated strictly in that order — identical to ingestion fingerprint requirements for dedupe-ready rows.

## Status model

| Status | Meaning |
| --- | --- |
| `SUCCESS` | Canonical identity derivable without blocking flags/issues. |
| `PARTIAL` | Usable canonical identity while optional/problematic facets remain (publisher missing, unmapped variant, etc.). |
| `FAILED` | Canonical title collapsed to unresolved sentinel — identity unusable until upstream ingestion improves. |

`normalization_flags_json` carries booleans aligned with README requirements (`missing_publisher`, `ambiguous_title`, `invalid_price`, `variant_conflict`, `condition_unmapped`) for dashboards without rescoring.

## Replay + append safety

- `run_checksum` hashes the ordered ingestion candidate fingerprint list (deterministic JSON dump per candidate subset).
- Replaying `POST /market-normalization/run` with unchanged candidates returns HTTP 200 alongside the persisted `MarketAcquisitionNormalizationRun` without duplicating normalized rows/events.
- `FAILED` retries wipe only that run’s normalization children before rebuilding events/issues/candidates deterministically.

## Failure handling / ops visibility

Normalization never deletes ingestion artifacts. Instead:

- deterministic issues record reasons (`INVALID_PRICE`, `VARIANT_CONFLICT`, etc.)
- health rollups summarize cross-run candidate statuses and issue cardinalities without scanning UI layers

Stale `RUNNING` states will surface HTTP 409 to avoid parallel writers — manual remediation (future TECH_DEBT) may add watchdog transitions.

## API surface

### Owner routes

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/market-normalization/run` | Executes normalization for `{ ingestion_batch_id }`. |
| `GET` | `/market-normalization/runs` | Includes embedded `health` rollup for dashboards. |
| `GET` | `/market-normalization/runs/{id}` | Detail + chronological events. |
| `GET` | `/market-normalization/candidates` | Filter by status, canonical publisher, condition band, date window, ingestion batch. |
| `GET` | `/market-normalization/issues` | Mirrors filters for observability dashboards. |

### Ops routes (read-only)

| Method | Path |
| --- | --- |
| `GET` | `/ops/market-normalization/runs` |
| `GET` | `/ops/market-normalization/runs/{id}` |
| `GET` | `/ops/market-normalization/candidates` |
| `GET` | `/ops/market-normalization/issues` |

Ops queries accept optional `owner_user_id` scoping identical to ingestion ops panels.

## Non-goals (explicit deferrals)

- ML entity resolution, fuzzy clustering, probabilistic completeness fills
- automatic publisher/title clustering beyond alias tables curated in-code
- live marketplace scraping or enrichment
- rewriting raw ingestion payloads to “fix” data quality (normalization emits parallel canonical tables only)

Downstream scoring (P39-03+) may consume canonical keys safely because they are deterministic and stable per ingestion revision.
