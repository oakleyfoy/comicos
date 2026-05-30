# Technical debt log

Operational notes for intentional deferrals and known cleanup work. Entries should be actionable when someone has a maintenance window.

## P45 closeout summary

This section consolidates deferred work that remains intentionally outside the completed agent platform scope after P45-08 closeout.

### High operational impact

- Full-repo backend regressions remain time-consuming in local environments even though targeted P45 suites are stable.
- Web bundle size still emits a non-blocking build warning.
- Permission and readiness telemetry are deterministic and queryable, but external alert routing and continuous health monitoring remain deferred.

### Medium operational impact

- Real-time dashboard streaming and push-style execution updates remain deferred.
- Multi-tenant role layering beyond current owner/admin-style control remains future work.
- Large-scale query tuning for long-lived execution, recommendation, and analytics histories remains future optimization work.

### Low operational impact

- The readiness report is JSON-only in P45; export formats and richer operator presentation are deferred.
- Documentation remains phase-oriented in a few places for easier lookup, which intentionally duplicates some concepts.

### P45 deferred work by area

- Agent foundation: distributed execution scaling, worker pools, external execution engines.
- Workflow engine: visual workflow editing, distributed orchestration, realtime step streaming.
- Research and intelligence: forecasting, autonomous downstream action, external marketplace ingestion, ML ranking.
- Dashboard: realtime updates, richer drilldowns, long-horizon trend visualizations.
- Security: enterprise RBAC expansion, external SIEM/alert export, continuous policy drift detection.
- Analytics: scheduled snapshot generation, external observability sinks, fleet-scale retention tuning.

### P45 deferred work by severity

- Critical: none expected after closeout verification.
- Warning: build-size warning, long full-suite runtime, future scale/telemetry tuning.
- Info: richer export/report UX, realtime operator polish, additional enterprise controls.

## P40 closeout summary

This section consolidates the remaining non-blocking work across the completed P40 stack.

### High operational impact

- Replay and feed verification remain test-driven rather than continuously scheduled in production.
- Large regression runs are still expensive in local SQLite-backed environments.
- Web bundle size still triggers a non-blocking Rollup warning during build.
- Query-plan tuning and large-scale performance profiling remain future work.

### Medium operational impact

- External audit export destinations are deferred.
- Cloud-storage expansion for replay/feed artifacts remains a future enhancement.
- Batch / realtime orchestration remains deferred until the platform-wide automation phase.
- Additional monitoring, alerting, and background replay monitors remain deferred.

### Low operational impact

- Documentation is now consolidated, but some phase-specific closeout notes remain intentionally duplicated for ease of per-phase lookup.
- Optional-phase gaps are expected and surfaced explicitly; they are not defects unless required lineage is missing.

### P40 deferred work by phase

- P40-16: official authentication certification, counterfeit classification, restoration detection, external database checks, slab-label claims, customer-facing authenticity certificate, ML counterfeit detection.
- P41-01: realtime workers, distributed queues, websocket queue updates, scheduled orchestration, retry automation, queue autoscaling, worker pools, priority aging, distributed locks.
- P41-02: distributed worker clusters, realtime websocket runtime, autoscaling workers, Kubernetes orchestration, distributed locking, queue sharding, dynamic concurrency tuning, worker autoscaling, external execution engines.
- P41-03: distributed orchestration clusters, realtime orchestration, external event buses, workflow visual editors, dynamic workflow editing, orchestration autoscaling, external cron providers, distributed dependency locking.
- P41-04: distributed retry orchestration, randomized retry jitter, ML-driven retry optimization, automatic dead-letter replay, external recovery queues, distributed replay recovery, autoscaling retry workers.
- P41-05: distributed batch clusters, autoscaling maintenance workers, ML-driven partitioning, destructive cleanup automation, cloud-scale replay sweeps, external maintenance schedulers, realtime maintenance telemetry.
- P41-06: external email providers, SMS integrations, push notifications, realtime websockets, distributed alert routing, ML-driven alert prioritization, external notification brokers.
- P41-17: cross-scan batch feed generation, live streaming feed updates, richer charting, external export destinations, subscription workflows, artifact retention policies, workflow automation from feed events.
- P40-18: automated artifact repair, scheduled replay jobs, batch replay orchestration, cryptographic signing, external audit exports, replay diff visualization v2, background replay monitors, compliance-grade audit certification.
- P40-19: continuous hardening automation, performance regression tooling, production-scale query tuning, and future build warning elimination if warranted.

### P40 deferred work by severity

