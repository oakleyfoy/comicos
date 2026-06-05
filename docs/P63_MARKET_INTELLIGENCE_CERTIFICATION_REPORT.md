# P63 Market Intelligence — Certification Report

**Run date (UTC):** 2026-06-03  
**Runner:** `python apps/api/scripts/p63_market_intelligence_certification.py`  
**Out of scope:** P64 assistant, V3 persistence, P62 replacement.

---

## Executive summary

| Gate | Result |
|------|--------|
| Pytest (P63 platform modules) | **PASS** (see CI/local run) |
| Portfolio snapshot build | **PASS** (with inventory) |
| Sell signals build + ordering | **PASS** |
| Acquisition opportunities build | **PASS** |
| Market signals + explanations | **PASS** |
| HTTP APIs (build / latest / patch / cert) | **PASS** |
| P62 row isolation (buy queue snapshots unchanged on P63 build) | **PASS** |
| Empty owner portfolio cert | **NOT_READY** (expected) |

**Overall:** **CERTIFIED** when owner has inventory and platform certification returns `platform_ready: true`.

---

## Automated tests

```bash
cd apps/api
python -m pytest tests/test_p63_portfolio_performance.py \
  tests/test_p63_sell_signals.py \
  tests/test_p63_acquisition_opportunities.py \
  tests/test_p63_market_signals.py \
  tests/test_p63_market_intelligence_platform.py -q
```

---

## Re-run

```bash
python scripts/p63_market_intelligence_certification.py --owner-email <email>
```

Use `--skip-pytest` when tests already ran in CI.
