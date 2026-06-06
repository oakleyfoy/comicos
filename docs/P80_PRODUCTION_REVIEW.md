# P80 Mobile Scanning & Inventory Capture — Production Review

## Architecture summary

P80 is a collector-facing mobile workflow stack built on existing ComicOS intelligence engines (no duplicate FMV, recommendation, grading, or acquisition engines).

| Phase | Role | API prefix |
|-------|------|------------|
| P80-01 | Scan identification + intelligence consolidation | `/api/v1/mobile` |
| P80-02 | Intake, storage assignment, audits, ops dashboard | `/api/v1/mobile/intake`, `storage`, `audit`, `operations` |
| P80-03 | Shopping / convention collector assistant | `/api/v1/collector` |
| P80-04 | Certification & production readiness | `/api/v1/mobile/certification` |

Web routes: `/mobile-scan`, `/mobile-intake`, `/mobile-storage`, `/mobile-audit`, `/mobile-operations`, `/collector-assistant`, `/convention-mode`, `/collector-dashboard`.

## Workflow summary

1. **Scan** — UPC/ISBN/QR or manual entry → book identity → ownership, P68 FMV, P51 recommendation, P72 grading, P79 storage paths, action card.
2. **Receive** — Order-linked intake scans mark copies received and track session metrics.
3. **Store** — Suggest slot/box (series grouping) and assign P79 locations.
4. **Audit** — Box-scoped verification, missing/unexpected detection.
5. **Shop** — Collector scan with optional vendor price, gap/run context, spec signals, BUY/PASS/HOLD/SELL/GRADE/WATCH action card.

## Certification

Service: `apps/api/app/services/mobile_scanning_certification.py`

Endpoints:

- `GET /api/v1/mobile/certification` — full category checks and `APPROVED_FOR_PRODUCTION` / `NEEDS_ATTENTION`
- `GET /api/v1/mobile/certification-dashboard` — readiness %, performance targets, production checklist

Categories exercised: identification, ownership, FMV, recommendation, grading, storage, inventory operations (intake/storage/audit), collector assistant, end-to-end scan, performance latency.

### Example certification output

```
Mobile Scanning Certification
Status: APPROVED_FOR_PRODUCTION
Checks Passed: 30+
Warnings: 0
Failures: 0
Platform Readiness: 99%+
```

## Production readiness checklist

| Area | Status |
|------|--------|
| Identification | PASS |
| Ownership | PASS |
| FMV | PASS |
| Recommendations | PASS |
| Grading | PASS |
| Storage | PASS |
| Intake | PASS |
| Audits | PASS |
| Collector Assistant | PASS |
| Mobile Performance | PASS |

Performance targets (certification): mobile scan & collector scan &lt; 2s; storage assign &amp; audit verify &lt; 1s (observed in-process; API round-trips may vary in CI).

## Test coverage

- `apps/api/tests/test_mobile_scanning.py` — P80-01
- `apps/api/tests/test_mobile_inventory_operations.py` — P80-02
- `apps/api/tests/test_mobile_collector_assistant.py` — P80-03
- `apps/api/tests/test_mobile_certification.py` — P80-04 certification API
- `apps/api/tests/test_mobile_performance.py` — latency smoke tests

Organization dealer capture (P44) tests: `apps/api/tests/test_organization_mobile_scanning.py`.

## Exit criteria

P80 is complete when certification returns **APPROVED_FOR_PRODUCTION** with zero failures for P80-01, P80-02, and P80-03 integration paths, and integration tests above pass.
