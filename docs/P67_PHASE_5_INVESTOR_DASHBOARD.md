# P67 Phase 5 — Investor Dashboard

**Model:** `P67InvestorDashboardSnapshot` with `cards_json` (winners, losers, largest holdings, grading top, recommendation scorecard).

**Service:** `app/services/investor_dashboard_service.py` — aggregates latest P67-01–04 snapshots.

**API:** `GET/POST /api/v1/investor-dashboard/latest|build`
