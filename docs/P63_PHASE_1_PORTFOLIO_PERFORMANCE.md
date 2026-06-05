# P63 Phase 1 — Portfolio Performance Intelligence

**Service:** `portfolio_performance_service.py`  
**Tables:** `portfolio_performance_snapshot`, `portfolio_performance_item`

Aggregates owner `inventory_copy` cost basis vs `current_fmv`, assigns performance tiers (`STRONG_GAIN`, `MODEST_GAIN`, `FLAT`, `DOWN`, `UNKNOWN`), and exposes top gainers/losers on the snapshot.
