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
  - Operations market workspace: `#market-ops-quicknav` jump links require matching `id` anchors on each panel; `#listing-export-ops` accompanies listing registry/export surfaces — extend the list when new market ops sections ship (including `#portfolio-liquidity-ops` for P38-03 rollup tables).

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

## P37-05 — Grading reconciliation (2026-05-26)

- Architecture note: deterministic reconciliation records, evidence rows, historical snapshots, and grader performance summaries live in `docs/GRADING_RECONCILIATION_ARCHITECTURE.md`. The lane compares expected grades and ROI assumptions against actual returned grades and realized economics.
- Owner routes may reconcile submission items and inspect outcome history; `/ops/grading-reconciliation*` and `/ops/grader-performance` remain read-only and support explicit owner filtering.
- **Deferred scope (beyond P37-05):**
  - Automated grader imports or live grader API integrations
  - OCR slab reading, scan verification, or AI grading analysis
  - Recommendation engines or post-grade automation
  - Automatic FMV, pricing, or inventory mutation based on reconciliation results
  - Probabilistic grading models or forecasting

## P37-06 — Grading recommendation engine (2026-05-26)

- Architecture note: deterministic recommendation snapshots, evidence rows, scenario rows, and append-safe history live in `docs/GRADING_RECOMMENDATION_ENGINE_ARCHITECTURE.md`. The lane translates existing grading ROI, spread, liquidity, reconciliation, grader performance, and listing-intelligence ledgers into explicit recommendation actions.
- Owner routes may generate and inspect recommendations; `/ops/grading-recommendations*` mirrors stay read-only and support explicit owner filtering without mutating FMV, inventory, listings, or submission workflows.
- **Deferred scope (beyond P37-06):**
  - Scan AI, defect prediction, image grading, or vision-model recommendation inputs
  - Probabilistic ML, forecasting, Monte Carlo scenario generation, or hidden scoring models
  - Live grader APIs, webhook ingest, or automatic submission / return orchestration
  - Autonomous repricing, FMV mutation, inventory mutation, or portfolio auto-actions
  - Fully automated grading decisions without explicit human review

## P37-07 — Grading risk / confidence modeling (2026-05-26)

- Architecture note: deterministic grading risk snapshots, evidence rows, confidence factors, and append-safe history live in `docs/GRADING_RISK_ENGINE_ARCHITECTURE.md`. The lane scores liquidity stability, spread and ROI volatility, grader consistency, reconciliation history, market depth, and evidence volume using fixed weightings only.
- Owner routes may generate and inspect risk snapshots; `/ops/grading-risk*` and `/ops/grading-confidence-factors` remain read-only mirrors with explicit owner filtering and no mutation of recommendations, FMV, inventory, or submission state.
- **Deferred scope (beyond P37-07):**
  - Probabilistic ML, Monte Carlo simulation, or predictive confidence forecasting
  - Scan AI, image grading, defect prediction, or vision-model-derived uncertainty
  - Live grader APIs or webhook-driven confidence adjustments
  - Autonomous grading decisions or automatic recommendation action changes
  - Hidden portfolio, FMV, pricing, or inventory mutations driven by confidence/risk outputs

## P37-08 — Dealer grading dashboard (2026-05-26)

- Architecture note: deterministic grading command-center snapshots, metrics, observational alerts, and append-safe feed events live in `docs/DEALER_GRADING_DASHBOARD_ARCHITECTURE.md`. The lane aggregates grading candidates, recommendation/risk posture, submission ops, reconciliation outcomes, and liquidity evidence into a replay-safe grading cockpit.
- Owner routes explicitly generate grading dashboard snapshots; `/ops/dealer-grading-dashboard*` remains read-only with optional owner scoping and should never mutate candidates, recommendations, submissions, reconciliation rows, FMV, pricing, or inventory.
- **Deferred scope (beyond P37-08):**
  - Real-time websocket updates, push refresh, or background dashboard fan-out
  - Mobile-specific grading dashboards or offline dashboard packaging
  - Scan AI, defect overlays, image grading, or OCR-driven slab interpretation
  - Live grader APIs, webhook callbacks, carrier sync, or automatic submission-state mutation
  - Autonomous grading decisions, predictive grading models, or automatic recommendation changes
  - Notification routing, staffing workflows, or task orchestration layered onto dashboard alerts