- Critical: none expected after the closeout verification sweep.
- Warning: build-size warning, expensive local regressions, optional-phase gaps in partial workflows.
- Info: documentation/visibility improvements, future automation polish, and cloud/storage evolution.

### P40 deferred work by operational impact

- Reliability: replay scheduling, hardening automation, batch replay orchestration.
- Scale: query tuning, large regression performance, storage expansion, cloud migration planning.
- Observability: monitoring, replay monitors, external audit exports.
- UX / ops workflow: richer charts, subscription workflows, automation helpers, replay diff UX.

## P40-16 — Authentication assistance layer (2026-05-27)

- Architecture note: deterministic authentication-support signals, identity consistency checks, metadata conflicts, lineage integrity, historical consistency summaries, review-required flags, and replay-safe manifests are documented in `docs/SCAN_AUTHENTICATION_ASSISTANCE_ARCHITECTURE.md`.
- This layer is review support only. It does not certify authenticity, detect restoration, assign grades, or mutate immutable upstream evidence.

### Deferred scope (beyond P40-16)

- Official authentication certification
- Counterfeit classification
- Restoration detection
- External database authentication checks
- Expert reviewer workflows
- Slab-label authentication claims
- Customer-facing authenticity certificate
- ML-based counterfeit detection

## P41-17 — Scan intelligence feed layer (2026-05-28)

- Architecture note: deterministic cross-system scan timeline aggregation, immutable feed events/issues/artifacts, replay-safe manifests, and owner/ops feed surfaces are documented in `docs/SCAN_INTELLIGENCE_FEED_ARCHITECTURE.md`.
- This layer is a chronology/orchestration surface only. It does not assign official grades, certify authenticity, estimate FMV, or mutate upstream ledgers.

### Deferred scope (beyond P41-17)

- P40-18 determinism / replay orchestration layer
- Cross-scan batch feed generation
- Live streaming / websocket feed updates
- Rich charting and timeline clustering
- External export destinations
- Feed subscription / notification workflows
- Artifact retention policies
- Reviewer assignment or workflow automation driven from feed events

## P41 closeout summary (2026-05-28)

P41 automation is feature-complete through P41-09 with P41-10 documentation and verification closeout. Consolidated deferred work below is **intentional**; it is not blocking single-deployment deterministic automation.

### By recommended future phase

| Future phase | Deferred capability |
| --- | --- |
| P42+ multi-tenant / dealer | Org-wide RBAC, dealer ops roles, shared automation visibility |
| Platform scale | Distributed queue scaling, queue sharding, worker autoscaling |
| Observability | Real-time telemetry, websocket feeds, advanced ops observability |
| Integrations | External email/SMS/push providers, external notification brokers, external cron |
| UX / authoring | Workflow visual editor, visual rule builders |
| Operations | Destructive cleanup tooling, enterprise automation controls |
| Cloud / replay at scale | Cloud-scale replay sweeps, artifact retention automation |

### By severity

| Severity | Items |
| --- | --- |
| Critical | None for P41 core automation after focused suite pass |
| Warning | Full-repo pytest failures outside P41; long local regression time; web bundle size warning |
| Info | Cloud storage backends for artifacts, richer analytics (non-ML), documentation duplication for per-phase lookup |

### By operational impact

| Impact | Deferred items |
| --- | --- |
| Reliability at scale | Distributed workers, sharding, external recovery queues |
| Observability | Realtime streams, ML anomaly/prioritization systems |
| Operator efficiency | Visual editors, destructive cleanup, autoscaling admin |
| Compliance / messaging | External providers, enterprise controls, cloud telemetry |

### Consolidated P41 deferred backlog (all phases)

- Distributed queue scaling and queue sharding
- Worker autoscaling and distributed worker clusters
- Real-time telemetry and websocket queue/runtime updates
- External notification providers (email, SMS, push) and brokers
- Workflow visual editor and dynamic workflow editing
- Destructive cleanup tooling (purge queue, delete dead letter, force replay overwrite)
- Cloud-scale replay sweeps and scheduled maintenance at fleet scale
- Advanced ops observability and ML-driven anomaly detection
- Enterprise automation controls and adaptive policies
- Predictive analytics / ML forecasting (P41-09 explicit non-goals)

Per-phase architecture notes remain in sections P41-01 through P41-09 below for detailed context.

## P41-10 — Closeout / docs (2026-05-28)

- Index and closeout docs: `docs/P41_ARCHITECTURE_INDEX.md`, dependency graph, lifecycle, operations guide, API reference, storage, determinism guarantees, production readiness, hardening report.
- No new automation features in this phase.

