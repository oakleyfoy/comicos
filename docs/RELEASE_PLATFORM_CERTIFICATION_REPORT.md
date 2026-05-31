# Release Platform Certification Report (P50-05)

**Certification version:** P50-05  
**Scope:** Release Intelligence Platform P50-01 through P50-04D  
**Mode:** Read-only closeout (no scoring, import, scheduler, or variant logic changes)

## Certification criteria

| Gate | Requirement |
|------|-------------|
| Validation | Overall status `PASS` (all subsystem checks PASS; no FAIL) |
| Health | Overall status not `FAILED` |
| Go-live | `APPROVED_FOR_PRODUCTION` when both gates satisfied |

## Subsystems validated

1. Release Intelligence — series, issues, key signals  
2. Watchlists — configured watchlists  
3. Continuity — continue-run planning  
4. Horizons — 30/60/90-day and announced buckets  
5. Spec Intelligence — spec recommendations  
6. Lunar Connector — credentials and completed import runs  
7. Scheduler — config presence and enabled state  
8. Variant Intelligence — variant rows and signals  
9. Re-import Idempotency — no duplicate canonical issue groups  

## Health components monitored

Release Feed, Release Intelligence, Watchlists, Spec Intelligence, Horizons, Scheduler, Variants, Import Pipeline.

## Summary metrics exposed

Total releases, series, variants, new #1 signals, opportunity buckets, watchlists, FOC alerts, scheduler status, last import timestamps, platform readiness score (mean of validation check scores).

## Live verification checklist

- [ ] Lunar imports complete successfully for production owner  
- [ ] Scheduler enabled (or manual import cadence documented)  
- [ ] Variants populated on multi-SKU titles  
- [ ] Second import does not increase duplicate canonical issues  
- [ ] Opportunities and new #1 lists populated for upcoming window  
- [ ] Horizons show issues in 30/60/90-day buckets  
- [ ] `/release-platform-certification` shows `APPROVED_FOR_PRODUCTION` when gates pass  

## API surface

- `GET /api/v1/release-platform/validation`  
- `GET /api/v1/release-platform/health`  
- `GET /api/v1/release-platform/summary`  
- `GET /api/v1/release-platform/certification`  

All routes are owner-scoped and return Scan API v1 envelopes.

## Deferred work (see TECH_DEBT.md)

P50 deferred items are tracked separately; they are out of scope for this certification phase.