## P38-05 — Concentration risk modeling (2026-05-26)

- Architecture note: deterministic concentration snapshots, evidence rows, weighted factor rows, and append-safe history live in `docs/CONCENTRATION_RISK_ARCHITECTURE.md`. The lane translates current portfolio exposure into explicit concentration posture without mutating FMV, inventory, listings, or portfolios.
- Owner routes may generate and inspect concentration rows; `/ops/concentration-risk*` mirrors remain read-only with optional owner scoping.

### Deferred scope (beyond P38-05)

- Real character / creator attribution beyond the current `unknown` placeholder contract.
- Predictive diversification guidance, portfolio optimization, or AI/ML concentration scoring.
- Auto-rebalancing workflows, sell execution, or portfolio mutation driven by concentration posture.
- Cross-owner benchmarking, market-relative diversification ranks, or benchmark-index modeling.
- Trendline forecasting / scenario simulation beyond the current deterministic snapshot-and-history ledger.

## P37-09 — Grading reporting / production closeout (2026-05-26)

- Architecture note: deterministic grading closeout reporting plus final stabilization lives in `docs/GRADING_CLOSEOUT_ARCHITECTURE.md` (`GradingOperationalReportRun|File|Item`, UTF-8 CSV checksums, row-level lineage, replay-safe generation, owner vs `/ops/grading-reports` parity, deterministic filename rules).
- The closeout lane must remain read-only over the P37 grading stack. Report generation may describe candidate, economics, submission, reconciliation, recommendation, risk, dashboard, and grader-performance state, but it must never fix or mutate them.
- **Deferred scope (post-P37):**
  - Scan AI and image-based defect detection
  - Slab OCR and broader vision systems
  - Autonomous grading or automatic recommendation execution
  - Probabilistic ML, Monte Carlo simulation, or predictive grading models
  - Live grader API integrations, webhook sync, or automatic submission systems
  - Automatic FMV, pricing, liquidity, or inventory mutation from grading outputs
  - Background workers, websocket status streaming, or external BI sink automation unless replay/checksum invariants are preserved

## P38-01 — Portfolio registry & exposure engine (2026-05-27)

- Architecture note: deterministic portfolio grouping, exposure/allocation snapshots, evidence, lifecycle events, replay keys, checksums, and owner vs `/ops/portfolio*` separation are documented in `docs/PORTFOLIO_REGISTRY_ARCHITECTURE.md`. Engines are descriptive only — they never mutate inventory, FMV, listings, or sales ledgers automatically.
- SPA surfaces intentionally stay lightweight (dashboard summary cards, ops tables, inventory detail teaser). Character/creator exposure dimensions remain keyed as `unknown` until canonical attribution exists on inventory/issue graphs.

### Deferred scope (beyond P38-01 / explicitly not shipped)

| Track | Deferred item |
| --- | --- |
| Optimization | Automated duplicate rollup / merging across portfolios |
| Recommendations | Sell/hold guidance, acquisition advice, market timing |
| Predictive | ML portfolio strategy, forecasting, scenario simulation |
| Automation | Automated portfolio rebalancing or target allocation enforcement |
| Tax / accounting | Tax-aware optimization, wash-sale logic, accounting exports |
| AI | AI-driven portfolio construction or dynamic strategy |

## P38-02 — Duplicate & consolidation intelligence (2026-05-27)

- Architecture note: deterministic duplicate clustering, strength scoring, observational consolidation captions, append-safe history checkpoints, salted batch replay semantics (`generation_batch_checksum` salted with `{snapshot_date, replay_key}`) and deterministic supersede semantics for ACTIVE recommendations are documented in `docs/DUPLICATE_CONSOLIDATION_ARCHITECTURE.md`.
- Owner routes generate and summarize duplicate intelligence; `/ops/duplicate*` routes stay read-only and align with Portfolio ops scope controls (shared owner filtering contract). Engines never mutate FMV automatically, silently retarget portfolios, auto-list duplicates, touch sales ledgers for optimization, or perform autonomous liquidation.

