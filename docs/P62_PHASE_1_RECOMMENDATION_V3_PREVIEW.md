# P62 Phase 1 — Recommendation V3 Preview

**Status:** Implemented (read-only foundation).

**Scope:** `RecommendationV3ScoringContext`, P61 component calculators, V3 preview + certification APIs, feature flags. No buy queue, FOC, pull forecast, auto watchlists, or V3 persistence.

---

## Feature flags

| Env | Default | Behavior |
|-----|---------|----------|
| `P62_V3_PREVIEW_ENABLED` | `true` | Gates `GET /v3/preview` |
| `P62_V3_PERSIST_ENABLED` | `false` | Must stay false in Phase 1; no V3 snapshot persist |
| `P62_READ_ONLY_GET` | `true` | `GET /cross-system-recommendations` reads persisted snapshot only |

Settings: `app/core/config.py` (`Settings.p62_*`).

---

## Services

| Module | Role |
|--------|------|
| `recommendation_v3_scoring_context.py` | Batch P61 demand, velocity, spec, observation depth |
| `recommendation_v3_components.py` | Five P61 component scores + `preview_score` |
| `recommendation_v3_preview_service.py` | V2 candidates + V3 breakdown; no V2 persist |
| `recommendation_v3_certification.py` | Phase 1 cert gates |
| `p62_feature_flags.py` | Flag accessors |

---

## APIs

| Method | Path |
|--------|------|
| `GET` | `/api/v1/recommendation-intelligence/v3/preview` |
| `GET` | `/api/v1/recommendation-intelligence/v3/certification` |

Preview response includes `v2_priority_score`, `v3_preview_score`, per-component breakdown, `readiness.reason_codes`, and `v2_mutated` (must be `false`).

---

## Certification (Phase 1)

PASS when:

- Global `issue_demand_snapshot` count &gt; 0
- Global `demand_velocity_snapshot` count &gt; 0
- V3 preview returns ≥ 1 scored candidate
- `v2_mutated` is false
- `P62_V3_PERSIST_ENABLED` is false

Missing owner spec snapshot is reported as `NO_SPEC_OPPORTUNITY_SNAPSHOT` but does not block preview when demand/velocity exist.

---

## Tests

`apps/api/tests/test_recommendation_intelligence_v3_phase1.py`

---

## Reproduction

```bash
cd apps/api
python -m pytest tests/test_recommendation_intelligence_v3_phase1.py -q
```
