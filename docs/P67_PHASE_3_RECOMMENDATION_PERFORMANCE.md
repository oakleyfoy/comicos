# P67 Phase 3 — Recommendation Performance

**Models:** `P67RecommendationPerformanceSnapshot`, `P67RecommendationPerformanceItem`.

**Tracks:** recommended / held / purchased / outcome per `cross_system_recommendation` row (read-only).

**Metrics:** hit rate, average return, recommendation ROI, confidence accuracy, best/worst titles.

**Service:** `app/services/recommendation_performance_service.py`

**API:** `GET/POST /api/v1/recommendation-performance/latest|build`
