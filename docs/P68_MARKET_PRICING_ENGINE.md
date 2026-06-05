# P68 Real FMV / Market Pricing Engine

Provider-agnostic pricing layer consuming inventory FMV, **INTERNAL_SALE** ledger rows, and manual overrides — without auto-overwriting `inventory_copy.current_fmv` (unless `P68_AUTO_OVERWRITE_INVENTORY_FMV=true`).

## Phases

| Phase | Doc |
|-------|-----|
| P68-01 Provider abstraction | [P68_PHASE_1_PROVIDER_ABSTRACTION.md](P68_PHASE_1_PROVIDER_ABSTRACTION.md) |
| P68-02 eBay adapter skeleton | [P68_PHASE_2_EBAY_ADAPTER_SKELETON.md](P68_PHASE_2_EBAY_ADAPTER_SKELETON.md) |
| P68-03 FMV calculation | [P68_PHASE_3_FMV_CALCULATION.md](P68_PHASE_3_FMV_CALCULATION.md) |
| P68-04 Price matching | [P68_PHASE_4_PRICE_MATCHING.md](P68_PHASE_4_PRICE_MATCHING.md) |
| P68-05 Portfolio FMV integration | [P68_PHASE_5_PORTFOLIO_FMV_INTEGRATION.md](P68_PHASE_5_PORTFOLIO_FMV_INTEGRATION.md) |
| P68-06 Internal sales ledger | `INTERNAL_SALE` provider in `internal_sale_provider.py` |

## APIs

`/api/v1/market-pricing/providers|observations|snapshots/latest|snapshots/build|manual|certification`

(P66 stub pricing remains at `/api/v1/market-pricing/latest` + `/build` on the legacy P66 router.)

## Tables

`p68_market_pricing_provider`, `p68_market_price_observation`, `p68_market_price_snapshot`, `p68_market_price_match_result`, `p68_inventory_computed_fmv`

## UI

`/portfolio-analytics` — Market Pricing (P68) panel with computed FMV, confidence, sales band, provider label.

## Certification

[ P68_MARKET_PRICING_CERTIFICATION_REPORT.md](P68_MARKET_PRICING_CERTIFICATION_REPORT.md)