### Deferred scope (unchanged — see consolidated backlog above)

Documentation-only closeout; deferrals listed in **P41 closeout summary**.

## P41-01 — Automation queue foundation (2026-05-28)

- Architecture note: deterministic job ledger ordering, reservation-safe queue selection, append-only job history, immutable payload snapshots, dependency edges, and replay-safe artifacts are documented in `docs/P41_AUTOMATION_QUEUE_ARCHITECTURE.md`.
- This layer is queue-foundation only. It does not execute jobs, schedule jobs, open realtime streams, or add hidden retry logic.

### Deferred scope (beyond P41-01)

- Realtime workers
- Distributed queues
- Websocket queue updates
- Scheduled orchestration
- Retry automation
- Queue autoscaling
- Worker pools
- Priority aging
- Distributed locks

## P41-02 — Worker runtime engine (2026-05-28)

- Architecture note: deterministic worker registration, lease ownership, heartbeat visibility, execution lineage, append-only runtime history, and replay-safe execution checksums are documented in `docs/P41_WORKER_RUNTIME_ARCHITECTURE.md`.
- This layer is runtime-only. It does not implement scheduling, distributed worker orchestration, realtime sockets, or autoscaling.

### Deferred scope (beyond P41-02)

- Distributed worker clusters
- Realtime websocket runtime
- Autoscaling workers
- Kubernetes orchestration
- Distributed locking
- Queue sharding
- Dynamic concurrency tuning
- Worker autoscaling
- External execution engines

## P41-03 — Workflow scheduling / trigger orchestration (2026-05-28)

- Architecture note: deterministic schedule activation, immutable trigger lineage, dependency-aware workflow sequencing, append-only execution history, and replay-safe orchestration manifests are documented in `docs/P41_WORKFLOW_SCHEDULING_ARCHITECTURE.md`.
- This layer is orchestration-only. It does not add distributed orchestration, realtime sockets, external event buses, or hidden retries.

### Deferred scope (beyond P41-03)

- Distributed orchestration clusters
- Realtime orchestration
- External event buses
- Workflow visual editors
- Dynamic workflow editing
- Orchestration autoscaling
- External cron providers
- Distributed dependency locking

## P41-04 — Retry / failure / dead-letter / replay recovery (2026-05-28)

- Architecture note: deterministic retry policies, replay-safe recovery runs, dead-letter lineage, stale execution recovery, and append-only failure history are documented in `docs/P41_RECOVERY_ARCHITECTURE.md`.
- This layer is recovery-only. It does not add distributed retry systems, random jitter, autoscaling workers, or external recovery queues.

### Deferred scope (beyond P41-04)

- Distributed retry orchestration
- Randomized retry jitter
- ML-driven retry optimization
- Automatic dead-letter replay
- External recovery queues
- Distributed replay recovery
- Autoscaling retry workers

## P41-05 — Batch processing / maintenance jobs (2026-05-28)

- Architecture note: deterministic batch partitioning, replay-safe maintenance lineage, append-only chunk/history ledgers, integrity audit visibility, and immutable batch artifacts are documented in `docs/P41_BATCH_PROCESSING_ARCHITECTURE.md`.
- This layer is batch/maintenance only. It does not add distributed compute, autoscaling, external schedulers, or destructive cleanup.

### Deferred scope (beyond P41-05)

- Distributed batch clusters
- Autoscaling maintenance workers
- ML-driven partitioning
- Destructive cleanup automation
- Cloud-scale replay sweeps
- External maintenance schedulers
- Realtime maintenance telemetry

## P41-06 — Notifications / alerting / operational messaging (2026-05-28)

- Architecture note: deterministic notification ledger, delivery lineage, alert escalation, template resolution, preference evaluation, and replay-safe manifests are documented in `docs/P41_NOTIFICATION_ARCHITECTURE.md`.
- This layer is messaging-only. It does not add external email/SMS providers, push infrastructure, or websocket delivery.

### Deferred scope (beyond P41-06)

- External email providers
- SMS integrations
- Push notifications
- Realtime websockets
- Distributed alert routing
- ML-driven alert prioritization
- External notification brokers

## P41-07 — Ops automation dashboard / admin controls (2026-05-28)

- Architecture note: unified ops snapshots, deterministic metrics, integrity audits, safe admin controls, artifact manifests, and append-only history are documented in `docs/P41_OPS_DASHBOARD_ARCHITECTURE.md`.
- This layer is visibility and safe control only. It does not add destructive admin tooling, realtime websockets, or distributed infrastructure management.

