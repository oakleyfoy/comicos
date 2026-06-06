# P74-02 FOC & Purchase Intelligence

## Purpose

Advisory preorder layer on P74-01 release monitoring. Does **not** place orders, modify retailer carts, charge payments, or auto-create inventory.

## Scoring rules (priority 0–100)

Weighted blend of:

- P61/P62 `recommendation_score` and `demand_score` (via `issue_intelligence_scores`)
- #1 issue, key signals, variant/ratio opportunity
- Watchlist match (P50-02)
- P70 market trend coverage (summary strength)
- FOC proximity (7/14 day boosts)
- Penalty for high owned + ordered counts (budget placeholder neutral)

Actions:

| Score | Action |
|-------|--------|
| ≥ 85 | MUST_BUY |
| ≥ 70 | BUY |
| ≥ 50 | WATCH |
| < 50 | PASS |

## Quantity rules

- PASS → 0
- WATCH → 1
- BUY → default 2 when priority ≥ 75
- MUST_BUY → base 3, capped with demand/#1/FOC boosts to 4+
- Reduces when owned + ordered already covers recommendation

## FOC definitions

| Bucket | Rule |
|--------|------|
| FOC_THIS_WEEK | 0–7 days |
| FOC_NEXT_WEEK | 8–14 days |
| FOC_WITHIN_30_DAYS | 15–30 days |
| FOC_MISSED | foc_date < today |
| FOC_UNKNOWN | missing or > 30 days |

## Recommendation changes

Compares latest stored `p74_purchase_recommendation` per issue before each snapshot:

- **NEW** — first recommendation
- **UPGRADED** — higher action rank or quantity
- **DOWNGRADED** — lower action or quantity
- **UNCHANGED** — not persisted to change feed

## APIs

| GET | Path |
|-----|------|
| `/api/v1/release-monitoring/foc` | FOC bucket counts |
| `/api/v1/release-monitoring/purchase-recommendations` | Current preorder rows |
| `/api/v1/release-monitoring/recommendation-changes` | Upgrade/downgrade events |
| `/api/v1/release-monitoring/foc-dashboard` | Alert center payload |

## Known limitations

- Ordered quantity uses pull-list issue links, not retailer cart sync.
- Owned quantity uses collection run counts, not per-issue inventory matching.
- Does not invoke P53 quantity engine directly; P74-02 uses its own advisory rules.
- Second snapshot without material input change may produce few change events.

## Verification

```bash
pytest tests/test_foc_purchase_intelligence.py -v
pytest tests/test_quantity_recommendation.py -v
pytest tests/test_recommendation_change_detection.py -v
pytest tests/test_foc_dashboard.py -v
pytest tests/test_purchase_priority_scoring.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
