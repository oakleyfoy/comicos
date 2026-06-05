# P68 Phase 5 — Portfolio FMV Integration

`p68_inventory_computed_fmv` stores computed FMV separately from `inventory_copy.current_fmv`.

P67 `portfolio_analytics_service` prefers copy FMV, then P68 computed, then P66 stub map.

`P68_AUTO_OVERWRITE_INVENTORY_FMV` default **false**.
