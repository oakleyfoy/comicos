# P66 Variant & Market Intelligence Platform

Turns **buy this book** into **buy this cover**, **this many copies**, with cited reasons—without changing P61 demand or P62 ranking logic.

## Phases

| Phase | Service | API |
|-------|---------|-----|
| P66-01 Variant Intelligence | `variant_intelligence_service` | `/api/v1/variant-intelligence` |
| P66-02 Quantity Intelligence | `quantity_intelligence_service` | `/api/v1/quantity-intelligence` |
| P66-03 Market Pricing (stub) | `market_pricing_service` | `/api/v1/market-pricing` |
| P66-04 Variant Decision | `variant_decision_engine` | `/api/v1/variant-decision` |
| P66-06 Printing Intelligence | `printing_intelligence` | Lunar import + decision/cross-system UI |

Orchestration: `POST /api/v1/variant-decision/platform/build`  
Integration for P65 workspace: `GET /api/v1/variant-decision/integration/latest`

Migration: `20260611_0226`

## Flags

- `P66_VARIANT_INTELLIGENCE_ENABLED` (default true)
- `P66_QUANTITY_INTELLIGENCE_ENABLED` (default true)
- `P66_MARKET_PRICING_ENABLED` (default true)
- `P66_VARIANT_DECISION_ENABLED` (default true)

## UI

Collector Workspace (`/collector-workspace`) — variant panel, cover comparison, quantity rationale after P66 build.
