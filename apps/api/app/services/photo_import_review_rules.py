"""P100-12 review / confirm eligibility rules."""

from __future__ import annotations

from app.models.photo_import import RECOGNITION_STATUS_AMBIGUOUS, PhotoImportCandidate, PhotoImportDetectedBook

MATCH_SCORE_CONFIRM_THRESHOLD = 70.0
AI_CONFIDENCE_CONFIRM_THRESHOLD = 0.75


def detection_has_catalog_match(det: PhotoImportDetectedBook) -> bool:
    return det.selected_catalog_issue_id is not None


def can_confirm_detection(
    det: PhotoImportDetectedBook,
    *,
    best_candidate: PhotoImportCandidate | None,
) -> bool:
    if det.selected_catalog_issue_id is None:
        return False
    if det.recognition_status == RECOGNITION_STATUS_AMBIGUOUS:
        return False
    return True


def qualifies_for_bulk_high_confidence_confirm(
    det: PhotoImportDetectedBook,
    *,
    best_candidate: PhotoImportCandidate | None,
) -> bool:
    if not can_confirm_detection(det, best_candidate=best_candidate):
        return False
    if best_candidate is None:
        return False
    ai_conf = float(det.ai_confidence or 0.0)
    if ai_conf < AI_CONFIDENCE_CONFIRM_THRESHOLD:
        return False
    if float(best_candidate.match_score) < MATCH_SCORE_CONFIRM_THRESHOLD:
        return False
    if det.recognition_status == RECOGNITION_STATUS_AMBIGUOUS:
        return False
    # Unknown-issue, fuzzy-only, and weak-subtitle series matches always require manual selection.
    from app.services.photo_import_candidate_service import NON_AUTO_CONFIRM_MATCHED_ON

    if (best_candidate.matched_on or "") in NON_AUTO_CONFIRM_MATCHED_ON:
        return False
    return True
