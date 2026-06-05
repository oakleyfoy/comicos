# P67 Phase 1 — Portfolio Performance

**Models:** `P67PortfolioPerformanceSnapshot`, `P67PortfolioPerformanceItem` (`p67_portfolio_performance_*`).

**Metrics:** cost basis, estimated value, unrealized/realized gain and %, average ROI, portfolio CAGR (derived), best/worst/largest position; publisher and series ROI in `metadata_json`.

**Service:** `app/services/portfolio_analytics_service.py`

**API:** `GET/POST /api/v1/portfolio-analytics/latest|build`
