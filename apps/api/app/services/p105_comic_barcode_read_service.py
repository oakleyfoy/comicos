"""P105 comic barcode read: split decode/OCR, reconstruction, catalog recovery."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

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
    merge_comic_upc_decodes,
    normalize_upc,
    upc_check_digit_valid,
)
from app.services.p105_comic_barcode_regions import (
    BarcodeCropConfig,
    crop_upc_region_pil,
    pil_to_jpeg_bytes,
    split_barcode_box_regions,
)
from app.services.photo_import_fingerprint_service import (
    fingerprint_match_score_for_crop_path,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_decoded_barcode": self.raw_decoded_barcode,
            "main_upc": self.main_upc,
            "left_supplement_ocr": self.left_supplement_ocr,
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
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def _barcode_crop_config() -> BarcodeCropConfig:
    return BarcodeCropConfig(expand_ratio=float(get_settings().p105_barcode_crop_expand_ratio or 0.12))


def _decode_main_upc_from_pil(pil) -> tuple[str, float]:
    candidates = collect_raw_upc_candidates_from_pil(pil)
    merged = merge_comic_upc_decodes(candidates) or ""
    if merged and len(merged) >= 12:
        main = merged[:12]
        if upc_check_digit_valid(main):
            return main, 0.95
    for raw in candidates:
        digits = _digits_only(raw)
        if len(digits) >= 12 and upc_check_digit_valid(digits[:12]):
            return digits[:12], 0.9
    return "", 0.0


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
        return "", 0.0
    digit = _digits_only(str(parsed.get("digit") or ""))
    conf = float(parsed.get("confidence") or 0.0)
    if len(digit) == 1:
        return digit, conf
    return "", 0.0


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


def read_comic_barcode_from_image_bytes(
    image_bytes: bytes,
    *,
    session: Session | None = None,
    cover_path: Path | None = None,
    log_context: str = "p105_comic_barcode",
) -> ComicBarcodeReadResult:
    """Decode main UPC from bars; OCR left supplement; reconstruct full comic barcode."""
    from PIL import Image
    import io as io_mod

    config = _barcode_crop_config()
    with Image.open(io_mod.BytesIO(image_bytes)) as img:
        pil = img.convert("RGB")
    upc_crop = crop_upc_region_pil(pil, config=config)
    regions = split_barcode_box_regions(upc_crop, config=config)

    main_upc, conf_main = _decode_main_upc_from_pil(regions["main_bars"])
    if not main_upc:
        main_upc, conf_main = _decode_main_upc_from_pil(regions["full_expanded"])

    left_bytes = pil_to_jpeg_bytes(regions["left_supplement"])
    right_bytes = pil_to_jpeg_bytes(regions["right_cover_digit"])
    left_ocr, conf_left = _vision_ocr_region(
        left_bytes, system=_LEFT_SUPPLEMENT_OCR_SYSTEM, user=_LEFT_SUPPLEMENT_OCR_USER, log_context=f"{log_context}:left"
    )
    right_ocr, _ = _vision_ocr_region(
        right_bytes, system=_RIGHT_DIGIT_OCR_SYSTEM, user=_RIGHT_DIGIT_OCR_USER, log_context=f"{log_context}:right"
    )

    left_raw = _digits_only(left_ocr)
    supplement = ""
    if len(left_raw) == 5:
        supplement = left_raw
    elif 3 <= len(left_raw) <= 4:
        supplement = left_raw
    inferred = False
    recovery: RecoveryKind = "none"
    review_reason = ""

    if main_upc and direct_market_requires_supplement_key(main_upc) and 3 <= len(left_raw) <= 4:
        review_reason = "Supplement OCR incomplete (3–4 digits); refusing direct auto-match."
        if session is not None:
            recovered, _, conf_rec = _recover_supplement_from_catalog(
                session, main_upc=main_upc, partial_supplement=left_raw, cover_path=cover_path
            )
            if recovered:
                supplement = recovered
                inferred = True
                recovery = "inferred_catalog"
                conf_left = max(conf_left, conf_rec)
                review_reason = "Supplement inferred from catalog + cover fingerprint."
            else:
                recovery = "none"
    elif len(left_raw) == 5:
        recovery = "merged"

    if len(supplement) == 5:
        reconstructed = _reconstruct_full(main_upc, supplement)
    else:
        reconstructed = main_upc
    if reconstructed and len(reconstructed) >= 17:
        recovery = "inferred_catalog" if inferred else "merged"
    raw_decoded = merge_comic_upc_decodes([main_upc, supplement, reconstructed]) or reconstructed or main_upc

    conf_reconstructed = 0.0
    if reconstructed and len(reconstructed) >= 17:
        conf_reconstructed = min(0.99, (conf_main + conf_left) / 2.0 if conf_left else conf_main)
    auto_match = bool(
        reconstructed
        and len(reconstructed) >= 17
        and len(supplement) == 5
        and upc_check_digit_valid(reconstructed[:12])
        and not inferred
        and conf_main >= 0.85
        and conf_left >= 0.7
    )
    if inferred:
        auto_match = False
        if not review_reason:
            review_reason = "Inferred supplemental digits — confirm in review."

    return ComicBarcodeReadResult(
        raw_decoded_barcode=raw_decoded,
        main_upc=main_upc,
        left_supplement_ocr=supplement or left_ocr,
        right_cover_digit_ocr=right_ocr,
        reconstructed_full=reconstructed,
        confidence_main=conf_main,
        confidence_left=conf_left,
        confidence_reconstructed=conf_reconstructed,
        recovery_kind=recovery,
        inferred_supplement=inferred,
        crop_expand_ratio=config.clamped_expand_ratio(),
        review_reason=review_reason,
        auto_match_allowed=auto_match,
    )


def merge_multi_frame_reads(reads: list[ComicBarcodeReadResult], *, min_votes: int = DEFAULT_MIN_VOTES) -> ComicBarcodeReadResult:
    """Vote on reconstructed full barcode across frames; stabilize main UPC separately."""
    if not reads:
        return ComicBarcodeReadResult(review_reason="No barcode reads.")
    full_candidates = [r.reconstructed_full for r in reads if r.reconstructed_full]
    vote = vote_barcode_reads(full_candidates, min_votes=min_votes) if full_candidates else None
    base = reads[-1]
    if vote and vote.acceptance == "accepted":
        merged = ComicBarcodeReadResult(
            raw_decoded_barcode=vote.raw_scan,
            main_upc=base_upc(vote.normalized),
            left_supplement_ocr=supplement_extension(vote.normalized),
            reconstructed_full=vote.normalized,
            confidence_main=base.confidence_main,
            confidence_left=base.confidence_left,
            confidence_reconstructed=min(0.99, base.confidence_reconstructed + 0.05),
            recovery_kind=base.recovery_kind,
            inferred_supplement=base.inferred_supplement,
            crop_expand_ratio=base.crop_expand_ratio,
            vote_count=vote.vote_count,
            review_reason=base.review_reason,
            auto_match_allowed=base.auto_match_allowed and not base.inferred_supplement,
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
