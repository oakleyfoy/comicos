# Technical debt log

Operational notes for intentional deferrals and known cleanup work. Entries should be actionable when someone has a maintenance window.

## `apps/api/app/main.py` — Ruff / structure (updated 2026-05-23)

Run: `python -m ruff check app/main.py` from `apps/api`.

### Duplicate HTTP handlers

Resolved during P32 closeout. The duplicate registrations for match-confidence regeneration were removed and route-count regression coverage was added in `apps/api/tests/test_ops_admin.py`.

Resolved routes:

| Route | Cleanup |
| --- | --- |
| `POST /cover-images/{cover_image_id}/regenerate-match-confidence` | Reduced to a single handler |
| `POST /ops/cover-images/{cover_image_id}/regenerate-match-confidence` | Reduced to a single handler |
| `GET /ops/cover-images/{cover_image_id}/relationship-graph` | Restored explicit ops route to match the web client |
| `GET /ops/cover-relationship-graph` | Restored explicit query-style ops route for parity |

### Remaining cleanup notes

- **`I001` / `E501`** — `python -m ruff check app/main.py` last cleared on 2026-05-23; new routes should keep decorators wrapped and lines within 100 columns as `main.py` grows.
- **RQ warnings** — Default test runs should remain on `fakeredis`; if new worker/dashboard helpers touch `rq.job.Job`, prefer `job.return_value()` and `job.latest_result()` over deprecated `job.result` / `job.exc_info`.

## P32 closeout notes

- Reconciliation dashboards now expose compact read-only summary counts for conflicts, canonical suggestions, match candidates, duplicate scans, variant families, and replay changes.
- Relationship conflict detection and relationship replay remain strictly non-mutating surfaces. They should continue to log review/audit state only, never automatic relationship or metadata changes.
- The default backend suite should remain independent of an external Redis instance; tests rely on in-memory `fakeredis` wiring in `apps/api/tests/conftest.py`.

## P34 — Scan pipeline / bulk ingest closeout (2026-05-24)

- **Architecture note:** see `docs/SCAN_PIPELINE_ARCHITECTURE.md` for lifecycle boundaries (Fujitsu bulk ingest semantics, Epson high-res escalation lane wording, deterministic QA/routing/replay/dashboard reads without OCR enqueue).

- **Operational surfaces consolidated** (`ScanSessionsPage`, owner dashboard receiving + pipeline rails, Ops **Bulk ingest operations** drawer) prioritize explicit buttons (`Run QA snapshot`, `Generate routing snapshot`, `Queue OCR`) over implicit automation — regression tests cover routing/dashboard non-enqueue guards.

- **Known follow-ups**
  - List endpoints that currently cap at owner-selected limits (scan items `limit=500` in SPA) remain UI-side until product defines shared pagination primitives for ingest queues.
  - FastAPI uniqueness regression only asserts the guarded scan-plane path prefixes enumerated in `test_scan_pipeline_closeout.py`; adding new sibling routers requires extending that registry when paths are logically part of the scan pipeline contract.

## P35 — Market sales foundation closeout (2026-05-24)

- **Architecture note:** market-sale persistence now keeps raw source payloads, ordered image evidence, deterministic issue rows, and stable source registry rows for future comp / FMV work without any live scraping or pricing heuristics.
- **Operational surfaces**: owner reads remain read-only, ops gets the explicit upsert lane, and the dashboard/ops page show compact preview surfaces without mutating inventory metadata.
- **Known follow-ups**
  - Extend market-sales pagination and bulk import ergonomics only when product defines the final ingest workflow.
  - Keep duplicate handling issue-only; no auto-merge or delete paths should be introduced on the sales foundation tables.

## P35-06 — FMV snapshot foundation closeout (2026-05-25)

- **Architecture note:** `market_fmv_snapshot` and `market_fmv_comp_reference` form a separate deterministic ledger sourced only from eligible comps plus approved/high-confidence canonical match state. These rows must stay append-only-or-idempotent snapshot artifacts and must never update `InventoryCopy.current_fmv` or manual `InventoryFmvSnapshot` history.
- **Operational surfaces:** owner dashboard and inventory detail expose read-only FMV snapshot visibility, while ops owns explicit batch generation and comp-reference inspection. Keep all generation semantics currency-specific and deterministic; no FX conversion, prediction, speculation, or recommendation logic should be introduced on this path.
- **Known follow-ups**
  - If snapshot volume grows, move FMV list filtering/aggregation from in-memory service passes to SQL-backed filtering while preserving the current stable sort contract (`snapshot_date`, scope rank, method rank, `id`).
  - If product wants broader graded comp partitioning later, document new scopes explicitly instead of overloading the existing `graded`, `graded_by_company`, and `graded_by_grade` semantics.