### Deferred scope (beyond P41-07)

- Destructive admin tooling
- Realtime telemetry
- Distributed ops coordination
- Autoscaling admin systems
- ML-driven anomaly detection
- External observability systems
- Cloud-scale operational telemetry

## P41-08 — Automation rules engine (2026-05-28)

- Architecture note: deterministic rule creation, immutable versioning, replay-safe evaluation lineage, ordered action execution, and rules-engine non-goals are documented in `docs/P41_RULES_ENGINE_ARCHITECTURE.md`.
- This layer is deterministic policy infrastructure only. It does not add ML-generated rules, realtime streaming evaluation, distributed rule clusters, or arbitrary scripting.

### Deferred scope (beyond P41-08)

- ML-driven rule systems
- Realtime stream processing
- Distributed rule clusters
- Arbitrary scripting engines
- Visual rule builders
- Cloud-scale rule orchestration
- Adaptive automation policies

## P41-09 — Automation analytics / intelligence layer (2026-05-28)

- Architecture note: deterministic analytics aggregation, replay-safe trends, historical comparisons, immutable snapshots, and analytics non-goals are documented in `docs/P41_ANALYTICS_ARCHITECTURE.md`.
- This layer is deterministic operational intelligence only. It does not add predictive AI, ML forecasting, realtime streaming analytics, distributed analytics clusters, or adaptive intelligence.

### Deferred scope (beyond P41-09)

- Predictive AI analytics
- ML forecasting
- Realtime analytics streaming
- Distributed analytics clusters
- Adaptive operational intelligence
- Cloud-scale telemetry systems
- Anomaly prediction systems

## P40-18 — Determinism / replay layer (2026-05-28)

- Architecture note: deterministic replay verification, checksum audits, lineage validation, immutable artifact checks, discrepancy persistence, and ops diagnostics are documented in `docs/SCAN_REPLAY_ARCHITECTURE.md`.
- This layer is verification-only. It does not create new intelligence, assign grades, certify authenticity, estimate FMV, or mutate upstream ledgers.

### Deferred scope (beyond P40-18)

- Automated artifact repair
- Scheduled replay jobs
- Batch replay orchestration
- Cryptographic signing
- External audit exports
- Replay diff visualization v2
- Background replay monitors
- Compliance-grade audit certification

## P40-19 — Tests / hardening sweep (2026-05-28)

- Hardening report: deterministic validation sweep, replay stability checks, isolation checks, envelope consistency checks, and production-readiness notes are documented in `docs/P40_HARDENING_REPORT.md`.
- This sweep is validation-only. It does not add features or rewrite completed phase behavior.

### Remaining non-blocking limitations

- Full regression runs are still expensive relative to the focused phase tests and may take significant time in local SQLite-backed test environments.
- The web bundle remains large enough to trigger a Rollup chunk-size warning during build, though the build succeeds.
- Hardening diagnostics remain test-driven rather than continuously scheduled.
- Artifact exports are deterministic and append-only, but external export destinations remain deferred.
- Replay and feed verification are deterministic, but production-scale benchmarking and query-plan tuning remain future work.

## P40-15 — Historical comparison engine (2026-05-27)

- Architecture note: deterministic scan-history comparison, prior-scan selection, evidence deltas, geometry normalization, reliability issues, and replay-safe manifests are documented in `docs/SCAN_HISTORICAL_COMPARISON_ARCHITECTURE.md`.
- This layer compares immutable scan history only. It does not assign grades, estimate FMV, or mutate historical records.

### Deferred scope (beyond P40-15)

- Multi-angle scan comparison
- Slabbed/raw transformation comparison
- Restoration inference
- Value-change modeling
- AI-based change interpretation
- Automated rescan recommendations
- Customer-facing historical condition reports
- Batch comparison jobs

## P40-14 — Review workspace (2026-05-27)

- Architecture note: deterministic review sessions, decisions, notes, evidence actions, completion snapshots, append-only history, and replay-safe lineage are documented in `docs/SCAN_REVIEW_WORKSPACE_ARCHITECTURE.md`.
- This layer remains human-review only. It records reviewer actions over immutable evidence without assigning official grades or mutating upstream artifacts.

### Deferred scope (beyond P40-14)

- Multi-reviewer approvals
- Customer-facing review reports
- Official certification workflow
- Slab-label workflow
- Role-based reviewer permissions
- Grading override audit UI
- Reviewer assignment queues
- Review SLA automation

