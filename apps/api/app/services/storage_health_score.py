"""P79-03 composite storage health score (0-100)."""

from __future__ import annotations

HIGH_VALUE_FMV = 75.0


def compute_storage_health_score(
    *,
    total_copies: int,
    assigned_count: int,
    audit_accuracy_pct: float,
    over_capacity_boxes: int,
    high_value_unassigned: int,
    duplicate_assignments: int,
    missing_books: int,
) -> tuple[int, str, dict[str, float | int]]:
    if total_copies <= 0:
        coverage = 100.0
    else:
        coverage = assigned_count / total_copies * 100.0

    score = 100.0
    score -= max(0.0, 100.0 - coverage) * 0.35
    score -= max(0.0, 100.0 - audit_accuracy_pct) * 0.2
    score -= min(30.0, over_capacity_boxes * 8)
    score -= min(25.0, high_value_unassigned * 5)
    score -= min(20.0, duplicate_assignments * 4)
    score -= min(15.0, missing_books * 3)

    final = int(max(0, min(100, round(score))))
    if final >= 85:
        status = "HEALTHY"
    elif final >= 65:
        status = "WATCH"
    else:
        status = "AT_RISK"

    factors = {
        "assignment_coverage_pct": round(coverage, 1),
        "audit_accuracy_pct": round(audit_accuracy_pct, 1),
        "over_capacity_boxes": over_capacity_boxes,
        "high_value_unassigned": high_value_unassigned,
        "duplicate_assignments": duplicate_assignments,
        "missing_books": missing_books,
    }
    return final, status, factors
