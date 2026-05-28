# Scan intelligence feed architecture

P41-17 adds a deterministic scan intelligence feed layer that aggregates immutable scan-system outputs into a replay-safe chronology for both owners and ops.

## Goals

- Build a single append-only timeline for scan activity across ingestion, normalization, OCR, reconciliation, detectors, aggregation, grading assistance, visual evidence, review, historical comparison, authentication, and feed-level ops/system signals.
- Preserve deterministic replay so identical upstream inputs produce the same `feed_checksum`.
- Keep upstream ledgers immutable. The feed reads persisted rows only and never writes back to prior systems.
- Surface the same underlying feed through owner-facing and ops-facing scan v1 endpoints and matching web UI.

## Core ledger

The layer persists five new tables:

- `scan_intelligence_feed_runs`
- `scan_intelligence_feed_events`
- `scan_intelligence_feed_artifacts`
- `scan_intelligence_feed_issues`
- `scan_intelligence_feed_history`

Each run stores the selected scan image, optional upstream anchor ids, `source_checksum`, `feed_checksum`, immutable input/output manifests, and summary counters. Events capture normalized timeline entries with stable rank, category, severity, source-system identity, and replay key. Issues capture feed-level and normalized upstream problems without mutating source ledgers. Artifacts store exportable feed payloads and manifests. History captures feed-run lifecycle entries.

## Deterministic aggregation

The feed service loads immutable upstream rows for a scan image and then:

1. normalizes source rows into canonical event drafts
2. derives synthetic lineage-gap issues when critical upstream stages are missing
3. sorts drafts by `(event_occurred_at, category_rank, severity_rank, source_system_rank, source_record_id, source_checksum, normalized_event_key)`
4. serializes the ordered timeline into manifests and artifacts
5. hashes the normalized manifest payload to produce `feed_checksum`

If an identical `feed_checksum` already exists for the owner, the service returns the existing run instead of creating a duplicate. That keeps replay idempotent and stable.

## Categories and severity

The first pass supports the requested feed categories:

- `INGESTION`
- `NORMALIZATION`
- `BOUNDARY`
- `OCR`
- `RECONCILIATION`
- `DEFECT_FOUNDATION`
- `SPINE`
- `CORNER_EDGE`
- `SURFACE`
- `STRUCTURAL`
- `AGGREGATION`
- `GRADING_ASSISTANCE`
- `VISUAL_EVIDENCE`
- `REVIEW`
- `HISTORICAL_COMPARISON`
- `AUTHENTICATION`
- `OPS`
- `SYSTEM`

Event severities are normalized to:

- `INFO`
- `SUCCESS`
- `WARNING`
- `ERROR`
- `REVIEW_REQUIRED`

## Artifacts

Each run emits deterministic filesystem-backed artifacts:

- `FEED_MANIFEST`
- `SCAN_TIMELINE_EXPORT`
- `SCAN_FEED_EXPORT`
- `OPS_FEED_EXPORT`
- `FEED_DEBUG_PREVIEW`

These are JSON exports in the initial implementation so the web UI can preview and download them without introducing a second serialization path.

## API surface

Owner routes:

- `POST /api/v1/scan-intelligence-feed/run`
- `GET /api/v1/scan-intelligence-feed/runs`
- `GET /api/v1/scan-intelligence-feed/runs/{run_id}`
- `GET /api/v1/scan-intelligence-feed/events`
- `GET /api/v1/scan-intelligence-feed/issues`
- `GET /api/v1/scan-intelligence-feed/artifacts/{artifact_id}`

Ops routes:

- `GET /api/v1/ops/scan-intelligence-feed/runs`
- `GET /api/v1/ops/scan-intelligence-feed/events`
- `GET /api/v1/ops/scan-intelligence-feed/issues`
- `GET /api/v1/ops/scan-intelligence-feed/failures`
- `GET /api/v1/ops/scan-intelligence-feed/review-required`

All routes use the existing scan API v1 envelope.

## Frontend

The web layer adds:

- `ScanIntelligenceFeedPage`
- `ScanIntelligenceFeedSummaryCard`
- `ScanIntelligenceFeedOpsPanel`

The owner page supports scan-image-scoped run launching, timeline filtering by severity/category/source system, issue review, lineage checksums, and artifact preview/download. Dashboard and ops surfaces expose quick status and operational counts without duplicating backend logic.

## Constraints and non-goals

This layer is orchestration and chronology only. It does not:

- assign official grades
- certify authenticity
- estimate FMV
- generate AI narratives
- suppress upstream evidence
- mutate upstream scan systems
- add marketplace logic
