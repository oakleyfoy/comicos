from __future__ import annotations

from app.services.recognition.catalog_matcher import CatalogFingerprintMatch
from app.services.recognition.recognition_types import RecognitionOCRSignal, RecognitionResult
from app.services.recognition.trust_calibration import (
    apply_trust_calibration,
    classify_visual_match_strength,
    ocr_supports_catalog_match,
    user_facing_confidence_from_fingerprint,
)


def test_classify_visual_match_strength_tiers() -> None:
    assert classify_visual_match_strength(0.98) == "exact"
    assert classify_visual_match_strength(0.95) == "exact"
    assert classify_visual_match_strength(0.86) == "possible"
    assert classify_visual_match_strength(0.80) == "possible"
    assert classify_visual_match_strength(0.79) == "weak"


def test_weak_fingerprint_without_ocr_capped_below_high_confidence() -> None:
    display = user_facing_confidence_from_fingerprint(0.86, ocr_supports=False, collision_peers=0)
    assert display <= 0.70
    assert display < 0.83


def test_possible_fingerprint_never_displays_as_eighty_three_percent() -> None:
    display = user_facing_confidence_from_fingerprint(0.8428, ocr_supports=False, collision_peers=0)
    assert display <= 0.70


def test_collision_peers_reduce_confidence() -> None:
    base = user_facing_confidence_from_fingerprint(0.86, ocr_supports=True, collision_peers=0)
    crowded = user_facing_confidence_from_fingerprint(0.86, ocr_supports=True, collision_peers=8)
    assert crowded < base


def test_apply_trust_calibration_keeps_exact_match() -> None:
    result = RecognitionResult(
        bucket="VERIFIED",
        confidence=0.98,
        series="Venom",
        issue_number="1",
        variant=None,
        publisher="Marvel",
        release_date=None,
        cover_image_url=None,
        candidate_count=1,
        catalog_issue_id=6327,
        winning_source="catalog_image_fingerprint",
        catalog_fingerprint_score=0.98,
        final_confidence=0.98,
    )
    ocr = RecognitionOCRSignal(
        raw_text="Lov#166",
        normalized_text="lov#166",
        title=None,
        issue_number="166",
        publisher="Marvel",
        variant=None,
        confidence=0.65,
    )
    calibrated = apply_trust_calibration(result, catalog_matches=[], ocr=ocr)
    assert calibrated.bucket == "VERIFIED"
    assert calibrated.confidence >= 0.95
    assert calibrated.visual_match_strength == "exact"
    assert calibrated.recognition_guidance == "Matched by cover image."


def test_apply_trust_calibration_review_copy_for_possible_match() -> None:
    matches = [
        CatalogFingerprintMatch(issue_id=6328, image_id=6328, confidence=0.8602, min_hamming_distance=19),
    ]
    result = RecognitionResult(
        bucket="REVIEW",
        confidence=0.88,
        series="Venom",
        issue_number="2",
        variant=None,
        publisher="Marvel",
        release_date=None,
        cover_image_url=None,
        candidate_count=1,
        catalog_issue_id=6328,
        winning_source="catalog_image_fingerprint",
        catalog_fingerprint_score=0.8602,
        final_confidence=0.88,
    )
    ocr = RecognitionOCRSignal(
        raw_text="MARVEL",
        normalized_text="marvel",
        title=None,
        issue_number="166",
        publisher="Marvel",
        variant=None,
        confidence=0.65,
    )
    calibrated = apply_trust_calibration(result, catalog_matches=matches, ocr=ocr)
    assert calibrated.bucket == "REVIEW"
    assert calibrated.confidence <= 0.70
    assert calibrated.recognition_guidance == "Possible visual match — please review"


def test_ocr_supports_series_name() -> None:
    ocr = RecognitionOCRSignal(
        raw_text="VENOM #1",
        normalized_text="venom #1",
        title="VENOM",
        issue_number="1",
        publisher="Marvel",
        variant=None,
        confidence=0.8,
    )
    assert ocr_supports_catalog_match(ocr, series="Venom", issue_number="1")
