from __future__ import annotations

from typing import Any

RUBRIC_VERSION = "PSA-SUPPORT-v1"

CATEGORY_WEIGHTING: dict[str, float] = {
    "SPINE": 1.0,
    "CORNERS": 0.9,
    "EDGES": 0.9,
    "SURFACE": 1.0,
    "STRUCTURE": 1.15,
    "PRESENTATION": 0.75,
    "OVERALL_SUPPORT": 1.25,
}

SUPPORT_BANDS: tuple[dict[str, Any], ...] = (
    {"label": "9.8-10.0 support", "low": 9.8, "high": 10.0, "max_score": 0.12, "status": "STRONG"},
    {"label": "9.4-9.6 support", "low": 9.4, "high": 9.6, "max_score": 0.26, "status": "STRONG"},
    {"label": "9.0-9.2 support", "low": 9.0, "high": 9.2, "max_score": 0.42, "status": "ACCEPTABLE"},
    {"label": "8.0-8.5 support", "low": 8.0, "high": 8.5, "max_score": 0.62, "status": "LIMITED"},
    {"label": "7.0-7.5 support", "low": 7.0, "high": 7.5, "max_score": 0.82, "status": "LIMITED"},
    {"label": "below-7 review support", "low": 0.0, "high": 6.5, "max_score": 99.0, "status": "REVIEW_REQUIRED"},
)

PRESSURE_SCORES = {"NONE": 0.0, "LOW": 0.2, "MODERATE": 0.45, "HIGH": 0.7, "SEVERE": 0.95}
SEVERITY_SCORES = {"MINOR": 0.15, "MODERATE": 0.45, "MAJOR": 0.8}
QUALITY_ISSUE_SCORES = {
    "LOW_RESOLUTION": 0.42,
    "LOW_DPI": 0.42,
    "EXCESSIVE_BLUR": 0.58,
    "EXCESSIVE_GLARE": 0.5,
    "OVEREXPOSED_IMAGE": 0.42,
    "UNDEREXPOSED_IMAGE": 0.42,
    "INSUFFICIENT_CONTRAST": 0.42,
    "QUALITY_GATE_FAILED": 0.6,
    "INSUFFICIENT_IMAGE_QUALITY": 0.68,
    "LOW_CLUSTER_CONFIDENCE": 0.36,
    "GEOMETRY_CONFLICT": 0.4,
    "OVERLAPPING_REGION_CONFLICT": 0.4,
}

REVIEW_REQUIRED_THRESHOLDS = {
    "category_mean_confidence_floor": 0.38,
    "major_structure_requires_review": True,
    "scan_quality_issue_score": 0.5,
    "mixed_cluster_ratio": 0.34,
}


def pressure_hint_from_inputs(*, severity_hint: str, confidence_score: float, weight: float = 1.0) -> str:
    base = SEVERITY_SCORES.get(str(severity_hint), 0.15)
    score = base * max(0.3, min(1.0, float(confidence_score) + 0.1)) * max(0.5, weight)
    if score >= 0.72:
        return "SEVERE"
    if score >= 0.52:
        return "HIGH"
    if score >= 0.32:
        return "MODERATE"
    if score >= 0.12:
        return "LOW"
    return "NONE"


def score_from_pressure(pressure_hint: str) -> float:
    return PRESSURE_SCORES.get(str(pressure_hint), 0.0)


def quality_issue_score(issue_type: str) -> float:
    return QUALITY_ISSUE_SCORES.get(str(issue_type), 0.25)


def support_band_for_score(*, normalized_score: float, review_required: bool, insufficient_evidence: bool) -> dict[str, Any]:
    if insufficient_evidence:
        return {
            "label": "below-7 review support",
            "low": 0.0,
            "high": 6.5,
            "status": "INSUFFICIENT_EVIDENCE",
        }
    adjusted = normalized_score + (0.08 if review_required else 0.0)
    for band in SUPPORT_BANDS:
        if adjusted <= float(band["max_score"]):
            status = "REVIEW_REQUIRED" if review_required else str(band["status"])
            return {"label": band["label"], "low": band["low"], "high": band["high"], "status": status}
    fallback = SUPPORT_BANDS[-1]
    return {"label": fallback["label"], "low": fallback["low"], "high": fallback["high"], "status": "REVIEW_REQUIRED"}


def summarize_category_status(*, support_band_status: str, review_required: bool) -> str:
    if review_required:
        return "REVIEW_REQUIRED"
    return support_band_status
