# Recommendation Intelligence Architecture (P51)

Phase 51 delivers advisory buy recommendations by combining release catalog data with layered intelligence inputs and Recommendation Engine V2 scoring.

## Layers

| Phase | Capability | Primary artifacts |
|-------|------------|-----------------|
| P51-01 | Character, franchise, creator intelligence | `CharacterProfile`, `FranchiseProfile`, `CreatorProfile`, popularity scores, release matching |
| P51-02 | Key issue intelligence | `KeyIssueProfile`, classifications, importance scoring |
| P51-03 | Market & user intelligence | `MarketDemandProfile`, `UserPreferenceProfile`, combined market/user fit |
| P51-04 | Recommendation Engine V2 | `RecommendationScoreV2`, score components, decisions, append-only runs |
| P51-05 | Validation, calibration, certification | Read-only validation/health/calibration/certification services |

## Scoring (V2)

V2 scoring lives in `recommendation_v2_components.py`. Components include investment #1 vs random #1, run-start value, P51-01/02/03 inputs, variant scarcity, horizon timing, continuity, and risk penalty. V1 spec scoring (`spec_scoring_agent.py`) remains unchanged and preserved.

## Data flow

1. Release catalog (P50) provides issues/variants/signals.
2. P51-01–03 enrich entities and preferences (seed + owner inference).
3. P51-04 run produces append-only V2 scores, components, and explanations.
4. P51-05 validates inputs/outputs and certifies readiness without mutating scores.

## Advisory boundary

Recommendations do not create orders, purchases, cart actions, or marketplace listings. All outputs are explainable tiers: MUST_BUY, STRONG_BUY, BUY, WATCH, PASS.

## APIs

- V2: `/api/v1/recommendations-v2/*`
- Certification: `/api/v1/recommendation-intelligence/*`

## UI

- `/recommendations-v2` — tier buckets and component breakdown
- `/recommendation-intelligence-certification` — validation, health, calibration, certification
