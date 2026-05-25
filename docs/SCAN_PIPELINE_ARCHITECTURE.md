# Scan pipeline and bulk ingest architecture (P34)

This document captures the **intent and boundaries** of ComicOS scan pipeline surfaces that shipped with P34. It is authoritative for ops and engineering handoff until a future redesign.

## Goals

1. Provide **explicit, deterministic** workflows for Fujitsu-style **bulk ingest** into scan sessions, physical **receiving**, **scan QA**, **queue routing**, **high-resolution review** (EPSON-class capture lane), replay/recovery, and consolidated **ops dashboards**.
2. Maintain **tenant isolation**: owner endpoints scope by `owner_user_id`; `/ops/*` surfaces require configured ops admins and read across owners where noted.
3. **Never infer hardware integration**: presets and manifests describe capture intent only; ComicOS does not ship scanner drivers.

## Workflow boundaries

### Fujitsu bulk ingest (`session_type=bulk_ingest`)

**Purpose.** Accept feeder-style multipart uploads (JPEG/PNG/WebP/GIF/TIFF) into `scan_session_item` rows, compute SHA256 and dimensions where decodable, and attach optional `inventory_copy_id` linkage that may create **`CoverImage`** rows in **processing pending** — without touching OCR pipelines.

**Non-goals.**

- Automatic OCR enqueue from ingest completion.
- Trusting filenames as identity (dup filename/dup hash rollups surface ambiguity only).

**Reliability.**

- Individual corrupt bytes must produce a **failed** item row without aborting unrelated slots in the same batch (see ingest tests).

### Physical intake (`physical_intake` projections)

**Purpose.** Derived **deterministic buckets** (`released_not_received`, `received_pending_scan`, etc.) drive receiving visibility and dashboards.

**Explicit mutations.**

- `POST /inventory/{id}/mark-received` updates receipt timestamps/status.
- Optional `POST /physical-intake/create-scan-session` creates an **`intake_receiving`** session **only after** explicit eligibility checks (released/received semantics — **never** implicitly on mark-received).

### Epson / high-resolution review lane (`HighResReviewRequest`)

**Purpose.** Escalation queue for supplemental **high-resolution** captures (distinct cover rows). Owners open requests deliberately; linkage and attach-scan flows persist rows only — they do **not** auto-complete OCR or reconcile metadata.

### Scan QA (`run-qa`)

**Purpose.** Persisted **signals-only** snapshot per session item (`ScanQaResult`), written exclusively via **`POST /scan-sessions/{id}/run-qa`** (and ops-safe read mirrors).

**Classification** is deterministic from ingest state, cover processing state, OCR quality probes (where present), and duplicate/hash context — **not** heuristic “fixups”.

### Queue routing recommendations (`generate-routing`)

**Purpose.** Persist `QueueRoutingRecommendation` rows reflecting deterministic recommendation types (**recommend\_ocr**, **recommend\_high\_res\_review**, **recommend\_rescan**, etc.) for UI and dashboards.

**Critical boundary.** Persisting routing does **not** enqueue OCR jobs. OCR runs only via **explicit inventory/cover OCR endpoints or UI buttons** wired to documented APIs.

### Scan-pipeline replay / recovery (`ScanPipelineReplayRun`)

**Purpose.** Book **comparison-oriented** ledger runs across ingest/QA/routing deltas for operators. Replay execution must **isolate per item failures** — one bad row must not silently discard the ledger for other items.

Replay must **never** enqueue OCR, repair ingest rows, mutate canonical/metadata, or perform destructive cleanup as a side-effect of read/compare paths.

### Scanner profiles

**Purpose.** Owner-scoped presets (dpi, recommended use, TIFF defaults, etc.). Sessions may reference `scanner_profile_id` and MUST retain **`scanner_profile_snapshot`** JSON **after profile deletion**, with FK optionally nulled (`test_delete_profile_sets_session_fk_null_preserves_snapshot`).

### Bulk ingest dashboards

**Endpoints.**

- Owner: `GET /scan-pipeline-dashboard`, `/scan-pipeline-dashboard/summary`
- Ops fleet: `GET /ops/scan-pipeline-dashboard`, `/ops/scan-pipeline-dashboard/summary`
- Compatibility: Owner `GET /scan-sessions/dashboard` (sessions tables only).

These reads aggregate SQL counts/joins — **no scan intelligence**, OCR enqueue, or metadata mutations.

### Scan-session lifecycle (`pending` → … → terminals)

Controlled exclusively through documented POST endpoints (**start**, **pause**, **cancel**, **complete**). Completed/cancelled sessions reject further multipart ingest batches with safe `400`-class errors rather than ambiguous success.

## Technology constraints (hard)

| Constraint | Applies to |
| --- | --- |
| Deterministic ordering for list APIs | Prefer stable tuple sorts (`updated_at DESC`, surrogate `id DESC`, sequence index, etc.) wherever pagination exposes partial windows. |
| No automatic OCR | Ingest, QA, routing persistence, dashboards, replay read paths. |
| No automatic metadata/canonical mutation | Same surfaces unless an explicitly named human/ops reconciliation endpoint says otherwise — **not** covered here. |
| No scanner/driver integration | All “Fujitsu” / “Epson” wording is operational vocabulary for capture tiers, not device SDKs. |
| Explicit-only receiving → scan bridging | Physical intake summaries never auto-call create-scan-session. |

## Operational vocabulary

| Term | Meaning in ComicOS |
| --- | --- |
| Fujitsu ingest | Bulk scan session multipart ingest semantics (professional sheet-fed feeder workflow style). |
| Epson high-res | Human-facing label for supplementary high-resolution capture / review escalation — not Epson SDK integration. |
| QA snapshot | Persisted `ScanQaResult` ledger after pressing **Run QA** — not OCR. |
| Routing snapshot | Persisted routing rows after **Generate routing** — not OCR. |

## UI mapping (owner)

| Concern | Primary surface |
| --- | --- |
| Multipart ingest, QA filters, routing row actions (`Queue OCR`) | `/scan-sessions` |
| Receiving placeholders & intake counts | `/dashboard` anchored sections |
| Preset CRUD | `/settings/scanner-profiles` |

## Verification references

Representative regression tests include:

| Area | Tests |
| --- | --- |
| Corrupt + valid batch survives | `test_scan_session_ingest.py::test_ingest_corrupt_then_valid_keeps_batch` |
| Idempotent ingest / duplicate hashes | Same module (`test_duplicate_sha256_same_source_filename_skips_second_ingest`, etc.) |
| No OCR enqueue on ingest-linked cover | `test_cover_created_with_inventory_keeps_processing_pending_without_ocr_enqueue` |
| Receiving isolation | `test_physical_intake.py::test_mark_received_requires_explicit_endpoint` |
| Intake-only session guards | `test_create_intake_scan_session_from_received_only` |
| QA / routing OCR guardrails | `test_scan_qa.py`, `test_scan_pipeline_dashboard.py`, `test_scan_pipeline_replays.py` |
| Profile snapshot survives delete | `test_scanner_profiles.py::test_delete_profile_sets_session_fk_null_preserves_snapshot` |
| Closed-out API uniqueness & routing guards | `apps/api/tests/test_scan_pipeline_closeout.py` |

## Extension guidance

Adding new classifications, routing types, dashboards, or cross-session intelligence requires:

1. A **persisted ledger** migration if it must survive recomputation drift.
2. Tests proving **no OCR enqueue hooks** slipped into mutation-free services.
3. Updates to **this document** describing new explicit user actions versus derived projections.
