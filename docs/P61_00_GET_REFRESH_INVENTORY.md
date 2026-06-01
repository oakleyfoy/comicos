# P61-00 — GET endpoints that performed refresh/generation (before P61)

## P58–P60 industry & spec (addressed in P61-00)

| Endpoint | Was | After P61-00 |
|----------|-----|----------------|
| `GET /api/v1/industry-scanner-dashboard` | `refresh=true` default → opportunity sync | `refresh=false` default; explicit `?refresh=true` or UI button |
| `GET /api/v1/industry-scanner-dashboard/summary` | same | same |
| `GET /api/v1/industry-opportunities/latest` | full refresh | read persisted; `POST .../refresh` |
| `GET /api/v1/industry-release-signals/latest` | classify/sync | read persisted; `POST .../refresh` |
| `GET /api/v1/spec-inputs/latest` | build inputs | read persisted; `POST .../refresh` |
| `GET /api/v1/spec-baseline-scores/latest` | generate baselines | read persisted; `POST .../refresh` |
| `GET /api/v1/ai-spec-evaluations/latest` | generate AI evals | read persisted; `POST .../refresh` |
| `GET /api/v1/top-spec-picks/latest` | rank + AI eval generation | read persisted; `POST .../run` |
| `GET /api/v1/weekly-spec-dashboard` | read-only (unchanged) | read-only |
| `POST /api/v1/spec-automation/run` | ops-only manual pipeline | owner manual pipeline (unchanged logic) |

## Certification (unchanged — manual POST, ops where configured)

- `POST /api/v1/ai-spec-certification/run`
- `POST /api/v1/industry-scanner-certification/run`
- `POST /api/v1/production-readiness/run` (+ subpaths)
- `POST /api/v1/final-platform-certification/run`
- `POST /api/v1/industry-scanner/run` (full scanner automation, ops admin)

## Other GET refresh patterns (out of P61-00 scope)

| Endpoint | Behavior |
|----------|----------|
| `GET /api/v1/organizations/{id}/dashboard?refresh=true` | org dealer dashboard regeneration |
| `GET /api/v1/cross-system-recommendations` | calls `refresh_and_list_latest_*` |
| `GET /api/v1/cross-system-recommendations/summary` | `generate_cross_system_recommendations` |

Measure memory: `python apps/api/scripts/measure_p61_dashboard_memory.py`
