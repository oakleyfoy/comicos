# Duplicate & consolidation intelligence (P38-02)

## Philosophy

ComicOS **duplicate intelligence** is an observational, deterministic layer that sits above inventory facts, liquidity snapshots, grading ledgers (recommendations, ROI, risk), and portfolio overlaps. It answers:

- which copies collide on canonical issues, variants, grading overlap paths, portfolio boundaries, or raw↔graded mixes;
- which copies rank higher on a transparent strength curve;
- when duplicate depth trips documented duplication posture buckets;
- what **consolidation captions** tie back to deterministic evidence rows (still no automation).

**Non-goals (explicit)**

- Automated selling/listing/market liquidation
- Acquisition or buy-list intelligence
- Predictive modeling, ML tuning, stochastic scoring
- FMV/auto-pricing/portfolio/auto-rebalancing mutations
- Hidden grading or submission actions

Engines **never** mutate `InventoryCopy`, portfolios, liquidity, grading candidates, FMV surfaces, listings, sales ledgers, or recommendation rows.

Append-safe semantics:

- New duplicate batches **always add** `DuplicateHistorySnapshot`, `DuplicateCluster`, `DuplicateClusterItem`, `DuplicateConsolidationRecommendation` rows tied to deterministic checksums + snapshot dates + replay keys.
- Prior ACTIVE consolidation rows are transitioned to **`SUPERSEDED`** when a materially new batch is persisted for the owner (replay-safe idempotent regeneration excepted).

---

## Models

| Model | Role |
| --- | --- |
| `DuplicateCluster` | Canonical duplicate grouping with aggregate FMV/cost tails, duplication posture, liquidity profile, salted batch checksum linkage. |
| `DuplicateClusterItem` | Explainable inventory membership with deterministic strength scoring, liquidity score, KEEP/WATCH/CONSOLIDATE/SELL Candidate priorities (descriptive labels). |
| `DuplicateConsolidationRecommendation` | Exactly one ACTIVE observational consolidation caption per duplicate cluster snapshot (plus historical superseded rows). |
| `DuplicateHistorySnapshot` | Lightweight append-only rollup per `{cluster_key, snapshot_date}` within a salted batch fingerprint. |

Liquidity posture on clusters uses **HIGH / MEDIUM / LOW** (spec “MEDIUM”; liquidity engine emits MODERATE for item rows — clustered averages map deterministic numeric buckets).

Replay contract:

| Input | Behaviour |
| --- | --- |
| `snapshot_date` | Defaults to deterministic UTC calendar day if omitted |
| `replay_key` | Optional; blank replay keys normalize to empty string uniqueness |
| Deterministic clustering | Computes structural cluster checksum ordering |
| **`generation_batch_checksum`** | `_sha256(snapshot_date.isoformat + replay_key + sorted structural cluster fingerprints))` so identical inventory fingerprints on distinct calendar days persist without colliding uniqueness |

Cluster uniqueness `(owner_user_id, generation_batch_checksum, cluster_type, cluster_key)` therefore tolerates materially identical structural clusters across **different salted batches** — required for longitudinal duplicate history without deleting prior truth.

Structural cluster checksum hashing includes ordered inventory fingerprints (grading band, deterministic priority tags, deterministic liquidity tiers, deterministic tie-break IDs).

---

## Clustering determinism

Dimensional coverage:

| `cluster_type` | Rule (requires ≥ 2 qualifying inventory IDs) |
| --- | --- |
| `exact_issue` | Shares `canonical_comic_issue_id` |
| `variant_family` | Shares `variant_id` |
| `graded_overlap` | Same issue with ≥ 2 graded (non-pipeline slabbed) duplicates |
| `raw_graded_overlap` | Issue mixes graded + (`RAW` or `GRADING_PIPELINE`) simultaneously |
| `portfolio_overlap` | Issue duplicates spanning ≥ 2 ACTIVE portfolio memberships |

Portfolio detection uses ACTIVE `portfolio_item` ∩ ACTIVE `portfolio` rows.

