"""P105 comic barcode read: split decode/OCR, reconstruction, catalog recovery."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.catalog_master import CatalogUpc
from app.services.barcode_scan_consensus_service import (
    DEFAULT_MIN_VOTES,
    vote_barcode_reads,
)
from app.services.barcode_validation_service import (
    base_upc,
    supplement_extension,
    validate_barcode_catalog_match,
)
from app.services.catalog_ingestion_service import (
    direct_market_requires_supplement_key,
    upc_check_digit_valid,
)
from app.services import p105_comic_barcode_regions as _p105_regions
from app.services.p105_comic_barcode_regions import (
    BarcodeCropConfig,
    compute_barcode_region_geometry,
    crops_from_geometry,
    draw_region_overlay,
    pil_to_jpeg_bytes,
    save_barcode_region_debug_to_dir,
)
from app.services.p105_supplement_ocr import (
    OcrAttempt,
    SupplementCandidate,
    gather_ocr_attempts,
    hamming5,
    score_supplement_candidates,
)
from app.services.p105_supplement_ocr_consensus import (
    SupplementFrameRead,
    vote_supplement_digits,
)
from app.services.photo_import_fingerprint_service import (
    fingerprint_match_score_for_crop_path,
)
from app.services.p105_upc_addon_decoder import (
    UpAddonDecodeResult,
    addon_debug_crops,
    decode_upc_addon,
    write_addon_microscope_debug,
)
from app.services.photo_import_upc_barcode_decoder import collect_raw_upc_candidates_from_pil

logger = logging.getLogger(__name__)

RecoveryKind = Literal["raw", "merged", "inferred_catalog", "none"]

_LEFT_SUPPLEMENT_OCR_SYSTEM = (
    "Read ONLY the small 5-digit supplemental issue code printed to the LEFT of the main UPC bars "
    "on a US comic price box (e.g. 03921). Return JSON only: "
    '{"digits":"","confidence":0}. digits must be exactly 5 digits or empty — never guess.'
)
_LEFT_SUPPLEMENT_OCR_USER = "Read the 5-digit supplemental code digits only."

_RIGHT_DIGIT_OCR_SYSTEM = (
    "Read ONLY the single cover/version digit printed beside the UPC if visible. "
    'Return JSON only: {"digit":"","confidence":0}. digit is one digit or empty.'
)
_RIGHT_DIGIT_OCR_USER = "Read the single cover digit if printed."


@dataclass
class ComicBarcodeReadResult:
    raw_decoded_barcode: str = ""
    main_upc: str = ""
    left_supplement_ocr: str = ""
    decoded_supplement: str = ""
    ocr_supplement: str = ""
    corrected_supplement: str = ""
    final_supplement: str = ""
    supplement_disagreement: bool = False
    supplement_decode_method: str = ""
    supplement_decode_confidence: float = 0.0
    catalog_confirmed: bool = False
    fingerprint_confirmed: bool = False
    correction_reason: str = ""
    right_cover_digit_ocr: str = ""
    reconstructed_full: str = ""
    confidence_main: float = 0.0
    confidence_left: float = 0.0
    confidence_reconstructed: float = 0.0
    recovery_kind: RecoveryKind = "none"
    inferred_supplement: bool = False
    crop_expand_ratio: float = 0.12
    vote_count: int = 0
    review_reason: str = ""
    auto_match_allowed: bool = False
    region_debug_path: str = ""
    detection_method: str = "percentage"
    geometry_attempted: bool = False
    opencv_available: bool = False
    fallback_reason: str = ""
    geometry_rejection_reason: str = ""
    exception_message: str | None = None
    ocr_attempts: list[dict[str, Any]] = field(default_factory=list)
    supplement_candidates: list[dict[str, Any]] = field(default_factory=list)
    region_ocr_debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_decoded_barcode": self.raw_decoded_barcode,
            "main_upc": self.main_upc,
            "left_supplement_ocr": self.left_supplement_ocr,
            "decoded_supplement": self.decoded_supplement,
            "ocr_supplement": self.ocr_supplement,
            "corrected_supplement": self.corrected_supplement,
            "final_supplement": self.final_supplement,
            "supplement_disagreement": self.supplement_disagreement,
            "supplement_decode_method": self.supplement_decode_method,
            "supplement_decode_confidence": self.supplement_decode_confidence,
            "catalog_confirmed": self.catalog_confirmed,
            "fingerprint_confirmed": self.fingerprint_confirmed,
            "correction_reason": self.correction_reason,
            "right_cover_digit_ocr": self.right_cover_digit_ocr,
            "reconstructed_full": self.reconstructed_full,
            "confidence_main": self.confidence_main,
            "confidence_left": self.confidence_left,
            "confidence_reconstructed": self.confidence_reconstructed,
            "recovery_kind": self.recovery_kind,
            "inferred_supplement": self.inferred_supplement,
            "crop_expand_ratio": self.crop_expand_ratio,
            "vote_count": self.vote_count,
            "review_reason": self.review_reason,
            "auto_match_allowed": self.auto_match_allowed,
            "region_debug_path": self.region_debug_path,
            "detection_method": self.detection_method,
            "geometry_attempted": self.geometry_attempted,
            "opencv_available": self.opencv_available,
            "fallback_reason": self.fallback_reason,
            "geometry_rejection_reason": self.geometry_rejection_reason,
            "exception_message": self.exception_message,
            "ocr_attempts": list(self.ocr_attempts),
            "supplement_candidates": list(self.supplement_candidates),
            "region_ocr_debug": dict(self.region_ocr_debug),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def _barcode_crop_config() -> BarcodeCropConfig:
    return BarcodeCropConfig(expand_ratio=float(get_settings().p105_barcode_crop_expand_ratio or 0.12))


def _main_upc_from_candidates(candidates: list[str]) -> tuple[str, float]:
    """Extract 12-digit main UPC only — never treat 17-digit bar decode as trusted supplement."""
    best = ""
    for raw in candidates:
        digits = _digits_only(raw)
        if len(digits) >= 17 and upc_check_digit_valid(digits[:12]):
            return digits[:12], 0.95
        if len(digits) == 12 and upc_check_digit_valid(digits):
            best = digits
        elif len(digits) == 13 and digits.startswith("0") and upc_check_digit_valid(digits):
            best = digits[1:]
    if best:
        return best, 0.9
    return "", 0.0


def _decoded_supplement_from_candidates(candidates: list[str], main_upc: str) -> str:
    if len(main_upc) != 12:
        return ""
    for raw in candidates:
        digits = _digits_only(raw)
        if len(digits) >= 17 and digits[:12] == main_upc:
            return digits[12:17]
    return ""


def _decode_main_upc_from_pil(pil: Image.Image) -> tuple[str, float]:
    candidates = collect_raw_upc_candidates_from_pil(pil)
    return _main_upc_from_candidates(candidates)


def _decode_supplement_from_pil(pil: Image.Image, main_upc: str) -> str:
    candidates = collect_raw_upc_candidates_from_pil(pil)
    return _decoded_supplement_from_candidates(candidates, main_upc)


def _vision_ocr_region(image_bytes: bytes, *, system: str, user: str, log_context: str) -> tuple[str, float]:
    settings = get_settings()
    if not settings.openai_api_key:
        return "", 0.0
    from app.services.gpt_comic_vision_client import call_comic_vision

    model = settings.photo_import_barcode_read_model or "gpt-4o"
    timeout = float(settings.photo_import_barcode_read_timeout_seconds or 45.0)
    try:
        parsed, _, _, _ = call_comic_vision(
            image_bytes,
            model=model,
            api_key=settings.openai_api_key,
            log_context=log_context,
            system=system,
            user=user,
            image_detail="high",
            max_image_side_px=2048,
            timeout_seconds=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("p105.barcode_ocr_fail context=%s err=%s", log_context, exc)
        return "", 0.0
    if system.startswith("Read ONLY the small 5-digit"):
        digits = _digits_only(str(parsed.get("digits") or ""))
        conf = float(parsed.get("confidence") or 0.0)
        if len(digits) == 5:
            return digits, conf
        if 3 <= len(digits) <= 4:
            return digits, conf * 0.85
        return "", 0.0
    digit = _digits_only(str(parsed.get("digit") or ""))
    conf = float(parsed.get("confidence") or 0.0)
    if len(digit) == 1:
        return digit, conf
    return "", 0.0


def _vision_supplement_attempt(left_bytes: bytes, log_context: str) -> OcrAttempt | None:
    digits, conf = _vision_ocr_region(
        left_bytes,
        system=_LEFT_SUPPLEMENT_OCR_SYSTEM,
        user=_LEFT_SUPPLEMENT_OCR_USER,
        log_context=f"{log_context}:left_vision",
    )
    digits = _digits_only(digits)
    if not digits:
        return None
    return OcrAttempt(
        variant="vision|gpt",
        raw_text=digits,
        digits=digits if len(digits) <= 5 else digits[:5],
        confidence=conf,
        source="vision",
    )


def _normalize_supplement_partial(text: str) -> str:
    digits = _digits_only(text)
    if len(digits) == 5:
        return digits
    if 3 <= len(digits) <= 4:
        return digits.zfill(5)
    return ""


def _reconstruct_full(main_upc: str, supplement: str) -> str:
    if not main_upc or len(main_upc) != 12:
        return ""
    if not supplement or len(supplement) != 5:
        return main_upc
    full = main_upc + supplement
    if upc_check_digit_valid(main_upc):
        return full
    return ""


def _catalog_full_barcodes_for_main(session: Session, main_upc: str) -> list[tuple[str, int]]:
    if len(main_upc) != 12:
        return []
    rows = session.exec(
        select(CatalogUpc.normalized_upc, CatalogUpc.issue_id).where(
            CatalogUpc.normalized_upc.startswith(main_upc)
        )
    ).all()
    out: list[tuple[str, int]] = []
    for row in rows:
        upc = str(row[0] if isinstance(row, tuple) else row.normalized_upc)
        issue_id = int(row[1] if isinstance(row, tuple) else row.issue_id or 0)
        if len(upc) >= 17 and issue_id:
            out.append((upc[:17], issue_id))
    return out


def _recover_supplement_from_catalog(
    session: Session,
    *,
    main_upc: str,
    partial_supplement: str,
    cover_path: Path | None,
) -> tuple[str, int | None, float]:
    """Match 3–4 digit partial supplement against catalog UPCs; fingerprint disambiguates."""
    partial = _normalize_supplement_partial(partial_supplement)
    if not partial or len(partial) != 5:
        return "", None, 0.0
    candidates = _catalog_full_barcodes_for_main(session, main_upc)
    if not candidates:
        return "", None, 0.0
    suffix_matches = [
        (full, issue_id)
        for full, issue_id in candidates
        if full[12:17] == partial or full[12:17].endswith(partial.lstrip("0"))
    ]
    if not suffix_matches:
        return "", None, 0.0
    if len(suffix_matches) == 1:
        return suffix_matches[0][0][12:17], suffix_matches[0][1], 0.85
    if cover_path is None or not cover_path.is_file():
        return "", None, 0.0
    best_full = ""
    best_issue: int | None = None
    best_score = 0.0
    for full, issue_id in suffix_matches:
        score = fingerprint_match_score_for_crop_path(session, crop_path=cover_path, catalog_issue_id=issue_id)
        if score > best_score:
            best_score = score
            best_full = full[12:17]
            best_issue = issue_id
    if best_score >= 70.0 and best_full:
        return best_full, best_issue, min(0.95, best_score / 100.0)
    return "", None, 0.0


def _catalog_supplements_for_main(session: Session, main_upc: str) -> dict[str, int]:
    """Map known 5-digit supplements -> issue_id for this base UPC (catalog truth)."""
    out: dict[str, int] = {}
    for full, issue_id in _catalog_full_barcodes_for_main(session, main_upc):
        supp = full[12:17]
        if len(supp) == 5 and supp not in out:
            out[supp] = issue_id
    return out


def _correct_supplement_via_catalog(
    session: Session | None,
    *,
    main_upc: str,
    ocr_digits: str,
    catalog_map: dict[str, int],
    cover_path: Path | None,
) -> tuple[str, int | None, float, int] | None:
    """When OCR likely substituted a digit, snap to nearest catalog supplement.

    Returns (corrected_supplement, issue_id, fingerprint_score, hamming_distance) or None.
    Requires single catalog candidate OR cover-fingerprint agreement to justify a rewrite.
    """
    if len(ocr_digits) != 5 or not catalog_map:
        return None
    near = sorted(
        ((supp, hamming5(ocr_digits, supp)) for supp in catalog_map),
        key=lambda pair: pair[1],
    )
    near = [(supp, dist) for supp, dist in near if 1 <= dist <= 2]
    if not near:
        return None
    best_dist = near[0][1]
    group = [supp for supp, dist in near if dist == best_dist]

    if len(catalog_map) == 1 and len(group) == 1:
        supp = group[0]
        issue_id = catalog_map[supp]
        fp = 0.0
        if session is not None and cover_path is not None and cover_path.is_file():
            fp = fingerprint_match_score_for_crop_path(session, crop_path=cover_path, catalog_issue_id=issue_id)
        return supp, issue_id, fp, best_dist

    if session is None or cover_path is None or not cover_path.is_file():
        return None
    best_supp = ""
    best_issue: int | None = None
    best_fp = 0.0
    for supp in group:
        issue_id = catalog_map[supp]
        fp = fingerprint_match_score_for_crop_path(session, crop_path=cover_path, catalog_issue_id=issue_id)
        if fp > best_fp:
            best_fp = fp
            best_supp = supp
            best_issue = issue_id
    if best_supp and best_fp >= 70.0:
        return best_supp, best_issue, best_fp, best_dist
    return None


@dataclass
class _SupplementDecision:
    ocr_supplement: str = ""
    corrected_supplement: str = ""
    final_supplement: str = ""
    inferred: bool = False
    catalog_confirmed: bool = False
    fingerprint_confirmed: bool = False
    disagreement: bool = False
    confidence: float = 0.0
    review_reason: str = ""
    correction_reason: str = ""
    recovery: RecoveryKind = "none"
    decode_method: str = ""
    decode_confidence: float = 0.0


def _fingerprint_for_supplement(
    session: Session | None,
    cover_path: Path | None,
    catalog_map: dict[str, int],
    supplement: str,
) -> float:
    if session is None or cover_path is None or not cover_path.is_file():
        return 0.0
    issue_id = catalog_map.get(supplement)
    if issue_id is None:
        return 0.0
    return fingerprint_match_score_for_crop_path(session, crop_path=cover_path, catalog_issue_id=issue_id)


def _resolve_supplement_decision(
    scored: list[SupplementCandidate],
    *,
    main_upc: str,
    addon: UpAddonDecodeResult,
    catalog_map: dict[str, int],
    session: Session | None,
    cover_path: Path | None,
) -> _SupplementDecision:
    """Add-on bar decode is primary; OCR is fallback when bars fail."""
    decision = _SupplementDecision()
    top = scored[0] if scored else None
    decision.ocr_supplement = top.digits if top else ""
    bar_supp = addon.supplement if addon and len(addon.supplement) == 5 else ""
    ocr_supp = decision.ocr_supplement

    if bar_supp:
        decision.decode_method = addon.method or "addon_bars"
        decision.decode_confidence = addon.confidence
        decision.final_supplement = bar_supp
        decision.confidence = addon.confidence
        decision.recovery = "merged"

        if ocr_supp and ocr_supp != bar_supp:
            decision.disagreement = True
            bar_in_cat = bar_supp in catalog_map
            ocr_in_cat = ocr_supp in catalog_map
            fp_bar = _fingerprint_for_supplement(session, cover_path, catalog_map, bar_supp)
            fp_ocr = _fingerprint_for_supplement(session, cover_path, catalog_map, ocr_supp)
            decision.review_reason = (
                f"Add-on bars read {bar_supp} ({decision.decode_method}) but printed OCR read {ocr_supp}; "
                "using bar decode — confirm in review."
            )
            if ocr_in_cat and fp_ocr >= 80.0 and (not bar_in_cat or fp_bar < 65.0):
                decision.corrected_supplement = ocr_supp
                decision.review_reason = (
                    f"Bars ({bar_supp}) disagree with OCR ({ocr_supp}); catalog + fingerprint favor OCR "
                    f"({fp_ocr:.0f}%) — manual confirm required."
                )
            elif bar_in_cat:
                decision.catalog_confirmed = True
                if fp_bar >= 70.0:
                    decision.fingerprint_confirmed = True
        elif bar_supp in catalog_map:
            decision.catalog_confirmed = True
            fp = _fingerprint_for_supplement(session, cover_path, catalog_map, bar_supp)
            decision.fingerprint_confirmed = fp >= 70.0
        return decision

    # --- Bar add-on decode failed: fall back to OCR / consensus ---
    decision.decode_method = "ocr"
    if top is None:
        if session is not None and catalog_map:
            best_supp = ""
            best_fp = 0.0
            for supp, issue_id in catalog_map.items():
                fp = 0.0
                if cover_path is not None and cover_path.is_file():
                    fp = fingerprint_match_score_for_crop_path(
                        session, crop_path=cover_path, catalog_issue_id=issue_id
                    )
                if fp > best_fp:
                    best_fp, best_supp = fp, supp
            if len(catalog_map) == 1 and best_fp >= 70.0 and best_supp:
                decision.final_supplement = best_supp
                decision.corrected_supplement = best_supp
                decision.inferred = True
                decision.fingerprint_confirmed = True
                decision.decode_method = "inferred"
                decision.recovery = "inferred_catalog"
                decision.confidence = min(0.9, best_fp / 100.0)
                decision.review_reason = (
                    "Add-on bars unreadable; inferred from catalog + cover fingerprint."
                )
                decision.correction_reason = decision.review_reason
                return decision
        decision.review_reason = (
            "Add-on bar decode failed and left supplement OCR unreadable; see debug crops/overlay."
        )
        return decision

    decision.confidence = top.ocr_confidence

    if top.catalog_exists:
        decision.final_supplement = top.digits
        decision.catalog_confirmed = True
        decision.fingerprint_confirmed = top.fingerprint_score >= 70.0
        decision.recovery = "merged"
        return decision

    corrected = _correct_supplement_via_catalog(
        session,
        main_upc=main_upc,
        ocr_digits=top.digits,
        catalog_map=catalog_map,
        cover_path=cover_path,
    )
    if corrected is not None:
        supp, _issue_id, fp, dist = corrected
        decision.final_supplement = supp
        decision.corrected_supplement = supp
        decision.inferred = True
        decision.catalog_confirmed = True
        decision.fingerprint_confirmed = fp >= 70.0
        decision.decode_method = "inferred"
        decision.recovery = "inferred_catalog"
        decision.confidence = max(top.ocr_confidence, min(0.95, fp / 100.0) if fp else 0.7)
        fp_txt = f" + cover fingerprint ({fp:.0f}%)" if fp else ""
        decision.correction_reason = (
            f"OCR read {top.digits}; corrected to catalog supplement {supp} "
            f"(differs by {dist} digit{'s' if dist != 1 else ''}{fp_txt})."
        )
        decision.review_reason = decision.correction_reason
        return decision

    decision.final_supplement = top.digits
    if catalog_map:
        decision.review_reason = (
            f"Add-on bars unreadable; OCR supplement {top.digits} not in catalog for base UPC {main_upc}."
        )
    decision.recovery = "merged"
    return decision


def _publisher_prefix_ok(main_upc: str, catalog_map: dict[str, int]) -> bool:
    """Light publisher-prefix agreement: a known direct-market prefix with catalog rows."""
    if not main_upc or len(main_upc) != 12:
        return False
    return bool(catalog_map) and direct_market_requires_supplement_key(main_upc)


def _supplement_ocr_for_frame_bytes(
    frame_bytes: bytes,
    *,
    frame_index: int,
    log_context: str,
) -> SupplementFrameRead:
    """Run supplement-only OCR on one frame (barcode anchor geometry per frame)."""
    import io as io_mod

    with Image.open(io_mod.BytesIO(frame_bytes)) as img:
        pil = img.convert("RGB")
    geometry = compute_barcode_region_geometry(pil, config=_barcode_crop_config())
    if not geometry.supplement_ocr_allowed:
        return SupplementFrameRead(frame_index=frame_index, digits="", confidence=0.0)
    text_crop = addon_debug_crops(pil, geometry)["supplement_text_only"]
    attempts = gather_ocr_attempts(
        [("supplement_text_only", text_crop)],
        deskew_angle=geometry.deskew_angle,
        log_context=f"{log_context}:frame{frame_index}",
    )
    scored = score_supplement_candidates(attempts, main_upc="", catalog_supplements={})
    if not scored or len(scored[0].digits) != 5:
        return SupplementFrameRead(frame_index=frame_index, digits="", confidence=0.0)
    top = scored[0]
    return SupplementFrameRead(
        frame_index=frame_index,
        digits=top.digits,
        confidence=top.ocr_confidence,
    )


def read_comic_barcode_from_image_bytes(
    image_bytes: bytes,
    *,
    session: Session | None = None,
    cover_path: Path | None = None,
    intake_item_id: int | None = None,
    debug_dir: Path | None = None,
    log_context: str = "p105_comic_barcode",
    supplement_frame_bytes: list[bytes] | None = None,
) -> ComicBarcodeReadResult:
    """Decode main UPC from bars; OCR-retry the printed left supplement; reconstruct full barcode."""
    import io as io_mod

    config = _barcode_crop_config()
    with Image.open(io_mod.BytesIO(image_bytes)) as img:
        pil = img.convert("RGB")

    geometry = compute_barcode_region_geometry(pil, config=config)
    regions = crops_from_geometry(pil, geometry)

    main_upc, conf_main = _decode_main_upc_from_pil(regions["main_bars"])
    if not main_upc:
        main_upc, conf_main = _decode_main_upc_from_pil(regions["full_expanded"])

    addon = decode_upc_addon(pil, geometry, main_upc=main_upc) if main_upc else UpAddonDecodeResult()
    decoded_supplement = addon.supplement

    catalog_map: dict[str, int] = {}
    if session is not None and main_upc:
        catalog_map = _catalog_supplements_for_main(session, main_upc)

    addon_crops = addon_debug_crops(pil, geometry)
    supplement_text_crop = addon_crops["supplement_text_only"]

    # --- OCR fallback only when add-on bar decode did not yield 5 digits ------
    supplement_crop = regions["left_supplement"]
    left_variants: list[tuple[str, Image.Image]] = [("supplement_text_only", supplement_text_crop)]
    attempts: list[Any] = []
    vision_attempt = None
    run_ocr = geometry.supplement_ocr_allowed
    run_ocr_fallback = run_ocr and not decoded_supplement
    if run_ocr:
        vision_attempt = _vision_supplement_attempt(
            pil_to_jpeg_bytes(supplement_text_crop), log_context
        )
        attempts = gather_ocr_attempts(
            left_variants,
            deskew_angle=geometry.deskew_angle,
            log_context=f"{log_context}:left",
            vision_attempt=vision_attempt,
        )
    elif not decoded_supplement:
        logger.warning(
            "p105.supplement_ocr_skipped item=%s reason=%s failed=%s addon_empty=%s",
            intake_item_id or log_context,
            geometry.fallback_reason or "geometry_not_ready",
            geometry.geometry_failed,
            True,
        )
    elif decoded_supplement:
        logger.info(
            "p105.supplement_ocr_skipped item=%s addon_bars=%s method=%s",
            intake_item_id or log_context,
            decoded_supplement,
            addon.method,
        )

    fingerprint_scorer = None
    if session is not None and cover_path is not None and cover_path.is_file():
        def fingerprint_scorer(issue_id: int) -> float:  # noqa: ANN001 - local closure
            return fingerprint_match_score_for_crop_path(
                session, crop_path=cover_path, catalog_issue_id=issue_id
            )

    scored = score_supplement_candidates(
        attempts,
        main_upc=main_upc,
        catalog_supplements=catalog_map,
        fingerprint_scorer=fingerprint_scorer,
        publisher_prefix_ok=_publisher_prefix_ok(main_upc, catalog_map),
    )

    extra_frames = list(supplement_frame_bytes or [])
    frame_bytes_list = [image_bytes] + [fb for fb in extra_frames if fb and fb != image_bytes]
    frame_reads: list[SupplementFrameRead] = []
    consensus = vote_supplement_digits([])
    if run_ocr_fallback and len(frame_bytes_list) > 1:
        frame_reads = [
            _supplement_ocr_for_frame_bytes(fb, frame_index=idx, log_context=log_context)
            for idx, fb in enumerate(frame_bytes_list)
        ]
        consensus = vote_supplement_digits(frame_reads)
    if consensus.complete and consensus.digits and run_ocr_fallback:
        consensus_attempts = [
            OcrAttempt(
                variant="multi_frame_consensus",
                raw_text=consensus.digits,
                digits=consensus.digits,
                confidence=consensus.confidence,
                source="multi_frame_consensus",
            )
        ]
        rescored = score_supplement_candidates(
            consensus_attempts,
            main_upc=main_upc,
            catalog_supplements=catalog_map,
            fingerprint_scorer=fingerprint_scorer,
            publisher_prefix_ok=_publisher_prefix_ok(main_upc, catalog_map),
        )
        consensus_candidate = rescored[0] if rescored else SupplementCandidate(
            digits=consensus.digits,
            score=2.0 + consensus.confidence,
            ocr_confidence=consensus.confidence,
            repeat_count=max(1, len([r for r in frame_reads if r.digits == consensus.digits])),
            sources=["multi_frame_consensus"],
        )
        if "multi_frame_consensus" not in consensus_candidate.sources:
            consensus_candidate.sources.append("multi_frame_consensus")
        consensus_candidate.repeat_count = max(
            consensus_candidate.repeat_count,
            len([r for r in frame_reads if r.digits == consensus.digits]),
        )
        scored = [consensus_candidate] + [c for c in scored if c.digits != consensus.digits]
        logger.info(
            "p105.supplement_consensus item=%s frames=%d digits=%s conf=%.2f reads=%s",
            intake_item_id or log_context,
            len(frame_bytes_list),
            consensus.digits,
            consensus.confidence,
            [r.digits for r in frame_reads if r.digits],
        )
    elif len(frame_bytes_list) > 1 and consensus.review_reason:
        logger.warning(
            "p105.supplement_consensus_incomplete item=%s frames=%d reason=%s reads=%s",
            intake_item_id or log_context,
            len(frame_bytes_list),
            consensus.review_reason,
            [r.digits for r in frame_reads],
        )

    decision = _resolve_supplement_decision(
        scored,
        main_upc=main_upc,
        addon=addon,
        catalog_map=catalog_map,
        session=session,
        cover_path=cover_path,
    )

    right_bytes = pil_to_jpeg_bytes(regions["right_cover_digit"])
    right_ocr, right_conf = _vision_ocr_region(
        right_bytes,
        system=_RIGHT_DIGIT_OCR_SYSTEM,
        user=_RIGHT_DIGIT_OCR_USER,
        log_context=f"{log_context}:right",
    )

    ocr_attempts_payload = [a.to_dict() for a in attempts]
    candidates_payload = [c.to_dict() for c in scored]
    region_ocr_debug: dict[str, Any] = {
        "geometry": geometry.as_dict(),
        "left_supplement": {
            "ocr_attempts": ocr_attempts_payload,
            "candidates": candidates_payload,
            "ocr_supplement": decision.ocr_supplement,
            "corrected_supplement": decision.corrected_supplement,
            "final_supplement": decision.final_supplement,
            "ocr_confidence": decision.confidence,
            "correction_reason": decision.correction_reason,
            "supplement_consensus": consensus.to_dict(),
            "addon_decode": addon.to_dict(),
        },
        "right_cover_digit": {"vision_digit": right_ocr, "vision_confidence": right_conf},
        "decoded_supplement_from_bars": decoded_supplement,
        "supplement_decode_method": decision.decode_method,
        "supplement_decode_confidence": decision.decode_confidence,
        "main_upc": main_upc,
        "main_confidence": conf_main,
        "detection_method": geometry.detection_method,
        "geometry_attempted": geometry.geometry_attempted,
        "opencv_available": geometry.opencv_available,
        "fallback_reason": geometry.fallback_reason,
        "geometry_rejection_reason": geometry.geometry_rejection_reason,
        "exception_message": geometry.exception_message,
    }
    logger.info(
        "p105.barcode_regions item=%s method=%s fallback=%s opencv=%s contours=%s main=%s decoded_supp=%s "
        "ocr_supp=%s final=%s inferred=%s catalog_ok=%s fp_ok=%s disagree=%s attempts=%d",
        intake_item_id or log_context,
        geometry.detection_method,
        geometry.fallback_reason or "(none)",
        geometry.opencv_available,
        geometry.contour_count,
        main_upc,
        decoded_supplement,
        decision.ocr_supplement,
        decision.final_supplement,
        decision.inferred,
        decision.catalog_confirmed,
        decision.fingerprint_confirmed,
        decision.disagreement,
        len(attempts),
    )

    region_debug_path = ""
    debug_base: Path | None = None
    if debug_dir is not None:
        debug_base = Path(debug_dir)
    elif intake_item_id is not None:
        debug_base = _p105_regions.P105_BARCODE_DEBUG_ROOT / str(int(intake_item_id))
    if debug_base is not None:
        overlay = draw_region_overlay(pil, geometry)
        from app.services.p105_geometry_debug_viz import (
            build_geometry_ocr_debug_visuals,
            write_geometry_debug_images,
        )

        geo_viz = build_geometry_ocr_debug_visuals(
            pil,
            geometry,
            regions["left_supplement"],
            chosen_digits=decision.ocr_supplement,
        )
        region_ocr_debug["geometry_viz"] = geo_viz.metadata
        region_debug_path = save_barcode_region_debug_to_dir(
            debug_base,
            regions,
            ocr_debug=region_ocr_debug,
            overlay=overlay,
            left_variants=left_variants,
            extra_crops=addon_crops,
        )
        write_geometry_debug_images(debug_base, geo_viz)
        write_addon_microscope_debug(debug_base, addon)

    final_supplement = decision.final_supplement
    if len(final_supplement) == 5:
        reconstructed = _reconstruct_full(main_upc, final_supplement)
    else:
        reconstructed = main_upc

    raw_decoded = main_upc
    if reconstructed and len(reconstructed) >= 17:
        raw_decoded = reconstructed

    conf_left = decision.confidence
    conf_reconstructed = 0.0
    if reconstructed and len(reconstructed) >= 17:
        conf_reconstructed = min(0.99, (conf_main + conf_left) / 2.0 if conf_left else conf_main)

    top = scored[0] if scored else None
    ocr_strong = bool(top and top.repeat_count >= 2 and top.ocr_confidence >= 0.6)
    bars_confirmed = bool(decoded_supplement and addon.confidence >= 0.75 and (addon.check_valid or decision.catalog_confirmed))
    confirmed = (
        decision.catalog_confirmed
        or decision.fingerprint_confirmed
        or bars_confirmed
        or (not catalog_map and ocr_strong)
    )

    auto_match = bool(
        reconstructed
        and len(reconstructed) >= 17
        and len(final_supplement) == 5
        and upc_check_digit_valid(reconstructed[:12])
        and not decision.inferred
        and not decision.disagreement
        and confirmed
        and conf_main >= 0.85
    )

    review_reason = decision.review_reason
    if decision.inferred:
        auto_match = False
        if not review_reason:
            review_reason = "Inferred/corrected supplemental digits — confirm in review."
    if decision.disagreement:
        auto_match = False
    if not geometry.supplement_ocr_allowed and not decoded_supplement:
        auto_match = False
        review_reason = review_reason or (
            "Supplement decode skipped: barcode anchor crop not ready. "
            f"See supplement_only.jpg ({geometry.fallback_reason or 'geometry_failed'})."
        )
    elif run_ocr_fallback and len(frame_bytes_list) > 1 and not consensus.complete:
        auto_match = False
        review_reason = review_reason or consensus.review_reason
    if geometry.geometry_failed:
        auto_match = False
        ow, oh = geometry.original_size
        lw = geometry.left_supplement[2] - geometry.left_supplement[0]
        lh = geometry.left_supplement[3] - geometry.left_supplement[1]
        review_reason = (
            f"Input image too small for reliable barcode OCR: original_size={ow}x{oh}, "
            f"uploaded {len(image_bytes)} bytes, left supplement crop only {lw}x{lh}px. "
            "Capture/store a higher-resolution photo. See overlay.jpg."
        )
    if not final_supplement and main_upc and direct_market_requires_supplement_key(main_upc):
        auto_match = False
        review_reason = review_reason or (
            f"Read base UPC {main_upc} but could not confirm the 5-digit supplement."
        )

    return ComicBarcodeReadResult(
        raw_decoded_barcode=raw_decoded,
        main_upc=main_upc,
        left_supplement_ocr=decision.ocr_supplement,
        decoded_supplement=decoded_supplement,
        ocr_supplement=decision.ocr_supplement,
        corrected_supplement=decision.corrected_supplement,
        final_supplement=final_supplement,
        supplement_disagreement=decision.disagreement,
        supplement_decode_method=decision.decode_method,
        supplement_decode_confidence=decision.decode_confidence,
        catalog_confirmed=decision.catalog_confirmed,
        fingerprint_confirmed=decision.fingerprint_confirmed,
        correction_reason=decision.correction_reason,
        right_cover_digit_ocr=right_ocr,
        reconstructed_full=reconstructed,
        confidence_main=conf_main,
        confidence_left=conf_left,
        confidence_reconstructed=conf_reconstructed,
        recovery_kind=decision.recovery,
        inferred_supplement=decision.inferred,
        crop_expand_ratio=config.clamped_expand_ratio(),
        review_reason=review_reason,
        auto_match_allowed=auto_match,
        region_debug_path=region_debug_path,
        detection_method=geometry.detection_method,
        geometry_attempted=geometry.geometry_attempted,
        opencv_available=geometry.opencv_available,
        fallback_reason=geometry.fallback_reason,
        geometry_rejection_reason=geometry.geometry_rejection_reason,
        exception_message=geometry.exception_message,
        ocr_attempts=ocr_attempts_payload,
        supplement_candidates=candidates_payload,
        region_ocr_debug=region_ocr_debug,
    )


def merge_multi_frame_reads(reads: list[ComicBarcodeReadResult], *, min_votes: int = DEFAULT_MIN_VOTES) -> ComicBarcodeReadResult:
    """Vote on OCR-based reconstructed full barcode across frames."""
    if not reads:
        return ComicBarcodeReadResult(review_reason="No barcode reads.")
    full_candidates = []
    for r in reads:
        if r.main_upc and len(r.final_supplement) == 5:
            full_candidates.append(_reconstruct_full(r.main_upc, r.final_supplement))
        elif r.reconstructed_full and len(r.ocr_supplement) == 5:
            full_candidates.append(r.reconstructed_full)
    vote = vote_barcode_reads(full_candidates, min_votes=min_votes) if full_candidates else None
    base = reads[-1]
    if vote and vote.acceptance == "accepted":
        vote_final_supp = supplement_extension(vote.normalized)
        if base.ocr_supplement and len(base.ocr_supplement) == 5 and vote_final_supp != base.ocr_supplement:
            base.review_reason = (
                base.review_reason or f"Frame vote ({vote_final_supp}) disagrees with OCR ({base.ocr_supplement})."
            )
            base.supplement_disagreement = True
            base.auto_match_allowed = False
            vote_final_supp = base.ocr_supplement
            vote_full = _reconstruct_full(base_upc(vote.normalized), vote_final_supp)
        else:
            vote_full = vote.normalized
        merged = ComicBarcodeReadResult(
            raw_decoded_barcode=vote_full,
            main_upc=base_upc(vote_full),
            left_supplement_ocr=base.ocr_supplement or vote_final_supp,
            decoded_supplement=base.decoded_supplement,
            ocr_supplement=base.ocr_supplement,
            final_supplement=vote_final_supp or base.final_supplement,
            supplement_disagreement=base.supplement_disagreement,
            right_cover_digit_ocr=base.right_cover_digit_ocr,
            reconstructed_full=vote_full,
            confidence_main=base.confidence_main,
            confidence_left=base.confidence_left,
            confidence_reconstructed=min(0.99, base.confidence_reconstructed + 0.05),
            recovery_kind=base.recovery_kind,
            inferred_supplement=base.inferred_supplement,
            crop_expand_ratio=base.crop_expand_ratio,
            vote_count=vote.vote_count,
            review_reason=base.review_reason,
            auto_match_allowed=base.auto_match_allowed and not base.inferred_supplement and not base.supplement_disagreement,
            region_debug_path=base.region_debug_path,
            region_ocr_debug=dict(base.region_ocr_debug),
        )
        return merged
    base.vote_count = max(r.vote_count for r in reads)
    if not base.review_reason:
        base.review_reason = f"Need {min_votes} agreeing frames before auto-match."
    base.auto_match_allowed = False
    return base


def publisher_validation_for_match(barcode: str, publisher: str | None, issue_number: str | None, year: str | None) -> str:
    result = validate_barcode_catalog_match(barcode, publisher=publisher, issue_number=issue_number, year=year)
    if result.status != "exact_match":
        return result.reason
    return ""