## P35-10 — Market reporting / deterministic exports (2026-05-25)

- Architecture note: consolidated in `docs/MARKET_FMV_ARCHITECTURE.md` (deterministic registry, comps, FMV/trend ledgers, attachments, reporting boundaries).
- Owner and ops surfaces share parallel `/reports/market*` vs `/ops/reports/market*` export paths; JSON summaries use `dumps_report_json` for deterministic key ordering while CSV renders share `render_csv` column contracts.
- **Known follow-ups**
  - If portfolio-scale exports exceed comfortable row counts, introduce cursor pagination while preserving lexical sort guarantees on stable keys (`inventory_copy_id`).
  - Consolidate SPA dashboard clustering for ops/owner previews when product finalizes telemetry density budgets (API contracts already stabilized).
  - Operations market workspace: `#market-ops-quicknav` jump links require matching `id` anchors on each panel; `#listing-export-ops` accompanies listing registry/export surfaces — extend the list when new market ops sections ship.

## P36-01 — Listing registry foundation (2026-05-25)

- Architecture note: canonical listing truth layer is documented in `docs/LISTING_REGISTRY_ARCHITECTURE.md` (lifecycle, append-only events/price ledger, replay keys, deterministic image ordering, owner vs ops guards).
- Operational surfaces: Dashboard and Operations include lightweight listing panels only; they must stay read-only aggregates (no posting, no auto pricing, no inventory mutation from listing reads).
- **Known follow-ups**
  - P36-02 seeded deterministic CSV exports documented in `docs/LISTING_EXPORTS_ARCHITECTURE.md`; extending `source_type` enums still requires explicit migrations and must keep canonical listing rows the system of record vs channel-specific shadow state.
  - If multi-quantity allocation semantics grow beyond the current `listing_inventory_link` row, model explicit partial allocations as new append-only ledger rows rather than silent overwrites on existing links.

## P36-02 — Deterministic marketplace export engine (2026-05-25)

- Architecture note: deterministic CSV ledger + replay semantics lives in `docs/LISTING_EXPORTS_ARCHITECTURE.md` (`ListingExport*` models, seeded templates per channel, `replay_key`, eligibility reasons, checksum contracts).
- Owner routes materialize synchronous exports; ops routes expose cross-owner read-only inspection plus mirrored CSV downloads. Generation never touches listing status or invokes external retailer APIs.

### Deferred scope (intentionally not P36-02)

- Live marketplace OAuth/posting integrations (Whatnot/Shopify/eBay uploads, webhook callbacks, webhook-driven status sync).
- Bulk listing-selection surfaces in the SPA (multi-ID workbooks tied to exporter actions); collectors should drive `POST /listing-export-runs` via API clients until UX lands.
- Deeper channel-specific validation (taxonomy enforcement, fulfillment profile binding, SKU schemas).
- Dedicated marketplace credential lockers and KMS-backed secret rotation.
- Async worker offload for heavyweight exports beyond the synchronous FastAPI envelope.
- Rich image packaging pipelines (beyond deterministic cover/scan tokens in CSV placeholders).

## P36-03 — Sales recording system (2026-05-25)

- Architecture note: the realized-sales truth layer lives in `docs/SALES_LEDGER_ARCHITECTURE.md` (`SaleRecord`, `SaleRecordLineItem`, `SaleFinancialAdjustment`, `SaleLifecycleEvent`, deterministic cent rounding, owner vs ops read surfaces).
- Owner routes own the write paths; ops routes stay read-only and can inspect aggregate or event history without mutating the ledger.

### Deferred scope (intentionally not P36-03)

- Inventory quantity decrementing / lot consumption on sale record.
- Partial lot cost allocation beyond the current single-sale / single-listing pattern.
- Marketplace payment imports, refunds/returns workflows, and settlement reconciliation.
- Tax reporting and accounting export pipelines.
- Any live marketplace posting or payment integration.
- Liquidity scoring, recommendations, grading ROI, or sell/hold intelligence.

## P36-04 — Inventory liquidity engine (2026-05-25)