Grading pipeline membership uses deterministic `grading_candidate.status ∈ {CANDIDATE, REVIEWING, READY_FOR_SUBMISSION, SUBMITTED}` with `archived_at IS NULL`.

Sorting / tie-break guarantees:

1. Canonical cluster specs sorted lexically by `(cluster_type, cluster_key)` before hashing.
2. Inventory rows inside specs sorted ascending by `inventory_item_id`.
3. Strength scoring resolves ties `(strength descending, inventory id ascending)`.

---

## Strength scoring (deterministic transparency)

Weighted linear composition (clamp 0–100 with two decimals):

| Signal | Contribution |
| --- | ---: |
| FMV percentile rank inside cluster (`10 .. 37` spread) |
| Liquidity ordinal map (`HIGH 85`, `MODERATE 70`, etc.) multiplied by **`0.30`** |
| Grading posture (`RAW 24`, `PIPELINE 30`, `GRADED 39`) |
| Latest grading recommendation (`ELITE→MARGINAL` map + capped confidence bonus ≤ 80) |
| Latest grading ROI liquidity-adjusted ROI breakpoints |
| Grading risk penalty (`HIGH −12`, `MEDIUM −7`, `LOW −2`, default −5`) |

Interpretation surfaced as **`estimated_strength_score`** on duplicate items and drives KEEP vs tail classifications.

Hidden randomness prohibited; any future weight change must revise documentation + deterministic regression fixtures.

---

## Duplication posture rules

Baseline count ladder (duplicate depth after first keeper):

| Count | Classification |
| --- | --- |
| 2 copies | HEALTHY |
| 3 | WATCH |
| 4–5 | REDUNDANT |
| ≥ 6 | OVEREXPOSED |

Escalations (additive bumps along ladder):

- Cluster liquidity profile **LOW** with ≥ 3 duplicates → bump one notch worse.
- Weak-half FMV share ≥ **35%** of cluster FMV (when FMV totals exist) → bump one notch worse.

Interpretation surfaced as **`duplication_status`** on clusters + echoed for history summaries.

---

## Consolidation captions (policy-free)

Recommended actions (**observational** strings only):

| Action | Deterministic cue |
| --- | --- |
| `HOLD` | HEALTHY duplication posture |
| `GRADE_STRONGEST_COPY` | `raw_graded_overlap` mixes |
| `REDUCE_EXPOSURE` | REDUNDANT / OVEREXPOSED ladders |
| `SELL_DUPLICATES` | Tail priorities flagged consolidate/sell candidates on shallow variant/issue clusters |
| `KEEP_BEST_COPY` | Fallback anchor retention narrative |

Supporting numeric hints (`expected_capital_reduction`, `estimated_liquidity_improvement`, `estimated_portfolio_efficiency_gain`) are **indexed heuristics** (0–100 style magnitudes); they are intentionally *not trades* nor marketplace orders.

Confidence (`LOW|MEDIUM|HIGH`) encodes deterministic data sufficiency—not predictive certainty.

---

## APIs

Owner:

- `/duplicate-intelligence/summary`
- `/duplicate-clusters[/id]`
- `/duplicate-cluster-items`
- `/duplicate-consolidation-recommendations` (`status` filter alias)
- `/duplicate-history`
- `/duplicate-clusters/generate`

Ops mirrors under `/ops/duplicate-*` sharing owner filter semantics aligned with Portfolio ops controls.

Filtering supports canonical issue, duplication posture, liquidity profile, consolidation action, bounded date windows, inventory membership, truncated history keys, optional `latest_only` presets.

---

## UI surfaces

Dashboard duplicate rail + deterministic generate CTA (`replay_key = web-dup-dash-<epoch>` refresh pattern).

Operations duplicate telescope inherits portfolio owner drafts for deterministic cross-module scoping parity.

Inventory detail surfaces cluster typology teaser, deterministic strongest-copy heuristic, ACTIVE consolidation captions when present.

---

## Deferred backlog

See `docs/TECH_DEBT.md` § P38-02 — autonomous selling/listing workflows, probabilistic duplication scoring, predictive market timing remain **out-of-scope**.