## P40-13 — Visual evidence system (2026-05-27)

- Architecture note: deterministic evidence packages, annotation overlays, review packet exports, append-only artifacts, and replay-safe lineage are documented in `docs/SCAN_VISUAL_EVIDENCE_ARCHITECTURE.md`.
- This layer packages existing upstream evidence only. It does not detect new defects, assign grades, or alter source images.

### Deferred scope (beyond P40-13)

- PDF review packet export
- Human review annotations
- Customer-facing report generation
- Official grading certificate views
- Slab-label integration
- AI narrative summaries
- Multi-scan comparison overlays
- Authentication presentation packages (full UI)

## P40-12 — Grading assistance engine (2026-05-27)

- Architecture note: deterministic support-band mapping, category pressure summaries, review-required flags, rubric versioning, append-only artifacts, and replay-safe lineage are documented in `docs/SCAN_GRADING_ASSISTANCE_ARCHITECTURE.md`.
- This layer remains assistance-only. It provides support ranges without assigning an official grade, guaranteeing certification outcomes, pricing condition, or replacing human review.

### Deferred scope (beyond P40-12)

- Official grade assignment
- PSA outcome prediction
- ML grading models
- Human review workflow
- Certification workflow
- Restoration determination
- FMV/ROI grading coupling
- Slab label generation
- Marketplace valuation integration

## P40-11 — Defect aggregation engine (2026-05-27)

- Architecture note: deterministic cross-detector evidence loading, cluster formation, condition-region summaries, append-only artifacts, and replay-safe lineage are documented in `docs/SCAN_DEFECT_AGGREGATION_ARCHITECTURE.md`.
- This layer remains evidence-only. It consolidates prior detector output without assigning grades, pricing impact, restoration labels, or final condition judgments.

### Deferred scope (beyond P40-11)

- Grading inference
- Market-value modeling
- AI evidence weighting
- Restoration classification
- ML condition scoring
- Probabilistic grading models
- Cross-scan comparative grading

## P40-10 — Structural damage detection (2026-05-27)

- Architecture note: deterministic structural-region isolation, geometry/anomaly segmentation, measurements, append-only artifacts, and replay-safe lineage are documented in `docs/SCAN_STRUCTURAL_DAMAGE_ARCHITECTURE.md`.
- This layer remains evidence-only. It detects probable structural deformation and integrity anomalies without assigning grades, pricing impact, restoration labels, or final condition judgments.

### Deferred scope (beyond P40-10)

- AI structural reconstruction
- Restoration detection
- Staple rust analysis
- Page-stack deformation analysis
- Grade-impact modeling
- ML-based structural classification
- Advanced paper physics modeling

## P40-08 — Corner / edge wear detection (2026-05-27)

- Architecture note: deterministic corner/edge region isolation, wear segmentation, measurements, append-only artifacts, and replay-safe lineage are documented in `docs/SCAN_CORNER_EDGE_ARCHITECTURE.md`.
- This layer remains evidence-only. It detects probable corner rounding and edge wear without assigning grades, pricing impact, restoration labels, or final condition judgments.

### Deferred scope (beyond P40-08)

- AI contour reconstruction
- Restoration detection
- Paper-fiber analysis
- Grade-impact modeling
- ML-based wear classification
- Microscopic edge analysis

## P40-09 — Surface defect detection (2026-05-27)

- Architecture note: deterministic surface-region isolation, surface anomaly segmentation, measurements, append-only artifacts, and replay-safe lineage are documented in `docs/SCAN_SURFACE_DEFECT_ARCHITECTURE.md`.
- This layer remains evidence-only. It detects probable surface-level interruptions without assigning grades, pricing impact, restoration labels, or final condition judgments.

### Deferred scope (beyond P40-09)

- AI surface segmentation
- Restoration detection
- Ink restoration analysis
- Paper-fiber analysis
- Grade-impact modeling
- ML-based surface classification
- Microscopic surface analysis
- Multi-angle gloss / reflection analysis

## P40-07 — Spine tick detection (2026-05-27)

- Architecture note: deterministic spine-region isolation, tick segmentation, measurements, append-only spine artifacts, and replay-safe lineage are documented in `docs/SCAN_SPINE_TICK_ARCHITECTURE.md`.
- This layer remains evidence-only. It detects probable spine stress ticks without assigning grades, pricing impact, restoration labels, or final condition judgments.

### Deferred scope (beyond P40-07)

