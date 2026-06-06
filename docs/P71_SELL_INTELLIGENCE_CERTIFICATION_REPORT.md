# P71 Sell Intelligence Certification Report

## Scope

Verify P71 builds read-only sell intelligence from P61–P69 without mutating upstream systems.

## Automated checks

`GET /api/v1/sell-intelligence/platform/certification` after `POST .../platform/build`:

| Check | Expectation |
|-------|-------------|
| exit_recommendations | Snapshot present |
| listing_intelligence | Snapshot present |
| liquidity | Snapshot present |
| exit_queue | Snapshot present |
| sell_dashboard | Snapshot with cards |
| owner_isolation | Per-owner snapshots |
| no_upstream_mutation | `inventory_copy.current_fmv` unchanged |

## Test suite

`tests/test_p71_sell_intelligence_platform.py` plus unit tests for scoring modules.

## Manual

1. Open `/sell-intelligence` and run Refresh build.
2. Confirm recommendations render for holdings with FMV.
3. Confirm no inventory hold status changes after build.

## Status

Certified when platform certification returns `certified: true` in CI/local pytest.
