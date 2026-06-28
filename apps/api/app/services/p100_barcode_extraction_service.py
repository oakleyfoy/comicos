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


def _vision_crop_bytes(image_bytes: bytes, *, wide_crop: bool) -> tuple[bytes, str]:
    if wide_crop:
        crop_bytes = crop_barcode_primary_bytes(image_bytes)
        crop_used = "barcode_primary_wide"
    else:
        crop_bytes = crop_upc_region_bytes(image_bytes)
        crop_used = "bottom_left" if crop_bytes != image_bytes else "full"
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            if w / max(h, 1) >= 2.0:
                return image_bytes, "barcode_strip_full"
    except Exception:  # noqa: BLE001
        pass
    return crop_bytes, crop_used


def _gcd_supplement_options(main_upc: str) -> list[str]:
    from app.core.config import get_settings

    main = normalize_upc(main_upc)
    if len(main) != 12:
        return []
    gcd_path = get_settings().gcd_sqlite_path
    if not gcd_path.is_file():
        return []
    import sqlite3

    supplements: set[str] = set()
    conn = sqlite3.connect(gcd_path)
    try:
        rows = conn.execute(
            """
            SELECT barcode FROM gcd_issue
            WHERE barcode IS NOT NULL AND barcode LIKE ?
            """,
            (f"{main}%",),
        ).fetchall()
        for (raw,) in rows:
            digits = normalize_upc(str(raw or ""))
            if digits.startswith(main) and len(digits) >= 17:
                supplements.add(digits[12:17])
    finally:
        conn.close()
    return sorted(supplements)[:12]


def _gpt_supplement_fallback(
    image_bytes: bytes,
    *,
    main_upc: str,
    log_context: str,
) -> str:
    from app.core.config import get_settings
    from app.services.gpt_comic_identification_prompts import (
        COMIC_SUPPLEMENT_FOCUS_SYSTEM,
        COMIC_SUPPLEMENT_FOCUS_USER,
    )
    from app.services.gpt_comic_vision_client import call_comic_vision

    settings = get_settings()
    if not settings.openai_api_key:
        return ""
    crop_bytes, _crop = _vision_crop_bytes(image_bytes, wide_crop=True)
    model = settings.photo_import_barcode_read_model or "gpt-4o"
    timeout_seconds = float(settings.photo_import_barcode_read_timeout_seconds or 45.0)
    user = COMIC_SUPPLEMENT_FOCUS_USER.format(main_upc=main_upc)
    options = _gcd_supplement_options(main_upc)
    if options:
        user = (
            f"{user} Choose exactly one of these catalog supplements if visible: "
            f"{', '.join(options)}."
        )
    try:
        parsed, _payload, _raw, _model = call_comic_vision(
            crop_bytes,
            model=model,
            api_key=settings.openai_api_key,
            log_context=f"{log_context}:supplement",
            system=COMIC_SUPPLEMENT_FOCUS_SYSTEM,
            user=user,
            image_detail="high",
            max_image_side_px=2048,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("p100.barcode_extraction.gpt_supplement_fail error=%s", exc)
        return ""
    supp = re.sub(r"\D", "", str(parsed.get("supplement") or ""))
    if len(supp) == 5:
        if options and supp not in options:
            logger.warning(
                "p100.barcode_extraction.gpt_supplement_not_in_catalog main=%s supplement=%s",
                main_upc,
                supp,
            )
            return ""
        return supp
    if 3 <= len(supp) <= 4:
        return supp.zfill(5)
    return ""


def _merge_gpt_main_and_supplement(
    image_bytes: bytes,
    *,
    main_code: str,
    log_context: str,
    base_result: dict[str, Any],
) -> dict[str, Any]:
    main_norm = normalize_upc(main_code)
    if len(main_norm) != 12 or not direct_market_requires_supplement_key(main_norm):
        return base_result
    supplement = _gpt_supplement_fallback(image_bytes, main_upc=main_norm, log_context=log_context)
    if len(supplement) != 5:
        return base_result
    merged = merge_comic_upc_decodes([main_norm, supplement])
    merged_norm = normalize_upc(merged or "")
    if len(merged_norm) < 17:
        return base_result
    try:
        from app.core.config import get_settings
        from app.services.gcd_barcode_search_service import find_gcd_rows_by_normalized_barcode

        gcd_path = get_settings().gcd_sqlite_path
        if gcd_path.is_file() and not find_gcd_rows_by_normalized_barcode(gcd_path, merged_norm):
            logger.warning(
                "p100.barcode_extraction.gpt_supplement_rejected main=%s supplement=%s full=%s (no GCD hit)",
                main_norm,
                supplement,
                merged_norm,
            )
            return base_result
    except Exception:  # noqa: BLE001
        logger.debug("p100.barcode_extraction.gpt_supplement_gcd_check_skipped", exc_info=True)
    logger.info(
        "p100.barcode_extraction.gpt_supplement_merged main=%s supplement=%s full=%s",
        main_norm,
        supplement,
        merged_norm,
    )
    out = dict(base_result)
    out["barcode"] = merged_norm
    out["method"] = "gpt_barcode_read+supplement"
    return out


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

    crop_bytes, crop_used = _vision_crop_bytes(image_bytes, wide_crop=wide_crop)
    model = settings.photo_import_barcode_read_model or "gpt-4o"
    timeout_seconds = float(settings.photo_import_barcode_read_timeout_seconds or 45.0)
    logger.info("p100.barcode_extraction.gpt_fallback crop=%s model=%s timeout=%.0f", crop_used, model, timeout_seconds)
    try:
        parsed, _payload, _raw, _model = call_comic_vision(
            crop_bytes,
            model=model,
            api_key=settings.openai_api_key,
            log_context=log_context,
            system=COMIC_BARCODE_FOCUS_SYSTEM,
            user=COMIC_BARCODE_FOCUS_USER,
            image_detail="high",
            max_image_side_px=2048,
            timeout_seconds=timeout_seconds,
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
    result = {
        "barcode": code,
        "barcode_type": "upc_a",
        "confidence": float(conf),
        "method": "gpt_barcode_read",
        "crop_used": crop_used,
        "error": None,
    }
    return _merge_gpt_main_and_supplement(
        image_bytes,
        main_code=code,
        log_context=log_context,
        base_result=result,
    )


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
        if gpt_code and len(normalize_upc(gpt_code)) >= 17:
            return gpt
        if gpt_code and (not needs_supplement or not direct_market_requires_supplement_key(gpt_code)):
            return gpt
        if gpt_code and direct_market_requires_supplement_key(gpt_code):
            merged = _merge_gpt_main_and_supplement(
                image_bytes,
                main_code=gpt_code,
                log_context=log_context,
                base_result=gpt,
            )
            if len(normalize_upc(merged.get("barcode") or "")) >= 17:
                return merged

    if local.get("barcode"):
        return local
    if allow_gpt_fallback and not needs_supplement:
        gpt = _gpt_barcode_fallback(image_bytes, log_context=log_context, wide_crop=False)
        if gpt.get("barcode"):
            return gpt
    return local if local.get("error") else _empty_result()