- AI spine segmentation
- Restoration detection
- Print-break differentiation
- Advanced paper-fiber analysis
- Grade impact modeling
- ML-based spine classification
- Microscopic crease reconstruction

## P40-06 — Defect detection foundation (2026-05-27)

- Architecture note: deterministic condition regions, scan-quality gates, baseline evidence anchors, append-only defect artifacts, and replay-safe lineage are documented in `docs/SCAN_DEFECT_FOUNDATION_ARCHITECTURE.md`.
- This layer remains foundation-only. It creates provisional condition evidence without assigning grades, naming final defects, pricing condition impact, or using AI restoration.

### Deferred scope (beyond P40-06)

- Structural damage classification
- AI defect segmentation
- Grade-impact modeling
- Restoration detection
- ML-based visual evidence scoring
- Defect-aware valuation

## P40-03 — Boundary mapping / cover detect (2026-05-27)

- Architecture note: deterministic cover-area geometry, immutable normalized inputs, overlay artifacts, and replay-safe checksum lineage are documented in `docs/SCAN_BOUNDARY_MAPPING_ARCHITECTURE.md`.
- This layer remains spatial detection only. It maps cover boundaries and scanner background metadata without OCR, grading, defect analysis, or AI cover identification.

### Deferred scope (beyond P40-03)

- AI-based cover segmentation
- Advanced contour reconstruction
- ML-based background removal
- Title/logo-aware boundary detection
- Defect-aware boundary adjustment
- Automated cover matching
- OCR-assisted boundary refinement

## P40-04 — OCR intelligence layer (2026-05-27)

- Architecture note: deterministic OCR extraction, provisional candidate generation, immutable upstream lineage, and append-only OCR history are documented in `docs/SCAN_OCR_ARCHITECTURE.md`.
- This layer remains OCR-only. It extracts text regions and provisional metadata candidates without comic reconciliation, grading, defect analysis, or AI completion.

### Deferred scope (beyond P40-04)

- AI semantic OCR correction
- External comic reconciliation
- Fuzzy matching intelligence
- Multilingual OCR
- ML OCR enhancement
- OCR-assisted grading
- Semantic title inference
- AI completion / reconstruction

## P40-05 — OCR reconciliation / matching (2026-05-27)

- Architecture note: deterministic canonical comic identity resolution, local dataset versioning, ranked candidate persistence, and replay-safe manifests are documented in `docs/SCAN_RECONCILIATION_ARCHITECTURE.md`.
- This layer remains reconciliation-only. It resolves OCR candidates against local canonical comic reference data without grading, defect analysis, pricing, external APIs, or AI speculation.

### Deferred scope (beyond P40-05)

- External marketplace reconciliation
- AI semantic matching
- Fuzzy ML title inference
- Cross-publisher probabilistic matching
- Multilingual reconciliation
- Collector-submitted alias learning
- AI confidence boosting
- Semantic storyline matching

## P40-02 — Image normalization engine (2026-05-27)

- Architecture note: deterministic preprocessing, immutable originals, artifact lineage, checksum propagation, and issue tracking are documented in `docs/SCAN_NORMALIZATION_ARCHITECTURE.md`.
- This layer remains preprocessing-only. It corrects geometry and scanner variance without performing OCR, grading, defect analysis, or any AI enhancement.

### Deferred scope (beyond P40-02)

- AI enhancement
- Super resolution
- Defect-aware restoration
- Advanced perspective reconstruction
- ML image cleanup
- Scan denoising AI

## P40-01 — Scan ingestion layer (2026-05-27)

- Architecture note: deterministic visual intake, immutable originals, append-only ingest events, storage-path abstraction, and duplicate detection are documented in `docs/SCAN_INGESTION_ARCHITECTURE.md`.
- This layer remains ingestion-only. It records images, metadata, variants, and upload sessions without performing OCR, grading, or any scan intelligence.

### Deferred scope (beyond P40-01)

- Live scanner streaming
- OCR processing
- Defect analysis
- AI scan interpretation
- Cloud storage optimization
- ML-based image deduplication

## P39-08 — Market Intelligence Dashboard UI integration (2026-05-26)

- Architecture note: owner dashboard + ops diagnostics are documented in `docs/MARKET_DASHBOARD_UI_ARCHITECTURE.md`. The UI consumes only P39-07 envelopes and must not add intelligence or bypass standard list/detail shapes.
- Operational drill-down remains in `OperationsPage`; dashboard panels are presentation + orchestration only.

### Deferred scope (beyond P39-08 UI layer)

