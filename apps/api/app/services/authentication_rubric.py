from __future__ import annotations

RUBRIC_VERSION = "AUTH-SUPPORT-v1"

STATUS_PRIORITY = {
    "SUPPORTS_AUTHENTICITY_REVIEW": 0,
    "NOT_APPLICABLE": 1,
    "INCONCLUSIVE": 2,
    "NEEDS_REVIEW": 3,
    "CONFLICT_DETECTED": 4,
}

REVIEW_PRIORITY_BY_STATUS = {
    "SUPPORTS_AUTHENTICITY_REVIEW": "LOW",
    "NOT_APPLICABLE": "LOW",
    "INCONCLUSIVE": "MEDIUM",
    "NEEDS_REVIEW": "HIGH",
    "CONFLICT_DETECTED": "CRITICAL",
}

LOW_CONFIDENCE_THRESHOLD = 0.45
CONFLICT_CONFIDENCE_THRESHOLD = 0.6
SUPPORT_CONFIDENCE_THRESHOLD = 0.72
LINEAGE_MINIMUM_CHECKS = 3
HISTORICAL_CONFLICT_THRESHOLD = 1


def status_for_confidence(*, confidence_score: float, has_conflict: bool = False, has_gap: bool = False) -> str:
    if has_conflict and confidence_score >= CONFLICT_CONFIDENCE_THRESHOLD:
        return "CONFLICT_DETECTED"
    if has_gap:
        return "NEEDS_REVIEW"
    if confidence_score >= SUPPORT_CONFIDENCE_THRESHOLD:
        return "SUPPORTS_AUTHENTICITY_REVIEW"
    if confidence_score >= LOW_CONFIDENCE_THRESHOLD:
        return "NEEDS_REVIEW"
    return "INCONCLUSIVE"


def review_priority_for_status(status: str) -> str:
    return REVIEW_PRIORITY_BY_STATUS.get(status, "MEDIUM")
