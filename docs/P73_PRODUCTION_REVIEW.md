# P73 Recommendation Feedback Platform — Production Review

## Status

**APPROVED_FOR_PRODUCTION**

| Phase | Scope | Status |
|-------|--------|--------|
| P73-01 | Outcome tracking & events | COMPLETE |
| P73-02 | Performance analytics | COMPLETE |
| P73-03 | Feedback intelligence & certification | COMPLETE |

## Architecture

The platform is a **read-only feedback loop** layered on recommendation outcomes:

1. **P73-01** — `p73_recommendation_outcome` and `p73_recommendation_action_event` capture lifecycle events without altering recommendation generation.
2. **P73-02** — `recommendation_analytics_service` aggregates funnel, adoption, profitability, and category metrics into performance snapshots.
3. **P73-03** — `recommendation_feedback_engine` combines outcomes, P73 analytics, P70 market refresh signals, and P72 grading outcomes to produce confidence, calibration, and effectiveness snapshots.

No external ML services are used. Scoring is deterministic and explainable.

## Feedback lifecycle

```
Recommendation issued (external engines)
        ↓
Outcome row created (P73-01)
        ↓
User / workflow events appended
        ↓
Analytics & intelligence snapshots (P73-02 / P73-03)
        ↓
Certification gate (production review)
```

## Confidence scoring

`recommendation_confidence_service` produces **0–100** scores per type (`BUY`, `GRADE`, `SELL`, `WATCH`) from:

- Category success rates and sample depth
- Observed ROI by type
- Attribution match rate
- Optional boosts from P70 FMV trend coverage and P72 grading hit rates

Scores inform operators; they **do not** auto-adjust live recommendation rankings.

## Calibration methodology

Seven calibration categories are tracked: First Appearance, Key Issue, Variant, Creator, Publisher Event, Milestone Issue, Franchise Expansion. For each: count, success rate, average ROI, median ROI.

## Known limitations

- Profit/ROI on outcomes requires explicit fields or event metadata.
- P70/P72 context is summary-level (counts and aggregates), not per-recommendation fusion.
- Each dashboard build writes new snapshot rows (no daily deduplication).
- Empty outcome history yields neutral confidence (~50) rather than high certainty.

## Future learning opportunities

- Deeper joins from linked `inventory_copy_id` to authoritative FMV and grading ROI.
- Time-windowed calibration (rolling 90-day).
- Operator-approved threshold tuning stored as configuration (still non-autonomous).

## Certification

Run `GET /api/v1/recommendation-feedback/certification` or `run_recommendation_feedback_certification()` to validate outcome tracking, analytics, confidence, calibration, effectiveness, dashboard build, and data integrity.

## Verification

```bash
pytest tests/test_recommendation_confidence.py -v
pytest tests/test_recommendation_calibration.py -v
pytest tests/test_recommendation_effectiveness.py -v
pytest tests/test_recommendation_feedback_dashboard.py -v
pytest tests/test_p73_production_review.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
