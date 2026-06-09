from __future__ import annotations

from app.services.recognition.recognition_types import RecognitionBucket


def bucket_for_confidence(confidence: float) -> RecognitionBucket:
    if confidence >= 0.95:
        return "VERIFIED"
    if confidence >= 0.70:
        return "REVIEW"
    return "UNKNOWN"


def combine_confidence(
    *,
    image_confidence: float,
    ocr_confidence: float,
    title_match_confidence: float,
    issue_match_confidence: float,
) -> float:
    """Blend image, OCR, and catalog evidence into a single deterministic score."""

    candidate_confidence = (
        (0.60 * max(0.0, min(title_match_confidence, 1.0)))
        + (0.30 * max(0.0, min(issue_match_confidence, 1.0)))
        + 0.10 * max(0.0, min((title_match_confidence + issue_match_confidence) / 2.0, 1.0))
    )
    combined = (
        0.05 * max(0.0, min(image_confidence, 1.0))
        + 0.05 * max(0.0, min(ocr_confidence, 1.0))
        + 0.90 * candidate_confidence
    )
    if title_match_confidence >= 0.98 and issue_match_confidence >= 0.98:
        combined += 0.05
    elif title_match_confidence >= 0.90 and issue_match_confidence >= 0.50:
        combined += 0.02
    return round(max(0.0, min(combined, 1.0)), 6)

