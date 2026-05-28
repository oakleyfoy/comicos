# P40 Operations Guide

This guide describes how to operate the completed P40 scan intelligence stack in production.

## Deployment guidance

- Deploy the API, worker, and frontend as separate services.
- Run Alembic migrations before enabling traffic.
- Confirm the backend starts cleanly with production environment variables.
- Keep ops admin email allowlists populated for `/ops` access.

## Recommended production workflow

1. Deploy schema changes.
2. Verify `/health`, `/health/db`, `/health/redis`, and `/health/worker`.
3. Confirm the scan workspace routes load in the frontend.
4. Run a representative feed and replay on a known-good scan image.
5. Check hardening outputs for critical discrepancies before opening traffic broadly.

## Replay diagnostics

- Use replay runs to confirm checksum continuity, ordering stability, and artifact immutability.
- Review `CRITICAL` discrepancies first.
- Treat `LINEAGE_GAP`, `CHECKSUM_MISMATCH`, `ARTIFACT_MISSING`, and `IMMUTABILITY_VIOLATION` as the highest-priority classes.

## Feed diagnostics

- Feed diagnostics should confirm deterministic event ordering and stable feed checksums.
- If feed creation returns an existing run, that is expected idempotent behavior for the same owner and input.
- Review feed artifacts when event or issue counts look inconsistent.

## Artifact troubleshooting

- Check that artifact paths match the deterministic storage convention.
- Confirm the owning run id and owner id line up with the artifact record.
- Compare stored checksums to the on-disk bytes before assuming corruption.

## Lineage troubleshooting

- Trace from ingestion to replay in the dependency graph.
- Missing optional stages should be explicit `SKIPPED` states.
- Missing required stages should surface as issues or discrepancies.

## Replay discrepancy handling

- Do not auto-repair.
- Do not overwrite artifacts in place.
- Preserve the discrepancy payload and escalate it operationally.

## Ops route usage

- Ops routes are read-only.
- Use them for fleet diagnostics, not for mutations.
- Mutation attempts on ops routes should fail and should be treated as a security signal.

## Storage guidance

- Keep replay and feed storage roots on durable volume-backed storage.
- Preserve deterministic directory structures.
- Avoid ad hoc manual edits inside storage roots.

## Backup recommendations

- Backup the database first; it is the source of truth for lineage and history.
- Back up storage roots that contain original scans, derived artifacts, feed exports, and replay exports.
- Keep retention policies aligned with immutable audit requirements.

## Migration management

- Always verify Alembic head continuity after schema changes.
- Do not ship a production deployment with multiple heads.
- When in doubt, run the focused P40 regression set after migration application.

## Monitoring recommendations

- Monitor replay failure counts, critical discrepancies, feed errors, and worker health.
- Track build warnings as non-blocking but visible signals.
- Watch for query growth or payload growth in feed and replay exports over time.

