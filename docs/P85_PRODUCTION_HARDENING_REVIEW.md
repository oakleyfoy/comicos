# P85 — Production Hardening & Collector Workflow Optimization

## Purpose

P85 polishes ComicOS into a coherent collector operating system: unified home, simplified navigation, clearer empty/error states, workflow health visibility, and cross-platform production certification—without new intelligence engines.

## Workflow audit summary

| Area | P85 change |
|------|------------|
| Home | `/collector-home` aggregates P77–P84 signals with capped list sizes |
| Command center | Reduced default refresh work (no forced marketplace seed on load) |
| Navigation | Ten workflow groups: Home, Buy, Inventory, Storage, Grade, Sell, Discovery, Mobile, Reports, Settings |
| Dashboards | Collector-themed empty/error components on marketplace + command center |
| Certification | `GET /api/v1/platform/certification` smoke-orchestrates existing platforms |
| Safety | Publish remains explicit POST; certification endpoints are GET-only smoke |

## Collector home architecture

`collector_home_service.build_collector_home` composes:

- Daily actions (P57)
- Buy/sell/grade slices (P78, P82)
- FOC / future pull (P81)
- Storage unassigned count (P79)
- Budget + portfolio movement (P77, P83)

All sections use `_HOME_LIMIT = 10` to avoid large aggregation cost.

## APIs

| Endpoint | Service |
|----------|---------|
| `GET /api/v1/collector-home` | `collector_home_service` |
| `GET /api/v1/platform/certification` | `platform_production_certification` |
| `GET /api/v1/platform/production-dashboard` | `platform_production_certification` |
| `GET /api/v1/platform/workflow-health` | `workflow_health_service` |

Scan metadata: `platform_certification`, `collector_home`, `workflow_health` → **P85**.

## Production safety checklist

- [x] No destructive reset in P85 certification path
- [x] Marketplace publish requires existing draft + explicit POST
- [x] Owner scoping via `get_current_user` on all P85 routes
- [x] Certification uses read-only smoke calls (optional `session.commit` for persisted subdomain snapshots only where already used)
- [x] Workflow health reports empty data without raising

## Certification output

Expected status: **`CERTIFIED_PRODUCTION_RELEASE`** when all category smokes pass.

Categories include release monitoring, recommendations, pull/FOC, purchase profile, portfolio home, market pricing, grading, selling, storage, mobile, discovery, marketplace acquisition, valuation, notifications, command center, and workflow health.

## Remaining known issues

- Full subdomain certification (P74/P78/P79/etc.) is not re-run inside P85; smokes validate availability only.
- Storage health on home uses unassigned count only (no full analytics pass on every home load).
- Legacy routes remain reachable via direct URL; nav no longer lists every phase dashboard at top level.

## Tests

- `tests/test_platform_certification.py`
- `tests/test_collector_home.py`
- `tests/test_workflow_health.py`
- `tests/test_navigation_contract.py`
- `tests/test_production_safety.py`
