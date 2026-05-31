# Recommendation Intelligence Certification Report (P51-05)

## Scope

Certifies Phase 51 (P51-01 through P51-04) for **advisory** recommendation use. Closeout services do not modify recommendation scoring, Lunar imports, release intelligence logic, inventory, orders, or marketplace behavior.

## Certification criteria

Certification is **never** granted because P51-05 code exists. It requires **live P51-04 output** for the owner:

- At least one **completed** V2 run with `recommendations_created > 0`
- Latest issue-level V2 scores, score components, and decision/explanation rows
- Validation overall status PASS or WARNING (not FAIL)
- Health overall status not FAILED
- Quality calibration not FAIL
- V1 spec recommendations preserved

Status remains **`NOT_READY`** until the above is true (including owner 40 live catalog validation).

Approval tiers:

- **`APPROVED_FOR_RECOMMENDATION_USE`** — validation PASS, calibration PASS, health HEALTHY, live V2 gates pass
- **`APPROVED_WITH_WARNINGS`** — live V2 gates pass with validation/health/calibration warnings only
- **`NOT_READY`** — missing live V2 output, calibration FAIL, validation FAIL, or health FAILED

## Certification statuses

| Status | Meaning |
|--------|---------|
| `APPROVED_FOR_RECOMMENDATION_USE` | All gates passed |
| `APPROVED_WITH_WARNINGS` | Certified with validation/calibration warnings |
| `NOT_READY` | One or more blocking checks failed |

## Version

- Certification version: **P51-05**
- Alembic head at closeout: **20260821_0171** (Recommendation V2 tables; P51-05 adds no schema migration)

## Operator checklist

1. Run V2 recommendation run for target owner.
2. Open `/recommendation-intelligence-certification` or call certification API.
3. Confirm readiness score and tier distribution in summary.
4. Review V1 vs V2 movement counts in summary.
5. Archive certification JSON for audit.

## Deferred enhancements

See `docs/TECH_DEBT.md` — P51 deferred items (live sales feeds, graded outcomes, licensed demand data, ML retraining).
