# P71 — Sell Intelligence Platform

Collector exit intelligence built on **read-only** inputs from P61–P69. ComicOS answers whether to sell, why, at what price, auction vs BIN, expected timing, and profit — **without** changing recommendation scoring, inventory FMV, or hold status.

## APIs

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/sell-intelligence/platform/build` | Build all P71 snapshots |
| `GET /api/v1/sell-intelligence/platform/certification` | Certification checks |
| `GET /api/v1/sell-intelligence/exit-recommendations` | Exit scores and actions |
| `GET /api/v1/sell-intelligence/listing-intelligence` | BIN/auction guidance |
| `GET /api/v1/sell-intelligence/liquidity` | Liquidity bands |
| `GET /api/v1/sell-intelligence/exit-queue` | Prioritized queue |
| `GET /api/v1/sell-intelligence/dashboard` | Investor sell cards |

## Feature flags (default true)

`P71_EXIT_RECOMMENDATIONS_ENABLED`, `P71_LISTING_INTELLIGENCE_ENABLED`, `P71_LIQUIDITY_ENABLED`, `P71_EXIT_QUEUE_ENABLED`, `P71_SELL_DASHBOARD_ENABLED`

## UI

`/sell-intelligence` — exit recommendations, queue, listing, liquidity, dashboard.

## Data

Tables prefixed `p71_*`. See phase docs for each engine.
