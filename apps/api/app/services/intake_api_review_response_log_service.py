"""Log intake review API payloads — identify fingerprint suggestion source (no logic changes)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.intake_queue import IntakeSessionItem

logger = logging.getLogger(__name__)

_LOG_TAG = "INTAKE_API_REVIEW_RESPONSE"


def _count_review_tops(container: dict[str, Any] | None) -> int | None:
    if not container:
        return None
    tops = container.get("needs_review_top_candidates")
    if isinstance(tops, list):
        return len(tops)
    return None


def _gap_diagnosis_view(barcode_read: dict[str, Any] | None) -> dict[str, Any]:
    """Best-effort view of worker gap diagnosis fields persisted on the item."""
    if not barcode_read:
        return {}
    explicit = barcode_read.get("gap_diagnosis")
    if isinstance(explicit, dict):
        return explicit
    barcode_gap = barcode_read.get("barcode_gap")
    bg = barcode_gap if isinstance(barcode_gap, dict) else {}
    recovery_hints = bg.get("recovery_hints") if isinstance(bg.get("recovery_hints"), dict) else {}
    full_cover = (
        barcode_read.get("full_cover_required")
        or barcode_read.get("needs_full_cover_photo")
        or bg.get("full_cover_followup_required")
        or bg.get("needs_full_cover_photo")
    )
    region_safe = barcode_read.get("fingerprint_region_safe")
    if region_safe is None:
        region_safe = recovery_hints.get("fingerprint_region_safe")
    if region_safe is None:
        region_safe = bg.get("fingerprint_region_safe")
    region_kind = barcode_read.get("fingerprint_image_region")
    if region_kind is None:
        region_kind = recovery_hints.get("fingerprint_image_region")
    if region_kind is None:
        region_kind = bg.get("fingerprint_image_region")
    return {
        "review_decision": bg.get("review_decision"),
        "full_cover_followup_required": bool(full_cover) if full_cover is not None else None,
        "needs_review_top_candidates_count": _count_review_tops(bg),
        "fingerprint_region_safe": region_safe,
        "fingerprint_image_region": region_kind,
        "needs_full_cover_photo": barcode_read.get("needs_full_cover_photo"),
    }


def _ui_fingerprint_candidate_source(
    *,
    item_status: str,
    barcode_read: dict[str, Any] | None,
    db_candidate_count: int,
    db_fingerprint_candidate_count: int,
) -> str:
    """Mirror ``intakeFingerprintReviewCandidates`` in IntakeReviewPage.tsx."""
    if item_status == "needs_full_cover_photo":
        return "none_suppressed_needs_full_cover_photo"
    if barcode_read and barcode_read.get("needs_full_cover_photo") is True:
        return "none_suppressed_needs_full_cover_photo"
    bg = barcode_read.get("barcode_gap") if barcode_read else None
    if isinstance(bg, dict):
        tops = bg.get("needs_review_top_candidates")
        if isinstance(tops, list) and len(tops) > 0:
            return "barcode_gap.needs_review_top_candidates"
    if db_fingerprint_candidate_count > 0:
        return "IntakeItemCandidate_rows"
    return "none"


def log_intake_item_api_response(
    item: IntakeSessionItem,
    *,
    db_candidates: list[Any],
    barcode_read: dict[str, Any] | None,
) -> None:
    """Emit structured log immediately before returning ``IntakeItemRead`` to the client."""
    intake_item_id = int(item.id or 0)
    db_count = len(db_candidates)
    db_fp_count = sum(1 for c in db_candidates if str(getattr(c, "source", "") or "") == "fingerprint")
    gap_view = _gap_diagnosis_view(barcode_read)
    barcode_gap = barcode_read.get("barcode_gap") if barcode_read else None
    bg_dict = barcode_gap if isinstance(barcode_gap, dict) else None
    ui_source = _ui_fingerprint_candidate_source(
        item_status=str(item.status or ""),
        barcode_read=barcode_read,
        db_candidate_count=db_count,
        db_fingerprint_candidate_count=db_fp_count,
    )
    payload = {
        "intake_item_id": intake_item_id,
        "item_status": item.status,
        "gap_diagnosis_review_decision": gap_view.get("review_decision"),
        "gap_diagnosis_full_cover_followup_required": gap_view.get("full_cover_followup_required"),
        "gap_diagnosis_needs_review_top_candidates_count": gap_view.get("needs_review_top_candidates_count"),
        "gap_diagnosis_fingerprint_region_safe": gap_view.get("fingerprint_region_safe"),
        "gap_diagnosis_fingerprint_image_region": gap_view.get("fingerprint_image_region"),
        "barcode_gap_needs_review_top_candidates_count": _count_review_tops(bg_dict),
        "intake_item_candidate_db_count": db_count,
        "intake_item_candidate_db_fingerprint_count": db_fp_count,
        "ui_fingerprint_suggestions_source": ui_source,
        "ui_uses_barcode_gap_for_fingerprint_suggestions": ui_source
        == "barcode_gap.needs_review_top_candidates",
        "ui_uses_intake_item_candidate_rows_for_fingerprint_suggestions": ui_source
        == "IntakeItemCandidate_rows",
    }
    logger.info("%s %s", _LOG_TAG, json.dumps(payload, default=str))
