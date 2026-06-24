"""P100-28 barcode extraction for standalone GPT Comic Read (local decode + optional GPT crop)."""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageEnhance, ImageOps

from app.services.photo_import_barcode_vision import crop_upc_region_bytes, sanitize_vision_barcode

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
    zones: list[tuple[str, Image.Image]] = []
    bottom_top = max(0, int(h * 0.52))
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
    zones.append(("full", pil))
    return zones


def _preprocess_variants(pil: Image.Image) -> list[tuple[str, Image.Image]]:
    out: list[tuple[str, Image.Image]] = [("raw", pil)]
    gray = ImageOps.grayscale(pil)
    out.append(("gray_autocontrast", ImageOps.autocontrast(gray).convert("RGB")))
    sharp = ImageEnhance.Contrast(pil).enhance(1.6)
    out.append(("sharpen", ImageEnhance.Sharpness(sharp).enhance(2.0)))
    return out


def _pil_to_jpeg_bytes(pil: Image.Image) -> bytes:
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def _decode_local_on_pil(pil: Image.Image) -> tuple[str, str, str] | None:
    """Return (barcode, barcode_type, backend_detail) or None."""
    from app.services.photo_import_upc_barcode_decoder import (
        _decode_opencv_bgr,
        _decode_pyzbar_pil,
        _opencv_available,
        _pyzbar_available,
        _try_backends_on_pil,
    )

    opencv_fn = _decode_opencv_bgr if _opencv_available() else None
    pyzbar_fn = _decode_pyzbar_pil if _pyzbar_available() else None
    if opencv_fn is None and pyzbar_fn is None:
        return None

    for pp_label, processed in _preprocess_variants(pil):
        hit = _try_backends_on_pil(processed, opencv_fn=opencv_fn, pyzbar_fn=pyzbar_fn)
        if hit is not None:
            code, detail = hit
            btype = "upc_a" if detail.startswith("opencv") else "ean13/upc"
            return code, btype, f"{detail}@{pp_label}"
    return None


def _local_decode(image_bytes: bytes) -> dict[str, Any]:
    logger.info("p100.barcode_extraction.started bytes=%d", len(image_bytes))
    try:
        pil = _pil_from_bytes(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("p100.barcode_extraction.invalid_image error=%s", exc)
        return _empty_result(error="invalid_image")

    for crop_name, crop_pil in _crop_zones(pil):
        logger.info("p100.barcode_extraction.crop_attempt crop=%s", crop_name)
        hit = _decode_local_on_pil(crop_pil)
        if hit is None:
            logger.info("p100.barcode_extraction.local_decode_fail crop=%s", crop_name)
            continue
        code, btype, detail = hit
        logger.info(
            "p100.barcode_extraction.local_decode_success crop=%s barcode=%s detail=%s",
            crop_name,
            code,
            detail,
        )
        return {
            "barcode": code,
            "barcode_type": btype,
            "confidence": 0.95,
            "method": "local_decode",
            "crop_used": crop_name,
            "error": None,
        }

    logger.info("p100.barcode_extraction.local_decode_fail crop=all")
    return _empty_result()


def _gpt_barcode_fallback(image_bytes: bytes, *, log_context: str) -> dict[str, Any]:
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

    crop_bytes = crop_upc_region_bytes(image_bytes)
    crop_used = "bottom_left" if crop_bytes != image_bytes else "full"
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
    if local.get("barcode"):
        return local
    if allow_gpt_fallback:
        gpt = _gpt_barcode_fallback(image_bytes, log_context=log_context)
        if gpt.get("barcode"):
            return gpt
    return local if local.get("error") else _empty_result()
