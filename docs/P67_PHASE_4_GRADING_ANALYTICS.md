# P67 Phase 4 — Grading Analytics

**Models:** `P67GradingOpportunitySnapshot`, `P67GradingOpportunityItem`.

**Sources:** P66 variant decision items + raw inventory copies; stub graded FMV uplift (no external grading provider).

**Metrics:** estimated grade, submission score, estimated ROI, raw vs graded value, submission priority queue.

**Service:** `app/services/grading_analytics_service.py`

**API:** `GET/POST /api/v1/grading-analytics/latest|build`