- Architecture note: descriptive liquidity snapshots live in `docs/LIQUIDITY_ENGINE_ARCHITECTURE.md` and are derived from deterministic listing velocity, stale thresholds, and realized sales evidence.
- Owner routes may materialize the current snapshot signature set; ops routes remain read-only mirrors over persisted snapshots, evidence, velocity rows, and stale events.

### Deferred scope (intentionally not P36-04)

- Predictive liquidity scoring or sell-through forecasting.
- Automated repricing or recommendation generation.
- Marketplace-wide intelligence beyond the current owner/item/canonical/channel scopes.
- ML-based sell-through prediction or dynamic threshold tuning.
- Portfolio strategy integration and any automatic liquidation workflow.
- Automatic stale-listing closure or any hidden inventory mutation.

## P36-05 — Convention / show operations (2026-05-25)

- Architecture note: convention operations live in `docs/CONVENTION_OPERATIONS_ARCHITECTURE.md` and track event lifecycles, assignments, movement history, temporary pricing, and sale sessions as an append-safe operational ledger.
- Owner routes own the write paths; ops routes mirror the same data read-only so dealer workflows stay visible without hidden mutation.

### Deferred scope (intentionally not P36-05)

- POS/payment integration and checkout tooling.
- Barcode scanning or offline sync workflows.
- Live dealer dashboards beyond the current lightweight summary panels.
- Quick-sale checkout automation or auto-selling inventory.
- Inventory decrementing or hidden movement state changes.
- Convention analytics, staffing workflows, and settlement reconciliation.

## P36-06 — Listing intelligence (2026-05-25)

- Architecture note: listing intelligence lives in `docs/LISTING_INTELLIGENCE_ARCHITECTURE.md` and explains completeness, export readiness, stale-risk flags, and channel performance using deterministic snapshot rows plus evidence.
- Owner routes generate and inspect the ledger; ops routes mirror the same data read-only and can filter across owners without mutating listing or inventory state.

### Deferred scope (intentionally not P36-06)

- Marketplace-specific validation and channel taxonomy enforcement depth.
- AI-generated title/description suggestions.
- Auto-pricing or sell/hold recommendations.
- Channel recommendations or ranking advice.
- Dynamic scoring thresholds or predictive listing performance.
- Bulk cleanup workflows beyond the current read-only intelligence surfaces.

## P36-07 — Dealer dashboard / Dealer OS foundation (2026-05-25)

- Architecture note: see `docs/DEALER_DASHBOARD_ARCHITECTURE.md` for deterministic rollup composition (`DealerDashboardSnapshot`, metrics ledger, deterministic alerts, deterministic feed ingestion), hashed checksum contracts, owner vs `/ops/dealer-dashboard` mirrors, replay semantics, observational-only alerting, explicit non-goals, and ingestion ordering guarantees.
- **Deferred scope**

  | Track | Deferred item |
  | --- | --- |
  | Connectivity | Websocket/live delta ingestion replacing explicit owner-initiated regeneration |
  | Signals | Dedicated notification/email/SMS delivery routers |
  | Platforms | Responsive mobile cockpit + offline workstation packaging |
  | Workforce | Staffing/task workflows, SLA tracking, ticketing built on dashboards |
  | Intelligence | Recommendation systems, predictive dealer analytics |
  | Comparative analytics | Automated cross-owner benchmarking without deterministic export contracts |

## P36-08 — Operational reporting / deterministic closeout (2026-05-25)

- Architecture note: deterministic append-safe reporting registry + CSV contracts live in `docs/REPORTING_CLOSEOUT_ARCHITECTURE.md` (`OperationalReportRun|File|Item`, UTF-8 CSV checksums, lineage JSON, replay keys, owner vs `/ops/reports` parity, `OPERATIONAL_REPORTS_STORAGE_ROOT`).
- Surfaces intentionally remain **read-mostly bookkeepers** over the P36 stack; they must never “fix” upstream objects, auto-mutate inventory, or enqueue marketplace work.
- **Deferred scope (post-P36)**
  - Real-time streaming / incremental report deltas / websocket fan-out of report status
  - Predictive dealer intelligence, acquisition intelligence, portfolio optimization, ML forecasting
  - Grading ROI systems, speculative pricing, automated sell/hold recommendation engines
  - Notification/email/SMS routers, staffing workflows, ticketing, or external BI sink automation
  - Async worker offload for heavy report fan-out beyond synchronous FastAPI envelopes (unless replay + checksum contracts are preserved)

