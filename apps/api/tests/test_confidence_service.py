from __future__ import annotations

from app.services.recognition.confidence_service import bucket_for_confidence, combine_confidence


def test_bucket_assignment_thresholds() -> None:
    assert bucket_for_confidence(0.95) == "VERIFIED"
    assert bucket_for_confidence(0.949) == "REVIEW"
    assert bucket_for_confidence(0.70) == "REVIEW"
    assert bucket_for_confidence(0.699) == "UNKNOWN"


def test_combine_confidence_rewards_consistent_signals() -> None:
    exact = combine_confidence(
        image_confidence=0.95,
        ocr_confidence=0.92,
        title_match_confidence=1.0,
        issue_match_confidence=1.0,
    )
    weak = combine_confidence(
        image_confidence=0.20,
        ocr_confidence=0.15,
        title_match_confidence=0.10,
        issue_match_confidence=0.05,
    )
    assert exact > 0.95
    assert weak < 0.70