### Deferred scope (beyond P38-02 / explicitly not shipped)

| Track | Deferred item |
| --- | --- |
| Execution | Automated selling, liquidation, marketplace auto-posting |
| Acquisition | Acquisition buy-list modeling, speculative arbitrage, timing advice |
| ML / stochastic | Probabilistic duplicate scoring or ML clustering |
| Tax / treasury | Capital gains/tax-aware disposal sequencing |
| Rebalancing | Autonomous trimming, mandate-based portfolio resizing |
| Continuous optimization | Duplicate-aware supply chain automation |

## P38-03 — Portfolio liquidity allocation engine (2026-05-27)

- Architecture note: deterministic portfolio-level liquidity rollups, bucket rows, evidence spine, append-only history, replay checksums, and owner vs `/ops/portfolio-liquidity*` parity are documented in `docs/PORTFOLIO_LIQUIDITY_ARCHITECTURE.md`. Generation consumes liquidity engine snapshots, FMV, sales lines, listings, latest allocation checksums, and convention assignments — strictly read-only toward inventory and FMV.
- SPA: dashboard summary card, Operations **Portfolio liquidity** panel (snapshots, buckets, evidence, history), inventory detail teaser for bucket + rollup pointers.

### Deferred scope (beyond P38-03 / explicitly not shipped)

| Track | Deferred item |
| --- | --- |
| Execution | Autonomous liquidation, auto-listing, or sell automation |
| Forecasting | Predictive liquidity forecasting, stochastic exit modeling |
| Rebalancing | Automated portfolio balancing or mandate enforcement |
| Tax / treasury | Tax-aware disposal sequencing or wash-sale optimization |
| Timing | Market timing, regime detection, momentum allocation |
| AI | ML / AI-driven allocation systems or hidden scoring |

## P38-04 — Portfolio recommendation engine (2026-05-27)

- Architecture note: deterministic portfolio recommendation snapshots, evidence rows, scenario rows, append-safe history, checksum replay semantics, and owner vs `/ops/portfolio-recommendation*` separation are documented in `docs/PORTFOLIO_RECOMMENDATION_ARCHITECTURE.md`. The engine is observational only and must not mutate inventory, FMV, portfolios, listings, or sales ledgers.
- UI remains intentionally lightweight: dashboard counts, ops tables, and inventory-detail teasers are read surfaces only. Any future execution workflow must be designed as a separate explicit system, not added implicitly to recommendation generation.

### Deferred scope (beyond P38-04 / explicitly not shipped)

| Track | Deferred item |
| --- | --- |
| Execution | Autonomous selling, auto-listing, brokerage integrations, or automatic liquidation |
| Predictive | Market timing, ML/AI recommendation models, hidden weights, Monte Carlo scenario generation |
| Rebalancing | Automatic portfolio rebalancing, mandate enforcement, or target-allocation execution |
| Tax / treasury | Tax-aware liquidation sequencing, wash-sale logic, treasury optimization |
| Automation | Background auto-refresh that silently changes strategic posture without explicit user initiation |
| Acquisition | Buy-list generation, acquisition guidance, or speculative arbitrage recommendations |

## P33 — Inventory Intelligence closeout (2026-05-24)

- Intelligence reads (risks, action center, timelines, duplication, run gaps, reconciliation summaries) remain **mutation-free** on the dedicated read paths.
- Portfolio FMV dashboards stay separate from deterministic intelligence panels; CSV/JSON snapshots omit FMV where schemas allow (`reports_export`).
- Extending intelligence or exports should preserve explicit tuple sort keys and regression tests rather than ad-hoc nondeterministic ordering.
- New caches or async mutation on intelligence/export code paths need an explicit design note plus tests for ordering, filters, and scope (owner vs ops).