## P37-01 — Grading candidate registry foundation (2026-05-25)

- Architecture note: append-safe grading intents, evidence lineage, deterministic snapshots (`grading_candidate*` tables) documented in `docs/GRADING_CANDIDATE_ARCHITECTURE.md`. Owners hold write/lifecycle transitions; `/ops/grading*` routes stay read mirrors with standard admin guards.
- This lane deliberately avoids grade prediction, scan AI scoring, defect annotation, PSA/CGC API automation, outbound notifications, and any inventory-side mutation (including silently touching FMV or listing readiness).
- **Deferred scope (beyond P37-01):**
  - Automated grading ROI backtests, probabilistic grading outcomes, speculative market modeling
  - Image-based defect catalogs, automated centering/frame analysis, counterfeit heuristics
  - Recommendation engines tying grading to acquisition or liquidation workflows
  - SLA tracking across physical shipments to graders, webhook callbacks from slabbers, insurance workflows

## P37-02 — Raw-vs-graded spread engine (2026-05-25)

- Architecture note: deterministic grading spread snapshots, evidence rows, and append-safe history are documented in `docs/GRADING_SPREAD_ENGINE_ARCHITECTURE.md`. The lane compares raw FMV, graded FMV, grading cost assumptions, and liquidity-adjusted upside only.
- Owner routes may generate and inspect spreads; `/ops/grading-spreads*` mirrors stay read-only and can filter by owner, issue, inventory, grader, grade, confidence, and spread status.
- **Deferred scope (beyond P37-02):**
  - Grade prediction or AI grading pipelines
  - Scan AI, defect scoring, image-based grading heuristics
  - Recommendation engines, sell/hold guidance, or portfolio optimization
  - Dynamic market forecasting or probabilistic pricing
  - Grader API integrations and automated market posting
  - Hidden FMV/inventory/liquidity mutations

## P37-03 — Grading ROI engine (2026-05-26)

- Architecture note: deterministic grading ROI snapshots, evidence rows, scenarios, and append-safe history live in `docs/GRADING_ROI_ENGINE_ARCHITECTURE.md`. The lane compares grading fees, shipping, insurance, liquidity, and realized-sale evidence to produce deterministic ROI, break-even, and scenario reads.
- Owner routes may generate and inspect ROI snapshots; `/ops/grading-roi*` mirrors stay read-only and can filter by owner, issue, inventory, candidate, grader, grade, confidence, ROI status, and date range.
- **Deferred scope (beyond P37-03):**
  - Grade prediction or AI grading pipelines
  - Scan AI, defect scoring, image-based grading heuristics
  - Recommendation engines, sell/hold guidance, or portfolio optimization
  - Dynamic market forecasting or probabilistic pricing
  - Grader API integrations and automatic market posting
  - Monte Carlo simulation or any probabilistic ROI forecasting
  - Hidden FMV, inventory, grading-candidate, or liquidity mutations

## P37-04 — Grading submission batch operations (2026-05-26)

- Architecture note: deterministic submission batches, lifecycle events, shipment rows, and cost snapshots live in `docs/GRADING_SUBMISSION_BATCH_ARCHITECTURE.md`. The lane groups grading candidates into append-safe workflow records with replay-safe creation and deterministic cost math.
- Owner routes can create and advance batches; `/ops/grading-submission*` mirrors stay read-only and can filter by owner, grader, batch status, and time range.
- **Deferred scope (beyond P37-04):**
  - Grader API integrations or automatic submission posting
  - Automated grade import or reconciliation
  - Webhook systems or live carrier tracking
  - Invoice reconciliation, label printing, packing workflows, or bulk scan intake
  - Any automatic inventory mutation or grade assignment beyond the explicit completion transition

## P33 — Inventory Intelligence closeout (2026-05-24)

- Intelligence reads (risks, action center, timelines, duplication, run gaps, reconciliation summaries) remain **mutation-free** on the dedicated read paths.
- Portfolio FMV dashboards stay separate from deterministic intelligence panels; CSV/JSON snapshots omit FMV where schemas allow (`reports_export`).
- Extending intelligence or exports should preserve explicit tuple sort keys and regression tests rather than ad-hoc nondeterministic ordering.
- New caches or async mutation on intelligence/export code paths need an explicit design note plus tests for ordering, filters, and scope (owner vs ops).