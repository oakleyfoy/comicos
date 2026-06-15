from __future__ import annotations

from dataclasses import replace

from app.services.recognition.catalog_matcher import CatalogFingerprintMatch
from app.services.recognition.recognition_types import RecognitionBucket, RecognitionOCRSignal, RecognitionResult
from app.services.import_catalog_resolution_service import issue_number_variants

VisualMatchStrength = str

STRONG_VISUAL_THRESHOLD = 0.95
POSSIBLE_VISUAL_MIN = 0.80
USER_HIGH_CONFIDENCE_CEILING = 0.70
MAX_REVIEW_FINGERPRINT_DISPLAY = 0.69

CONFIDENCE_BAND_TOLERANCE = 0.012
COLLISION_PEER_SOFT = 4
COLLISION_PEER_STRONG = 8


def classify_visual_match_strength(catalog_fingerprint_score: float) -> VisualMatchStrength:
    if catalog_fingerprint_score >= STRONG_VISUAL_THRESHOLD:
        return "exact"
    if catalog_fingerprint_score >= POSSIBLE_VISUAL_MIN:
        return "possible"
    if catalog_fingerprint_score > 0.0:
        return "weak"
    return "none"


def count_confidence_band_peers(
    catalog_matches: list[CatalogFingerprintMatch],
    *,
    top_score: float,
    top_issue_id: int | None,
) -> int:
    if top_score < POSSIBLE_VISUAL_MIN:
        return 0
    peers = 0
    for match in catalog_matches:
        if top_issue_id is not None and match.issue_id == top_issue_id:
            continue
        if abs(match.confidence - top_score) <= CONFIDENCE_BAND_TOLERANCE:
            peers += 1
    return peers


def ocr_supports_catalog_match(
    ocr: RecognitionOCRSignal,
    *,
    series: str | None,
    issue_number: str | None,
) -> bool:
    if not series and not issue_number:
        return False
    haystacks = [ocr.raw_text or "", ocr.normalized_text or "", ocr.title or ""]
    joined = " ".join(h for h in haystacks if h).lower()
    if series and series.strip().lower() in joined:
        return True
    if issue_number and ocr.issue_number:
        expected = set(issue_number_variants(issue_number))
        observed = set(issue_number_variants(ocr.issue_number))
        if expected & observed:
            return True
    return False


def recognition_guidance_for_match(
    *,
    bucket: RecognitionBucket,
    visual_strength: VisualMatchStrength,
    winning_source: str,
) -> str | None:
    if winning_source == "catalog_image_fingerprint" and visual_strength == "exact":
        return "Matched by cover image."
    if bucket == "REVIEW" and winning_source == "catalog_image_fingerprint" and visual_strength in {"possible", "weak"}:
        return "Possible visual match — please review"
    if bucket == "REVIEW" and visual_strength in {"possible", "weak"}:
        return "Possible visual match — please review"
    return None


def user_facing_confidence_from_fingerprint(
    catalog_fingerprint_score: float,
    *,
    ocr_supports: bool,
    collision_peers: int,
) -> float:
    if catalog_fingerprint_score >= STRONG_VISUAL_THRESHOLD:
        return catalog_fingerprint_score

    if catalog_fingerprint_score >= POSSIBLE_VISUAL_MIN:
        display = 0.42 + (catalog_fingerprint_score - POSSIBLE_VISUAL_MIN) * 1.5
    else:
        display = 0.22 + catalog_fingerprint_score * 0.45

    if not ocr_supports:
        display = min(display, USER_HIGH_CONFIDENCE_CEILING)

    if collision_peers >= COLLISION_PEER_STRONG:
        display *= 0.75
    elif collision_peers >= COLLISION_PEER_SOFT:
        display *= 0.88

    display = min(display, MAX_REVIEW_FINGERPRINT_DISPLAY)
    return round(max(0.0, display), 6)


def bucket_for_calibrated_fingerprint(
    catalog_fingerprint_score: float,
    user_confidence: float,
) -> RecognitionBucket:
    if catalog_fingerprint_score >= STRONG_VISUAL_THRESHOLD:
        return "VERIFIED"
    if user_confidence >= 0.40:
        return "REVIEW"
    return "UNKNOWN"


def apply_trust_calibration(
    result: RecognitionResult,
    *,
    catalog_matches: list[CatalogFingerprintMatch],
    ocr: RecognitionOCRSignal,
) -> RecognitionResult:
    visual_strength = classify_visual_match_strength(result.catalog_fingerprint_score)
    top_issue_id = catalog_matches[0].issue_id if catalog_matches else result.catalog_issue_id
    collision_peers = count_confidence_band_peers(
        catalog_matches,
        top_score=result.catalog_fingerprint_score,
        top_issue_id=top_issue_id,
    )
    ocr_supports = ocr_supports_catalog_match(
        ocr,
        series=result.series,
        issue_number=result.issue_number,
    )

    if result.catalog_fingerprint_score >= STRONG_VISUAL_THRESHOLD and result.winning_source == "catalog_image_fingerprint":
        return replace(
            result,
            confidence=result.catalog_fingerprint_score,
            final_confidence=result.catalog_fingerprint_score,
            bucket="VERIFIED",
            visual_match_strength=visual_strength,
            recognition_guidance="Matched by cover image.",
        )

    fingerprint_led = result.winning_source == "catalog_image_fingerprint" and result.catalog_fingerprint_score > 0.0
    if fingerprint_led or (result.catalog_issue_id and result.catalog_fingerprint_score >= POSSIBLE_VISUAL_MIN):
        user_confidence = user_facing_confidence_from_fingerprint(
            result.catalog_fingerprint_score,
            ocr_supports=ocr_supports,
            collision_peers=collision_peers,
        )
        bucket = bucket_for_calibrated_fingerprint(result.catalog_fingerprint_score, user_confidence)
        guidance = recognition_guidance_for_match(
            bucket=bucket,
            visual_strength=visual_strength,
            winning_source=result.winning_source,
        )
        return replace(
            result,
            confidence=user_confidence,
            final_confidence=user_confidence,
            bucket=bucket,
            visual_match_strength=visual_strength,
            recognition_guidance=guidance,
        )

    if not ocr_supports and result.confidence > USER_HIGH_CONFIDENCE_CEILING:
        capped = round(min(result.confidence, USER_HIGH_CONFIDENCE_CEILING), 6)
        bucket: RecognitionBucket = "REVIEW" if capped >= 0.40 else "UNKNOWN"
        return replace(
            result,
            confidence=capped,
            final_confidence=capped,
            bucket=bucket,
            visual_match_strength=visual_strength,
            recognition_guidance=recognition_guidance_for_match(
                bucket=bucket,
                visual_strength=visual_strength,
                winning_source=result.winning_source,
            ),
        )

    return replace(
        result,
        visual_match_strength=visual_strength,
        recognition_guidance=recognition_guidance_for_match(
            bucket=result.bucket,
            visual_strength=visual_strength,
            winning_source=result.winning_source,
        ),
    )
