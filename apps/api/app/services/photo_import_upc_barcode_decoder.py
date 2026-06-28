"""1D UPC/EAN decode from comic cover photos (OpenCV / pyzbar), before GPT barcode fallback."""

from __future__ import annotations

import io
import logging
from typing import Any, Callable

from PIL import Image, ImageEnhance, ImageOps

from app.services.catalog_ingestion_service import merge_comic_upc_decodes, normalize_upc, upc_check_digit_valid
from app.services.photo_import_barcode_vision import crop_upc_region_bytes, sanitize_vision_barcode

logger = logging.getLogger(__name__)


def _pil_from_bytes(image_bytes: bytes) -> Image.Image:
    with Image.open(io.BytesIO(image_bytes)) as img:
        return img.convert("RGB")


def _bgr_from_pil(pil: Image.Image) -> Any:
    import cv2
    import numpy as np

    rgb = np.asarray(pil)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _opencv_available() -> bool:
    try:
        import cv2  # noqa: F401

        return hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector")
    except ImportError:
        return False


def _pyzbar_available() -> bool:
    try:
        from pyzbar.pyzbar import decode as _decode  # noqa: F401

        return True
    except (ImportError, OSError, FileNotFoundError):
        return False


def _collect_valid_upc(candidates: list[str]) -> str | None:
    merged = merge_comic_upc_decodes(candidates)
    if merged:
        return merged
    for raw in candidates:
        code = sanitize_vision_barcode(raw)
        if code:
            return code
        digits = normalize_upc(raw)
        if digits and upc_check_digit_valid(digits):
            return digits
    return None


def _decode_opencv_bgr(bgr: Any) -> list[str]:
    import cv2

    det = cv2.barcode.BarcodeDetector()
    found: list[str] = []
    try:
        ok, info, _typ = det.detectAndDecode(bgr)
        if ok and info:
            found.append(str(info).strip())
    except Exception:  # noqa: BLE001
        pass
    try:
        ok, infos, _types, _points = det.detectAndDecodeMulti(bgr)
        if ok and infos is not None:
            if isinstance(infos, str):
                found.append(infos.strip())
            else:
                for item in infos:
                    if item:
                        found.append(str(item).strip())
    except Exception:  # noqa: BLE001
        pass
    return found


def _decode_pyzbar_pil(pil: Image.Image) -> list[str]:
    from pyzbar.pyzbar import decode as pyzbar_decode

    out: list[str] = []
    for symbol in pyzbar_decode(pil):
        try:
            text = symbol.data.decode("utf-8", errors="ignore").strip()
        except AttributeError:
            text = str(symbol.data).strip()
        if text:
            out.append(text)
    return out


def _preprocess_pil_variants(pil: Image.Image) -> list[Image.Image]:
    variants: list[Image.Image] = [pil]
    gray = ImageOps.grayscale(pil)
    variants.append(ImageOps.autocontrast(gray).convert("RGB"))
    sharp = ImageEnhance.Contrast(pil).enhance(1.6)
    variants.append(ImageEnhance.Sharpness(sharp).enhance(2.0))
    return variants


def _image_byte_variants(image_bytes: bytes) -> list[tuple[str, bytes]]:
    crop = crop_upc_region_bytes(image_bytes)
    variants: list[tuple[str, bytes]] = [("full", image_bytes)]
    if crop != image_bytes:
        variants.append(("upc_crop", crop))
    return variants


def _try_backends_on_pil(
    pil: Image.Image,
    *,
    opencv_fn: Callable[[Any], list[str]] | None,
    pyzbar_fn: Callable[[Image.Image], list[str]] | None,
) -> tuple[str, str] | None:
    candidates: list[str] = []
    last_label = "raw"
    for label, processed in [("raw", pil), *[(f"pp{i}", p) for i, p in enumerate(_preprocess_pil_variants(pil)[1:])]]:
        last_label = label
        if opencv_fn is not None:
            candidates.extend(opencv_fn(_bgr_from_pil(processed)))
        if pyzbar_fn is not None:
            candidates.extend(pyzbar_fn(processed))
    code = _collect_valid_upc(candidates)
    if code:
        return code, f"merged:{last_label}"
    return None


def collect_raw_upc_candidates_from_pil(pil: Image.Image) -> list[str]:
    """All 1D decode strings from one image (no merge)."""
    opencv_fn = _decode_opencv_bgr if _opencv_available() else None
    pyzbar_fn = _decode_pyzbar_pil if _pyzbar_available() else None
    if opencv_fn is None and pyzbar_fn is None:
        return []
    candidates: list[str] = []
    w, h = pil.size
    scales = [1.0]
    if max(w, h) < 500 or h < 360:
        scales.extend([2.0, 3.0])
    for scale in scales:
        source = pil
        if scale != 1.0:
            source = pil.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        for processed in _preprocess_pil_variants(source):
            if opencv_fn is not None:
                candidates.extend(opencv_fn(_bgr_from_pil(processed)))
            if pyzbar_fn is not None:
                candidates.extend(pyzbar_fn(processed))
    return candidates


def decode_upc_from_image_bytes(image_bytes: bytes) -> tuple[str, str] | None:
    """Return (normalized_upc, source_tag) or None if no valid UPC decoded."""
    if not image_bytes:
        return None

    use_opencv = _opencv_available()
    use_pyzbar = _pyzbar_available()
    if not use_opencv and not use_pyzbar:
        logger.debug("photo_import.upc_decoder unavailable (no opencv or pyzbar)")
        return None

    opencv_fn = _decode_opencv_bgr if use_opencv else None
    pyzbar_fn = _decode_pyzbar_pil if use_pyzbar else None

    all_candidates: list[str] = []
    for region_label, blob in _image_byte_variants(image_bytes):
        try:
            pil = _pil_from_bytes(blob)
        except Exception:  # noqa: BLE001
            continue
        all_candidates.extend(collect_raw_upc_candidates_from_pil(pil))
    code = _collect_valid_upc(all_candidates)
    if code:
        logger.info("photo_import.upc_decoder hit barcode=%s candidates=%d", code, len(all_candidates))
        return code, "merged:all_regions"
    return None