- Real-time dashboard streaming via websockets or push channels
- Live market tick ingestion into the dashboard surface
- AI-driven UI personalization, adaptive layout, or speculative panel ordering
- Predictive UI ordering based on model attention or user behavior
- Animated intelligence graphs beyond simple static histograms
- Cross-user dashboard synchronization or shared live cursors

## P39-09 — Market Intelligence Feed system (2026-05-26)

- Architecture note: deterministic append-only feed, replay, and owner/ops read models are documented in `docs/MARKET_FEED_ARCHITECTURE.md`. The feed records meaningful P39 outputs only; it must not invent new intelligence, mutate upstream P39 rows, or bypass the standard market v1 envelope.
- Dashboard and ops feed surfaces remain observational. Inventory detail only shows a compact latest-event teaser.

### Deferred scope (beyond P39-09 feed layer)

- Real-time feed streaming / websocket fan-out
- Live notification delivery or push subscriptions
- Cross-user shared cursors or collaborative feed state
- Predictive event clustering or AI interpretation of the feed
- Non-deterministic ranking or prioritization of feed rows
- Automatic write-back from feed replay into upstream P39 sources


## P39-03 — Market scoring engine (2026-05-26)

- Architecture note: deterministic acquisition ranking, evidence, snapshots, and append-safe history live in `docs/MARKET_SCORING_ARCHITECTURE.md`. The scorer must remain a pure reader over P39-02 normalized candidates and persisted P38 context.
- UI surfaces stay lightweight: dashboard summary cards, ops drill-down tables, and inventory detail teasers only. Do not expand these into autonomous workflow controls without a separate product decision.

### Deferred scope (beyond P39-03)

- ML ranking models or probabilistic weighting
- Predictive pricing systems or real-time market forecasting
- External signal weighting, live marketplace feeds, or third-party ranking inputs
- Autonomous recommendation tuning or auto-generated buy actions
- Caching layers for larger owner datasets once score volume justifies dedicated materialized read paths
- Real-time websocket score feeds instead of explicit read-only snapshot refreshes

## P39-04 — Market signal classification system (2026-05-26)

- Architecture note: deterministic signal mapping, evidence, snapshots, and append-safe history live in `docs/MARKET_SIGNAL_ARCHITECTURE.md`. The signal system must remain a pure interpreter over persisted P39-03 score rows and score evidence.
- UI surfaces remain observational only: dashboard counts, ops drill-down, and a single inventory signal teaser. Do not expand this layer into action queues or autonomous recommendation workflows without a separate product decision.

### Deferred scope (beyond P39-04)

- ML-based signal classification
- Predictive signal evolution or trend forecasting
- Real-time signal streaming / websocket fan-out
- External sentiment signals or marketplace commentary feeds
- AI-driven signal weighting or adaptive signal priority tuning

## P39-05 — Market opportunity snapshot aggregation (2026-05-26)

- Architecture note: deterministic rollup lives in `docs/MARKET_OPPORTUNITY_ARCHITECTURE.md`. Opportunities are pure aggregations over persisted scoring + signal snapshots; rerunning generation must remain idempotent for identical inputs.

### Deferred scope (beyond P39-05)

- Predictive opportunity ranking
- AI investment optimization
- Automated buying systems
- Real-time market feeds
- External pricing APIs
- ML opportunity scoring

## P39-06 — Portfolio ↔ market coupling engine (2026-05-26)

- Architecture note: deterministic bridging layer lives in `docs/MARKET_PORTFOLIO_COUPLING_ARCHITECTURE.md`. Coupling must remain strictly read-only versus P38 registry context and persisted P39-05 opportunity payloads; regenerated snapshots replay idempotently on identical checksum payloads.
- UI surfaces expose dashboard coupling metrics, coupled inventory teasers tied to portfolio items, and ops drill-down edges plus checksum parity — no execution knobs.

### Deferred scope (beyond P39-06)

- AI portfolio matching
- Predictive coupling
- Autonomous recommendations
- External graph learning
- ML similarity matching
- Real-time market graph optimization

## P39-07 — Market API exposure & standardization (2026-05-26)

