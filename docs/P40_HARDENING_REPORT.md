# P40 Hardening Report

## Scope

P40-19 is the final validation sweep for the P40 scan intelligence stack. It does not add new behavior; it checks that completed phases remain deterministic, replay-safe, immutable, and isolated.

## Deterministic guarantees

- Repeated identical feed runs produce stable checksums and stable ordering.
- Repeated identical replay runs produce stable `replay_checksum` values.
- Feed events, replay steps, checks, discrepancies, and history records remain stably ordered.
- Manifest payloads remain deterministic and replay-safe.

## Replay guarantees

- Replay verification is performed over immutable upstream inputs.
- Replay discrepancies are preserved, not repaired or hidden.
- Replay artifacts are append-only and use deterministic storage paths.
- Replay isolation is enforced through owner-scoped access controls.

## Immutability guarantees

- Original scan inputs remain unchanged.
- Normalized and downstream artifacts remain checksum-stable.
- Replay artifacts never overwrite upstream artifacts.
- Review history remains append-only.

## Owner isolation guarantees

- Cross-owner access to run detail and artifact routes is blocked.
- Ops routes are read-only and diagnostic only.
- Envelope structure remains consistent across owner and ops surfaces.

## Known limitations

- Full hardening runs are still relatively expensive in local test environments.
- Web bundle size still produces a non-blocking Rollup warning.
- Deterministic validation exists as test coverage rather than a continuous runtime monitor.
- External audit export destinations are deferred.
- Production-scale query tuning and performance profiling remain future work.

## Production-readiness notes

- The P40 stack has targeted regression coverage for ingestion, feed, replay, review, historical comparison, and authentication support.
- The final hardening pass validates the most important stability and isolation contracts without introducing new feature behavior.
- No CRITICAL hardening issues should remain unresolved before promotion.
