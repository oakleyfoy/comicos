# Recommendation Intelligence Runbook (P51)

## Prerequisites

- Release platform certified (P50-05) with Lunar catalog for the owner.
- P51-01 intelligence catalog seeded (`POST /api/v1/intelligence/seed` if empty).
- P51-02 key issues refreshed for owner (`POST /api/v1/key-issues/refresh`).
- P51-03 market/user refresh (`POST /api/v1/market-user-intelligence/refresh`).

## Generate V2 recommendations

```bash
POST /api/v1/recommendations-v2/run
```

Owner-scoped. Append-only: each run adds rows; V1 spec recommendations are not deleted.

## Review outputs

- Dashboard: `GET /api/v1/recommendations-v2/dashboard`
- Detail: `GET /api/v1/recommendations-v2/{id}` (components + decision text)

## Certification closeout (P51-05)

```bash
GET /api/v1/recommendation-intelligence/validation
GET /api/v1/recommendation-intelligence/health
GET /api/v1/recommendation-intelligence/calibration
GET /api/v1/recommendation-intelligence/summary
GET /api/v1/recommendation-intelligence/certification
```

Expected go-live values (only after live V2 run succeeds):

- `APPROVED_FOR_RECOMMENDATION_USE`
- `APPROVED_WITH_WARNINGS`
- Until then: **`NOT_READY`** (default)

## Live owner validation (example owner 40)

From `apps/api`:

```bash
python scripts/live_recommendation_intelligence_certification_check.py --owner-user-id 40
```

Ensure V2 run completes before certification if the catalog is large (V2 run may take several minutes).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Certification NOT_READY | Run V2; confirm explanations exist; review validation FAIL checks |
| Calibration FAIL (identical scores) | Re-run V2 after catalog/key issue refresh; verify score variance |
| Empty key issue bucket | Run key issue refresh against owner catalog |
| V1 missing | Run spec scoring + spec recommendations (V1 path) — do not delete V2 rows |

## Out of scope

Do not use certification endpoints to change scoring, Lunar imports, inventory, orders, or marketplace publishing.
