# P40 Replay / Audit Guide

This guide explains how to run and interpret P40 replay audits.

## Replay workflow

1. Select a scan image or use an ops audit scope.
2. Run the replay endpoint for the desired scope.
3. Review replay steps, checks, discrepancies, issues, and artifacts.
4. Compare the replay checksum against any previous run for the same inputs.
5. Escalate critical discrepancies for operational review.

## Example replay lifecycle

- A scan enters the stack through ingestion.
- Downstream phases produce stable ledgers and artifacts.
- Feed aggregates the scan activity into a deterministic timeline.
- Replay audits the stored lineage and derives a stable replay manifest.
- Hardening confirms that the replay contract still holds after end-to-end validation.

## Checksum audits

- Check the stored checksum chain before looking at surface-level symptoms.
- Compare expected and observed values from the replay step table.
- Treat checksum drift as evidence, not as a cue to rewrite history.

## Discrepancy interpretation

- `LINEAGE_GAP`: a required or expected lineage edge is missing.
- `CHECKSUM_MISMATCH`: the stored value and observed value differ.
- `ARTIFACT_MISSING`: the referenced artifact bytes are not present.
- `ORDERING_DRIFT`: stored ordering no longer matches deterministic replay ordering.
- `IMMUTABILITY_VIOLATION`: bytes or histories changed when they should not have.

## Lineage validation

- Confirm the full P40 lineage chain is present.
- Confirm the phase order is stable.
- Confirm that optional phases are recorded explicitly when absent.

## Immutability validation

- Compare file checksums to the persisted artifact checksums.
- Confirm history rows are append-only and ordered.
- Treat any mismatch as CRITICAL unless the phase explicitly documents a non-blocking condition.

## Operational procedures

- Always start with the replay manifest and summary counters.
- Use ops routes for fleet-wide diagnostics only.
- Do not repair artifacts or rewrite checksums manually as part of audit review.

## Troubleshooting guidance

- If replay returns `FAILED` or `CRITICAL`, inspect discrepancies first.
- If an artifact preview looks truncated, use the artifact checksum and file path to confirm integrity.
- If lineage looks incomplete, trace backward using the dependency graph and lifecycle docs.

## Audit workflows

- Owner audit: confirm a specific scan image’s replay is stable.
- Ops audit: search for fleet-level critical discrepancies.
- Regression audit: compare current replay outputs with prior known-good runs after migrations or deployments.