- Architecture note: unified envelope, versioning, pagination, scoped errors, and ops read-only **`v1`** surface are documented in `docs/MARKET_API_STANDARDIZATION_ARCHITECTURE.md`. Legacy unversioned P39 URLs remain unchanged; the SPA consumes **`/api/v1/market`** through `requestMarketV1`.
- Deferred scope (beyond P39-07 API-only work):

  - GraphQL layer
  - Real-time streaming APIs or websocket feeds
  - External API federation
  - API auto-generation (OpenAPI client codegen as the single source of truth)
  - AI-driven endpoint budgeting or speculative response shaping

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
  - Operations market workspace: `#market-ops-quicknav` jump links require matching `id` anchors on each panel; `#listing-export-ops` accompanies listing registry/export surfaces — extend the list when new market ops sections ship (including `#portfolio-liquidity-ops` for P38-03 rollup tables and `#market-portfolio-coupling-ops` for P39-06 coupling inspection).

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

## P38-06 — Acquisition priority engine (2026-05-26)

- Architecture note: deterministic acquisition snapshots, evidence rows, scenario rows, and append-safe history live in `docs/ACQUISITION_PRIORITY_ARCHITECTURE.md`. The lane translates existing owner inventory into explicit expansion and gap-analysis opportunities using only persisted portfolio, concentration, liquidity, duplicate, grading, recommendation, listing, and sales ledgers.
- Owner routes may generate and inspect acquisition rows; `/ops/acquisition-priorities*` mirrors remain read-only with optional owner scoping.

### Deferred scope (beyond P38-06)

- Autonomous buying, brokerage integrations, auction automation, or execution tooling.
- Predictive market timing, probabilistic acquisition forecasting, or AI portfolio management.
- External candidate-universe generation that depends on live market catalog ingest beyond the owner’s current issue graph.
- Automatic portfolio mutation, FMV mutation, or inventory mutation driven by acquisition signals.
- Marketplace-specific sourcing bots, watchlists, or auction-sniping workflows.

## P38-07 — Portfolio strategy dashboard (2026-05-26)

- Architecture note: deterministic strategy snapshots, metrics, observational alerts, and append-safe feed events live in `docs/PORTFOLIO_STRATEGY_DASHBOARD_ARCHITECTURE.md`. The lane consolidates existing P38 ledgers only; it must never become an execution engine.

### Deferred scope (beyond P38-07)

- Autonomous portfolio balancing, auto-rebalancing, or automatic liquidation workflows.
- Predictive portfolio strategy, market timing, probabilistic scoring, or AI portfolio management.
- Tax-aware optimization, wash-sale handling, or accounting-style optimization overlays.
- Brokerage integrations, auction execution, sourcing bots, or automatic acquisition workflows.
- Real-time push dashboards, websocket alerting, staffing/task orchestration, or notification routing layered onto strategy alerts.
- Any hidden mutation of portfolios, FMV, listings, recommendations, or inventory based on strategy dashboard outputs.

## P38-08 — Portfolio strategy dashboard stabilization (2026-05-26)

- Performance follow-up: if owner-wide strategy generation grows materially, move more dependency selection / dedupe work to targeted SQL projections and add explicit query-budget checks around multi-engine aggregation.
- Caching follow-up: introduce an opt-in checksum-aware cache layer only if it preserves replay semantics and never hides upstream ledger changes.
- Delivery follow-up: websocket / realtime strategy feed remains deferred until the product defines replay-safe streaming contracts.
- Intelligence follow-up: predictive portfolio intelligence remains explicitly deferred beyond P38; stabilization does not authorize ML, forecasting, or autonomous actions.

## P39-01 — Market ingestion foundation (2026-05-26)

- Normalization engine remains deferred to P39-02; P39-01 only preserves raw records plus lightweight candidate scaffolding.
- Scoring/ranking layers remain deferred to P39-03+; ingestion must stay intelligence-free.
- External enrichment, predictive pricing, ML models, and market-fit intelligence remain out of scope for the foundation layer.
- Live marketplace automation, webhook ingestion, and scheduled background imports remain deferred until replay-safe source contracts are defined.

## P39-02 — Market normalization engine (2026-05-26)

- Architecture note: deterministic canonicalization lanes, deterministic `canonical_key`, replay-safe `run_checksum`, append-only normalization issues/events, and strict non-mutation of ingestion tables are documented in `docs/MARKET_NORMALIZATION_ARCHITECTURE.md`.
- **Deferred beyond P39-02:**
  - ML-style entity resolution, fuzzy clustering, probabilistic completeness fills
  - AI title inference / auto-correction pipelines
  - External metadata enrichment APIs or live marketplace lookups
  - Predictive normalization (guessing publishers, speculative variant labels, probabilistic grading hints)
  - Automatic liquidity hints or grade-potential heuristics (fields stay null until deterministic rules ship)
  - Rewriting ingestion/raw rows to coerce quality

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