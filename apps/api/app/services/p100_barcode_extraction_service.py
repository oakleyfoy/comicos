"""P100-28 barcode extraction for standalone GPT Comic Read (local decode + optional GPT crop)."""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from app.services.catalog_ingestion_service import (
    direct_market_requires_supplement_key,
    merge_comic_upc_decodes,
    normalize_upc,
)
from app.services.photo_import_barcode_vision import (
    crop_barcode_primary_bytes,
    crop_upc_region_bytes,
    normalize_comic_scan_barcode,
    sanitize_vision_barcode,
)

logger = logging.getLogger(__name__)

BarcodeMethod = Literal["local_decode", "gpt_barcode_read", "none"]

_GPT_BARCODE_DIGITS = re.compile(r"^\d{8,18}$")


def _empty_result(*, error: str | None = None) -> dict[str, Any]:
    return {
        "barcode": None,
        "barcode_type": None,
        "confidence": 0.0,
        "method": "none",
        "crop_used": None,
        "error": error,
    }


def accept_gpt_barcode_digits(raw: str | None) -> str | None:
    """Digits-only 8–18 chars; prefer validated UPC check digit when possible."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if not _GPT_BARCODE_DIGITS.fullmatch(digits):
        return None
    validated = merge_comic_upc_decodes([digits]) or sanitize_vision_barcode(digits)
    return validated or None


def _pil_from_bytes(image_bytes: bytes) -> Image.Image:
    with Image.open(io.BytesIO(image_bytes)) as img:
        return img.convert("RGB")


def _crop_zones(pil: Image.Image) -> list[tuple[str, Image.Image]]:
    w, h = pil.size
    zones: list[tuple[str, Image.Image]] = [("full", pil)]
    if h > int(w * 0.85):
        mid = max(1, h // 2)
        zones.append(("top_half", pil.crop((0, 0, w, mid))))
        zones.append(("bottom_half", pil.crop((0, mid, w, h))))
    bottom_top = max(0, int(h * 0.35))
    bottom_strip = pil.crop((0, bottom_top, w, h))
    zones.append(("bottom_strip", bottom_strip))
    zones.append(
        (
            "bottom_left",
            bottom_strip.crop((0, 0, max(1, int(bottom_strip.size[0] * 0.55)), bottom_strip.size[1])),
        )
    )
    zones.append(
        (
            "bottom_right",
            bottom_strip.crop(
                (
                    max(0, int(bottom_strip.size[0] * 0.45)),
                    0,
                    bottom_strip.size[0],
                    bottom_strip.size[1],
                )
            ),
        )
    )
    return zones


def _pil_to_jpeg_bytes(pil: Image.Image) -> bytes:
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def _local_decode(image_bytes: bytes) -> dict[str, Any]:
    logger.info("p100.barcode_extraction.started bytes=%d", len(image_bytes))
    try:
        pil = _pil_from_bytes(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("p100.barcode_extraction.invalid_image error=%s", exc)
        return _empty_result(error="invalid_image")

    all_candidates: list[str] = []
    best_crop = "merged"
    for crop_name, crop_pil in _crop_zones(pil):
        logger.info("p100.barcode_extraction.crop_attempt crop=%s", crop_name)
        from app.services.photo_import_upc_barcode_decoder import collect_raw_upc_candidates_from_pil

        chunk = collect_raw_upc_candidates_from_pil(crop_pil)
        if chunk:
            best_crop = crop_name
        all_candidates.extend(chunk)

    from app.services.photo_import_upc_barcode_decoder import _collect_valid_upc

    code = _collect_valid_upc(all_candidates)
    if code is None:
        logger.info("p100.barcode_extraction.local_decode_fail crop=all candidates=%d", len(all_candidates))
        return _empty_result()

    logger.info(
        "p100.barcode_extraction.local_decode_success crop=%s barcode=%s candidates=%d",
        best_crop,
        code,
        len(all_candidates),
    )
    return {
        "barcode": code,
        "barcode_type": "upc_a",
        "confidence": 0.95,
        "method": "local_decode",
        "crop_used": best_crop,
        "error": None,
        "raw_candidates": all_candidates[:24],
    }


def _gpt_barcode_fallback(
    image_bytes: bytes,
    *,
    log_context: str,
    wide_crop: bool = False,
) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.services.gpt_comic_identification_prompts import (
        COMIC_BARCODE_FOCUS_SYSTEM,
        COMIC_BARCODE_FOCUS_USER,
    )
    from app.services.gpt_comic_vision_client import call_comic_vision
    from app.services.photo_import_barcode_vision import parse_barcode_focus_payload

    settings = get_settings()
    if not settings.openai_api_key:
        logger.info("p100.barcode_extraction.gpt_fallback_skip reason=no_openai_key")
        return _empty_result(error="gpt_unconfigured")

    crop_bytes = crop_barcode_primary_bytes(image_bytes) if wide_crop else crop_upc_region_bytes(image_bytes)
    crop_used = "barcode_primary_wide" if wide_crop else ("bottom_left" if crop_bytes != image_bytes else "full")
    logger.info("p100.barcode_extraction.gpt_fallback crop=%s", crop_used)
    try:
        parsed, _payload, _raw, _model = call_comic_vision(
            crop_bytes,
            model=settings.gpt_comic_read_model,
            api_key=settings.openai_api_key,
            log_context=log_context,
            system=COMIC_BARCODE_FOCUS_SYSTEM,
            user=COMIC_BARCODE_FOCUS_USER,
            image_detail="high",
            max_image_side_px=2560,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("p100.barcode_extraction.gpt_fallback_fail error=%s", exc)
        return _empty_result(error="gpt_barcode_failed")

    raw_code, conf, _reasoning = parse_barcode_focus_payload(parsed)
    code = accept_gpt_barcode_digits(raw_code)
    if not code:
        logger.info("p100.barcode_extraction.gpt_fallback_rejected raw=%r", raw_code[:32] if raw_code else "")
        return _empty_result(error="gpt_barcode_rejected")

    logger.info("p100.barcode_extraction.gpt_fallback_success barcode=%s conf=%.2f", code, conf)
    return {
        "barcode": code,
        "barcode_type": "upc_a",
        "confidence": float(conf),
        "method": "gpt_barcode_read",
        "crop_used": crop_used,
        "error": None,
    }


def _normalized_extracted_barcode(raw: str | None) -> str:
    return normalize_comic_scan_barcode(str(raw or "")) or normalize_upc(str(raw or ""))


def extract_barcode_from_image(
    image: bytes | str | Path,
    *,
    allow_gpt_fallback: bool = True,
    log_context: str = "p100_barcode_extraction",
) -> dict[str, Any]:
    """Extract a normalized barcode from image bytes or path."""
    if isinstance(image, (str, Path)):
        path = Path(image)
        if not path.is_file():
            return _empty_result(error="file_not_found")
        image_bytes = path.read_bytes()
    else:
        image_bytes = image

    local = _local_decode(image_bytes)
    local_code = _normalized_extracted_barcode(local.get("barcode"))
    needs_supplement = bool(local_code) and direct_market_requires_supplement_key(local_code)

    if allow_gpt_fallback and (not local_code or needs_supplement):
        gpt = _gpt_barcode_fallback(image_bytes, log_context=log_context, wide_crop=True)
        gpt_code = _normalized_extracted_barcode(gpt.get("barcode"))
        if gpt_code and (not needs_supplement or not direct_market_requires_supplement_key(gpt_code)):
            return gpt
        if gpt_code and len(gpt_code) >= 17:
            return gpt

    if local.get("barcode"):
        return local
    if allow_gpt_fallback and not needs_supplement:
        gpt = _gpt_barcode_fallback(image_bytes, log_context=log_context, wide_crop=False)
        if gpt.get("barcode"):
            return gpt
    return local if local.get("error") else _empty_result()
