# Portfolio–market coupling architecture (P39-06)

This document describes how **internal portfolio intelligence (P38)** and **external market intelligence (P39)** are joined in a **read-only, deterministic** way. The coupling engine is observational: it does **not** mutate portfolio rows, market ingestion, normalization, scoring, or signal tables, and it performs **no autonomous trading or ranking overrides**.

## Philosophy

- Build a **relational bridge** so product surfaces can answer two questions at once: *how do market opportunities line up with portfolio gaps?* and *how does portfolio structure filter which market rows are relevant?*
- Keep every output **replay-safe**: the same opportunity snapshot, the same portfolio snapshot context, and stable sort keys must produce the **same checksum**.
- Treat ML, fuzzy similarity, and probabilistic matching as **non-goals** (see TECH_DEBT.md).

## Data model overview

Ledger tables (`PortfolioMarketCoupling*`):

| Table | Responsibility |
| --- | --- |
| `portfolio_market_coupling_snapshot` | Single rollup keyed on `(owner, opportunity_snapshot, checksum)`. Stores portfolio KPI mirror, coupling KPIs, and coverage ratios. |
| `portfolio_market_coupling_edge` | One row per deterministic `(candidate, coupling_type, opportunity_item)` pair (plus optional portfolio item linkage). Stable ordering derives from deterministic keys—not DB insertion order—for checksums and API sorts. |
| `portfolio_market_coupling_evidence` | Lightweight audit trail tying each snapshot back to portfolios, normalized candidates, concentrated publishers, duplication counts, etc. |
| `portfolio_market_coupling_history` | Append-once bookkeeping per coupling snapshot checksum (alignment + rollup counts only). |

## Deterministic coupling rules

1. **Inputs** – Always read persisted `MarketAcquisitionOpportunity*` rows for the referenced opportunity snapshot plus P38-derived context (portfolio items, exposures, liquidity, concentration aggregates). Nothing is recomputed upstream.
2. **Edge emission** – For each deterministic opportunity item (sorted ascending by `market_acquisition_opportunity_item.id`), evaluate explicit predicates (canonical comic issue matches, deterministic publisher/title/issue slugs aligned with exposures, deterministic signal classifications). Strength levels flow from persisted signal tiers; coupling scores derive from deterministic integer arithmetic on signal strength × coupling-type offsets × portfolio-fit hints.
3. **Ordering** – Edges emitted into memory are sorted `(candidate_id ASC, portfolio_item_id ASC with NULL sentinel, coupling_type LEX, coupling_strength LEX, opportunity_item.id ASC)`. API detail queries mirror this order.
4. **Checksum** – `sha256(canonical_json)` over `{opportunity summary, summarized portfolio anchors, deterministic edge payloads}`. Replay hits the uniqueness constraint `(owner_user_id, opportunity_snapshot_id, checksum)` without inserting duplicates.

## Coverage metrics

Stored on each snapshot row:

| Field | Meaning |
| --- | --- |
| `signal_coverage_ratio` | Share of opportunity items with ≥1 positive (non-conflict) coupling edge versus total opportunity items—surrogate for signals mapped onto portfolio-readable needs. |
| `scoring_coverage_ratio` | Share of opportunity items whose normalized candidate resolves to an applicable `MarketAcquisitionScore` row for the owner/date scope—surrogate for scoring→portfolio context bridging. |
| `normalization_coverage_ratio` | Share of normalized candidates on the snapshot that report `SUCCESS` status—ties back to completeness of P39-02 payloads. |

## Replay safety model

Generating the pairing twice with identical deterministic inputs yields `replayed: true`, returns the persisted snapshot ids, increments **no upstream tables**, keeps history unique per coupling snapshot (`UniqueConstraint(portfolio_market_coupling_snapshot_id)`), and never rewrites prior edges.

## API surface summary

Owners call `/market-portfolio-coupling*`, admins call `/ops/market-portfolio-coupling*`. Filters cover `coupling_type`, `coupling_strength`, snapshot date spans, coupling score floors, alignment floors, and optional ops `owner_user_id`.

## Frontend expectations

The dashboard exposes a **coupling layer** card row; inventory detail shows a teaser badge keyed off portfolio items; Operations renders edge tables plus checksum reconciliation.

## Explicit non-goals

- Automated trade generation, brokerage routing, recommendation overrides, reinforcement learning rerankers.
- Mutation of ingestion, normalization, scoring, signal, liquidity, recommendation, concentration, inventory FMV layers.
- Fuzzy clustering of candidates or stochastic portfolio weighting adjustments.
