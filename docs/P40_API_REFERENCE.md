# P40 API Reference

This reference summarizes the stable P40 route families and their response conventions.

## Envelope structure

P40 scan APIs use the v1 envelope:

```json
{
  "data": { },
  "meta": { }
}
```

- `data` contains the payload or list response.
- `meta` carries owner scope, snapshot/checksum metadata, generated time, and engine versions.

## Pagination structure

List responses use stable pagination fields and deterministic ordering. The payload shape is consistent across owner and ops surfaces.

## Owner routes

- Ingestion, normalization, boundary, OCR, reconciliation, defect, aggregation, grading assistance, visual evidence, review, historical comparison, authentication, feed, and replay routes all expose owner-scoped read/write surfaces according to their phase design.
- Owner list/detail routes require authenticated owner access.

## Ops routes

- Ops routes are read-only diagnostics.
- They mirror the owner data shape but may add fleet-wide filters and cross-owner visibility where appropriate.
- Mutation attempts on ops routes should fail.

## Artifact routes

- Artifact detail routes expose stored export payloads and previews.
- Artifact access follows the owner of the underlying run.
- Artifact content is immutable once written.

## History routes

- History routes expose append-only lifecycle evidence.
- History is ordered deterministically by creation time and stable identifiers.

## Feed routes

- `POST /api/v1/scan-intelligence-feed/run`
- `GET /api/v1/scan-intelligence-feed/runs`
- `GET /api/v1/scan-intelligence-feed/runs/{run_id}`
- `GET /api/v1/scan-intelligence-feed/events`
- `GET /api/v1/scan-intelligence-feed/issues`
- `GET /api/v1/scan-intelligence-feed/artifacts/{artifact_id}`
- Ops mirrors under `/api/v1/ops/scan-intelligence-feed/*`

## Replay routes

- `POST /api/v1/scan-replay/run`
- `GET /api/v1/scan-replay/runs`
- `GET /api/v1/scan-replay/runs/{run_id}`
- `GET /api/v1/scan-replay/steps`
- `GET /api/v1/scan-replay/checks`
- `GET /api/v1/scan-replay/discrepancies`
- `GET /api/v1/scan-replay/issues`
- `GET /api/v1/scan-replay/artifacts/{artifact_id}`
- Ops mirrors under `/api/v1/ops/scan-replay/*`

## Auth expectations

- Owner routes require authenticated owner access.
- Ops routes require configured ops authorization.
- Unauthorized access should fail before any mutation or read leakage occurs.

## Deterministic ordering expectations

- List responses are stable across repeated identical inputs.
- Pagination windows must not reorder the underlying rows.
- Route responses should preserve the ordering implied by the stored ledgers.

## Replay expectations

- Replay is a read/audit path over immutable upstream evidence.
- Replay results must remain checksum-stable for identical inputs.
- Replay discrepancies must be surfaced, not suppressed.

