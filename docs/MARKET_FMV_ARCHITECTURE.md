# Market and FMV architecture (P35 closeout)

ComicOS keeps **deterministic observability**: raw market ingestion, deterministic normalization bookkeeping, curated match suggestions for canonical alignment, deterministic comp-eligibility labeling, immutable FMV and trend snapshots, inventory FMV attachments, comparable sales visibility, and portfolio rollups derived from attachments.

This document summarizes **behavioral boundaries** and **ordering contracts** implemented for P35-10 reporting and dashboards.

---

## Registry and raw preservation

Source rows live in ordered market-source tables with stable integer priorities. System presets are idempotently seeded. Import runs are append-mostly workflows with deterministic status transitions audited through run events.

**Raw market sale preservation:** Each sale row stores deterministic normalized fields separately from importer-provided raw title/issue/publisher/variant/grade text. Upserts never discard raw strings; reviewers may write normalized fields explicitly.

Deterministic sorting for sale lists prefers recency (`sale_date` descending with null-last semantics), ties broken by `(source_name, normalized_title, normalized_issue, sale id)`.

---

## Normalization review

Normalization issues persist as typed rows referencing a sale (`issue_type`, deterministic `severity`, JSON `details_json`). Review-queue aggregates are deterministic counts keyed by deterministic classification enums.

For exports, aggregated counts group by `(issue_type, severity)` with lexicographic sort — never by nondeterministic row ids alone.

---

## Canonical match suggestions

Match suggestions deterministically propose canonical-issue alignment for importer rows based on deterministic scoring thresholds. Operators explicitly approve/reject/ignore artifacts; approvals may lift comp eligibility gates but never auto-mutate canonical issues or inventory without separate workflows.

Exports of eligible comps filter to `eligible` status deterministically sorted by eligibility service ordering.

---

## Comp eligibility

Comp eligibility summarizes **gates** computed from deterministic rule checks (pricing, grading, currency coverage, duplication flags, ignore state, unresolved identity constraints, approved canonical linkage). Outputs are explanatory labels (`eligible`, `needs_review`, `ineligible`), not trade instructions.

Eligible-comp exports omit buyer/seller PII surfaced on richer detail payloads.

---

## FMV snapshots (methodology envelope)

Snapshots are persisted rows describing **eligible referenced sales**, valuation method enums (`median_recent_sales`, `weighted_recent_sales`), currency-specific amounts, deterministic confidence/liquidity/volatility buckets, explicit stale flags tied to ingestion windows, comp counts, and evidence JSON blobs.

Snapshots are **immutable valuation artifacts**. Generating fresh snapshots performs controlled writes confined to FMV ledger tables plus append-only audit rows where applicable; snapshots **must not** silently rewrite manual `InventoryCopy.current_fmv` or manual valuation history snapshots.

Portfolio rollups recombine attachments per inventory row using deterministic precedence across scopes tied to graded vs raw holdings and canonical alignment state.

Ordering for snapshot exports matches list ordering `(snapshot_date desc, scope rank, method rank, id)`.

---

## Comparable sales explorer

Grouped comparables summarize inclusion/exclusion with deterministic classifications and deterministic quality buckets (recency buckets, liquidity signals, volatility labels). Panels are explanatory—no automated bid/ask quoting.

Ordering within exports follows explorer service ordering tied to deterministic sort keys documented in comps tests.

---

## Trend snapshots (limits)

Trend documents compare deterministic FMV history across fixed enumerated windows (`seven_day`, `thirty_day`, `ninety_day`, `one_year`). Outputs record direction enums, deterministic strength enums, deterministic liquidity deltas, volatility scores, stale flags, counts, compact evidence JSON attachments, plus explicit disclaimers baked into deterministic summary JSON.

Trends intentionally **avoid forecasting semantics**: they summarize historical deltas over closed windows relative to deterministic inputs and never emit probability estimates for future periods.

Trend export ordering matches list snapshots `(window rank, created_at ts desc, scope rank, currency, id)`.

---

## Inventory FMV attachment

Attachments project each inventory row to at most one active FMV snapshot + optional trend excerpt + evidence tuple via deterministic scope precedence. Preconditions (preorder versus cancelled exclusions) omit market numbers while preserving scope labels consistent with summaries.

Portfolio summaries aggregate deterministic currency-separated totals with explicit buckets for preorder informational values, duplicate ownership exposure summaries, stale FMV overlays, cancelled exclusions, low-confidence valuations, no-market counts, raw vs graded split.

---

## Deterministic exports and reports (`/reports/market*` and `/ops/reports/market*`)

Exports return UTF-8 CSV or JSON envelopes with deterministic column tuples and deterministic row sorting. Sensitive fields (seller/buyer names, unstructured metadata blobs) intentionally stay off fleet-wide CSV aggregates.

`/reports/market-deterministic-summary.json` (plus ops twin) merges coverage counts, normalization aggregates, deterministic trend counters, deterministic comp status counters, deterministic portfolio summaries, deterministic attachment trace exemplars capped for payload size (`<=120`), and deterministic boundary disclaimers. Keys sort lexicographically inside `dumps_report_json`.

---

## Non-goals and explicit exclusions

Cross-cutting prohibitions reaffirmed throughout P35 (and surfaced in deterministic summary disclaimers):

- **No forecasting** — descriptive windows only; no probability models for unseen periods.
- **No buy/hold/sell recommendations** language or implicit trading guidance.
- **No grading crossover recommendations** — eligibility never instructs slabbing or crossover.
- **No speculation upside scoring** distinct from enumerated deterministic quality buckets tied to ingestion evidence.
- **No metadata mutation** from read-only dashboards, exports, deterministic summaries.
- **No inventory mutation** from export generation or deterministic summary reads beyond explicit review endpoints outside this envelope.
