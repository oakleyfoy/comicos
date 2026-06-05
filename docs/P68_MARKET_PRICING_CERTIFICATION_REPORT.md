# P68 Market Pricing — Certification Report

**Tests:**

```powershell
cd apps/api
python -m pytest tests/test_market_pricing_provider.py tests/test_market_price_observations.py tests/test_fmv_calculation_engine.py tests/test_market_price_identity_matching.py tests/test_p68_market_pricing_platform.py -q
```

| Check | Status |
|-------|--------|
| Observations ingest (manual + internal) | API + unit tests |
| Snapshots build | POST `/snapshots/build` |
| FMV math / outliers | `test_fmv_calculation_engine` |
| Printing identity guards | `test_market_price_identity_matching` |
| P67 consumes computed FMV | `p67_inventory_bridge.p68_computed_fmv_for_copy` |
| No auto inventory overwrite | `P68_AUTO_OVERWRITE_INVENTORY_FMV=false` in certification |

**P68 Market Pricing: CERTIFIED** (automated).
