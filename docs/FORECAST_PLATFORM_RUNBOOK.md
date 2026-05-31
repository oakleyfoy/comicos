# Forecast Platform Runbook

Operational guide for the ComicOS P47 decision-intelligence stack: market intelligence, forecasting, risk assessment, dealer copilot, and validation/learning.

## Market intelligence lifecycle

1. `market_signal_agent` appends owner-scoped `MarketSignal` rows from inventory, FMV, and marketplace context.
2. `market_snapshot_agent` appends `MarketSnapshot` rows summarizing daily and weekly market posture.
3. `market_trend_agent` appends `MarketTrend` rows for market and asset direction.
4. `market_observation_agent` appends `MarketObservation` rows describing notable conditions without making decisions.

### Troubleshooting

- No dashboard market score: verify signals exist, then run snapshot generation.
- Sparse trends: confirm snapshots and signals exist for the owner before trend execution.
- Observation gaps: observations depend on trend/snapshot coverage; backfill those first.

## Forecast lifecycle

1. `price_forecast_agent` appends price forecasts and forecast points.
2. `trend_forecast_agent` appends bullish, bearish, strength, and momentum forecast rows.
3. `market_risk_agent` appends read-only risk assessments.
4. Forecast dashboards consume immutable history only; no forecast rows are updated in place.

### Recovery

- Poor forecast coverage: run price, trend, then risk agents in order.
- Unexpected forecast mix: inspect owner-scoped signal and trend history before regenerating.
- Do not edit forecast rows manually; append new forecast history through agent runs only.

## Risk assessment lifecycle

1. Risk agent reads signal volatility, trend direction, and snapshot posture.
2. It appends `MarketRiskAssessment` rows for volatility, decline, liquidity, or instability.
3. Risk rows inform dealer copilot and validation layers but do not trigger actions.

### Recovery

- Missing risks: confirm market signals and trends exist for the asset or owner.
- Excessive risk volume: review duplicated or unstable signal generation before further runs.

## Dealer recommendation lifecycle

1. Opportunity scores are derived from forecasts, risks, and market demand signals.
2. Dealer agents append `DealerRecommendation` rows for buy, sell, hold, grade, and watch actions.
3. Every recommendation must have evidence rows.
4. Reviews are appended separately through reviewed, accepted, or dismissed actions.

### Recovery

- Recommendation without evidence: treat as validation failure and inspect copilot agent output.
- Missing recommendation types: verify opportunity scores exist before running dealer agents.
- Do not change recommendation records in place; append reviews instead.

## Validation and learning lifecycle

1. `forecast_validation_agent` appends forecast vs. actual validation rows and daily accuracy metrics.
2. `forecast_learning_agent` appends outcome rows for forecasts and recommendations.
3. `forecast_reliability_agent` appends drift events and signal quality metrics.
4. `forecast-platform` closeout services read these append-only records to calculate readiness and certification.

### Recovery

- No accuracy metrics: run validation first, then learning and reliability.
- Confidence failures: inspect forecast confidence against actual error before rerunning the reliability agent.
- Missing signal quality: ensure signals exist for the owner and rerun reliability.

## Certification and closeout

- `GET /api/v1/forecast-platform/validation` returns deterministic PASS, WARNING, or FAIL checks.
- `GET /api/v1/forecast-platform/health` returns on-demand HEALTHY, WARNING, FAILED, or DISABLED health.
- `GET /api/v1/forecast-platform/certification` determines whether the P47 platform is certified.
- Certification is read-only and does not mutate forecasts, recommendations, or validations.

## Recovery procedures

1. Run owner-scoped validation: `market intelligence -> forecasting -> dealer copilot -> validation/learning`.
2. Inspect `/api/v1/forecast-platform/validation` for failing checks.
3. Inspect `/api/v1/forecast-platform/health` for failed or warning components.
4. Re-run the missing upstream agent layer only; do not rewrite historical rows.
5. Re-check certification once validation passes and health stabilizes.

## Escalation

- If forecasts appear inconsistent with signals, stop downstream interpretation and inspect P47-01/P47-02 lineage first.
- If dealer recommendations are missing evidence, treat the platform as uncertified until corrected.
- If validation records are absent, do not treat forecast confidence as production-ready.
