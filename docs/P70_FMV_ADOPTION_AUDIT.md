# P70 FMV Adoption Audit

## Authoritative source (P70-06)

**Single authoritative FMV layer:** P68 Market Pricing Engine

- Per-copy: latest `p68_market_price_snapshot` (`blended_fmv`, `raw_fmv`, `graded_fmv`, `confidence`, `liquidity_score`, `sales_count`, `provider_breakdown`, `last_comp_date`)
- Fallback: `p68_inventory_computed_fmv` when no per-copy snapshot exists
- **Inventory `current_fmv` is not auto-overwritten** (`P68_AUTO_OVERWRITE_INVENTORY_FMV=false` by default). Display layers prefer P68 over stored inventory FMV.

Resolver: `apps/api/app/services/authoritative_fmv_service.py`

## Consumer inventory

| Surface | Path | Prior source | P70-06 source |
|--------|------|--------------|---------------|
| Inventory Portfolio / list | `inventory.py` + `inventory_fmv.py` | `InventoryCopy.current_fmv` + legacy `MarketFmvSnapshot` | P68 overlay on `current_market_fmv` and read-model `current_fmv` |
| Collection / market intel rows | `market_intelligence_inventory.py` | `InventoryCopy.current_fmv` | P67 bridge + P68 snapshot via `enrich_row_value` |
| Portfolio analytics (P67) | `portfolio_analytics_service.py` | P67 bridge | P68 snapshot-first in `p68_computed_fmv_for_copy` |
| P71 Sell Intelligence | `p71_sell_context.py` | P68 snapshots + computed FMV | Unchanged; already P68-backed |
| Investor sell dashboard | `investor_sell_dashboard_service.py` | P71 contexts | P68 via P71 context |
| Market & FMV (P68 API) | `market_pricing_engine_api.py` | P68 snapshots | P68 + provider breakdown on read |
| Legacy Market FMV attachment | `inventory_fmv.py` | `MarketFmvSnapshot` | P68 authoritative overlay when present |
| Exit / hold / sell engines | Various P56/P71 | `current_fmv` / bridge | P68-preferred bridge enrichment |
| Recommendation enrichment | `recommendation_priority_enrichment.py` | SQL `avg(current_fmv)` | **Legacy aggregate** — use portfolio/P68 summaries for new work |
| Executive / dealer dashboards | Mixed | Often `current_fmv` in tests/seeds | Display follows inventory list when loaded via API |

## Conflicts removed

- `enrich_row_value` now prefers P68 computed/snapshot FMV before legacy `current_value`.
- Inventory list API aligns `current_fmv` with `p68_authoritative_fmv` in valuation evidence (read-only projection).

## Not in scope (P70-06)

- eBay listing, shipping, grading automation
- Page-load market refresh (refresh is scheduled / manual API only)
