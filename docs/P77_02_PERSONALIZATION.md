# P77-02 Personalized Recommendations & Quantity Intelligence

Applies P77-01 collector profile to existing P51/P55/P53 outputs without replacing engines.

## Formula

`personalized_score = clamp(global_score + collector_adjustments)`

Adjustments consider publishers, characters, creators, goals, gap completion, duplicate ownership, budget state (GREEN/YELLOW/RED), and risk profile.

## API (`/api/v1/collector-profile`)

| Path | Purpose |
|------|---------|
| GET `/recommendations` | Personalized unified + acquisition list with budget filtering |
| GET `/quantities` | P53 quantity recs with profile-adjusted copy counts |
| GET `/budget-status` | Monthly spend, remaining, utilization, state |
| GET `/personalized-dashboard` | Budget + top recs + quantity highlights |

## P80 integration

Collector scan responses include `personalization` and action cards use personalized score / budget state for BUY vs PASS.

Engine version: `collector_personalization` = `P77-02`
