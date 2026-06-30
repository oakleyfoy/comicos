"""Full front-cover follow-up when barcode reads but catalog/GCD barcode paths miss on UPC crops."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.intake_queue import IntakeSessionItem
from app.services.intake_fingerprint_image_region_service import (
    FingerprintRegionAssessment,
    REGION_FULL_COVER,
    merge_fingerprint_region_instrumentation,
)
from app.services.photo_import_storage_service import REPO_ROOT, resolve_photo_import_storage_path

FULL_COVER_REASON_CODE = "needs_full_cover_photo"
FULL_COVER_USER_MESSAGE = (
    "Barcode was read, but no barcode record exists in GCD or your catalog. "
    "Add a full front-cover photo to identify by cover art."
)


def _parse_barcode_read(item: IntakeSessionItem) -> dict[str, Any]:
    raw = item.barcode_read_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def intake_has_full_cover_followup_image(item: IntakeSessionItem) -> bool:
    payload = _parse_barcode_read(item)
    rel = str(payload.get("full_cover_storage_path") or "").strip()
    if not rel:
        return False
    path = resolve_photo_import_storage_path(rel, image_id=int(item.id or 0))
    return path.is_file()


def resolve_intake_recognition_image_path(
    item: IntakeSessionItem,
    primary_path: Path,
) -> tuple[Path, bool]:
    """Return path used for OCR / cover fingerprint (full-cover follow-up when present)."""
    payload = _parse_barcode_read(item)
    rel = str(payload.get("full_cover_storage_path") or "").strip()
    if rel:
        follow = resolve_photo_import_storage_path(rel, image_id=int(item.id or 0))
        if follow.is_file():
            return follow, True
    return primary_path, False


from app.services.intake_scanner_barcode_authority_service import p106_gap_is_exact_barcode_authority


def gcd_barcode_lookup_missed(gap_diag: dict[str, Any] | None) -> bool:
    """True when GCD has no attachable exact barcode hit for this scan (P106.1 metadata pool does not count)."""
    if gap_diag is None:
        return True
    if gap_diag.get("ready_to_auto_import"):
        return False
    if p106_gap_is_exact_barcode_authority(gap_diag):
        return False
    if int(gap_diag.get("gcd_sql_exact_barcode_column_count") or 0) > 0:
        return False
    reason = str(gap_diag.get("reason") or gap_diag.get("final_reason") or "")
    if reason in {"no_gcd_barcode_match", "gcd_database_missing"}:
        return True
    if int(gap_diag.get("gcd_match_count") or 0) == 0:
        return True
    if gap_diag.get("recovery_stage") and not gap_diag.get("ready_to_auto_import"):
        return True
    return False


def should_require_full_cover_followup(
    *,
    gap_diag: dict[str, Any] | None,
    primary_region: FingerprintRegionAssessment,
    recognition_region: FingerprintRegionAssessment,
    has_full_cover_image: bool,
    local_catalog_hit: bool,
    p106_exact_barcode_authority: bool,
    barcode_decoded: bool,
) -> bool:
    if not barcode_decoded:
        return False
    if has_full_cover_image:
        return False
    if local_catalog_hit:
        return False
    if p106_exact_barcode_authority:
        return False
    if not gcd_barcode_lookup_missed(gap_diag):
        return False
    if (
        recognition_region.fingerprint_image_region == REGION_FULL_COVER
        and recognition_region.fingerprint_region_safe
        and primary_region.fingerprint_image_region == REGION_FULL_COVER
        and primary_region.fingerprint_region_safe
    ):
        return False
    if not recognition_region.fingerprint_region_safe:
        return True
    if not primary_region.fingerprint_region_safe:
        return True
    return False


def apply_full_cover_followup_to_diagnosis(
    diagnosis: dict[str, Any],
    primary_region: FingerprintRegionAssessment,
    *,
    recognition_region: FingerprintRegionAssessment | None = None,
) -> None:
    diagnosis.pop("needs_review_top_candidates", None)
    diagnosis.pop("fingerprint_review", None)
    diagnosis.pop("comicvine_review_candidate", None)
    diagnosis.pop("review_decision", None)
    diagnosis["needs_full_cover_photo"] = True
    diagnosis["review_reason"] = FULL_COVER_REASON_CODE
    diagnosis["ready_to_auto_import"] = False
    merge_fingerprint_region_instrumentation(diagnosis, primary_region)
    if recognition_region is not None:
        diagnosis["recognition_fingerprint_image_region"] = recognition_region.fingerprint_image_region
        diagnosis["recognition_fingerprint_region_safe"] = recognition_region.fingerprint_region_safe
    if not diagnosis.get("fingerprint_suppressed_reason"):
        diagnosis["fingerprint_suppressed_reason"] = (
            recognition_region.fingerprint_suppressed_reason
            if recognition_region and recognition_region.fingerprint_suppressed_reason
            else primary_region.fingerprint_suppressed_reason or "unsafe_crop"
        )


def merge_full_cover_flags_into_barcode_read(
    barcode_read_json: str | None,
    *,
    gap_diag: dict[str, Any] | None = None,
) -> str:
    payload = {}
    if barcode_read_json:
        try:
            parsed = json.loads(barcode_read_json)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    if gap_diag and gap_diag.get("needs_full_cover_photo"):
        payload["needs_full_cover_photo"] = True
        payload["full_cover_required"] = True
        for key in (
            "fingerprint_image_region",
            "fingerprint_region_safe",
            "fingerprint_suppressed_reason",
        ):
            if key in gap_diag:
                payload[key] = gap_diag[key]
    return json.dumps(payload)


def full_cover_storage_path_for_primary(primary_path: Path) -> Path:
    return primary_path.parent / f"{primary_path.stem}_fullcover.jpg"


def relative_full_cover_storage_path(primary_relative: str) -> str:
    primary = resolve_photo_import_storage_path(primary_relative)
    dest = full_cover_storage_path_for_primary(primary)
    return str(dest.relative_to(REPO_ROOT)).replace("\\", "/")
