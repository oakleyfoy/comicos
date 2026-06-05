# P63 — Market Intelligence Platform

**Status:** Implemented (P63-01 through P63-04).

**Context:** Builds on certified P61 demand signals and P62 recommendation/collector layers. Does **not** replace P62, enable V3 persistence, or implement P64 AI assistant.

**Goal:** Owner-scoped **Buy / Hold / Sell / Acquire / Grade / Watch** guidance from inventory, FMV, demand, and recommendation preview inputs.

**Phase docs:**

- [P63_PHASE_1_PORTFOLIO_PERFORMANCE.md](P63_PHASE_1_PORTFOLIO_PERFORMANCE.md)
- [P63_PHASE_2_SELL_SIGNAL_INTELLIGENCE.md](P63_PHASE_2_SELL_SIGNAL_INTELLIGENCE.md)
- [P63_PHASE_3_ACQUISITION_OPPORTUNITY.md](P63_PHASE_3_ACQUISITION_OPPORTUNITY.md)
- [P63_PHASE_4_MARKET_SIGNAL_INTELLIGENCE.md](P63_PHASE_4_MARKET_SIGNAL_INTELLIGENCE.md)

**Certification:** [P63_MARKET_INTELLIGENCE_CERTIFICATION_REPORT.md](P63_MARKET_INTELLIGENCE_CERTIFICATION_REPORT.md)

---

## API base

`/api/v1/market-intelligence`

| Area | GET latest | POST build | PATCH status | GET certification |
|------|------------|------------|--------------|-------------------|
| Portfolio | `/portfolio/latest` | `/portfolio/build` | — | `/portfolio/certification` |
| Sell signals | `/sell-signals/latest` | `/sell-signals/build` | `/sell-signals/item/{id}` | `/sell-signals/certification` |
| Acquisition | `/acquisition/latest` | `/acquisition/build` | `/acquisition/item/{id}` | `/acquisition/certification` |
| Market signals | `/signals/latest` | `/signals/build` | — | `/signals/certification` |
| Platform | — | `/platform/build` | — | `/platform/certification` |

**Contract:** GET is read-only; rebuild via POST only (same pattern as P61/P62).

---

## Feature flags (default **true**)

- `P63_MARKET_INTELLIGENCE_ENABLED`
- `P63_PORTFOLIO_PERFORMANCE_ENABLED`
- `P63_SELL_SIGNALS_ENABLED`
- `P63_ACQUISITION_OPPORTUNITIES_ENABLED`
- `P63_MARKET_SIGNALS_ENABLED`

---

## Migration

`20260608_0223_add_p63_market_intelligence_platform.py`

---

## Tests

`apps/api/tests/test_p63_*.py`
