"""Barcode extraction helpers for photo import (GPT + validation)."""

from __future__ import annotations

import io
import re

from app.services.catalog_ingestion_service import merge_comic_upc_decodes, normalize_upc, upc_check_digit_valid


def normalize_comic_scan_barcode(raw: str | None) -> str:
    """Digits-only comic UPC key (12-digit UPC-A plus optional 5-digit supplement when present)."""
    digits = normalize_upc(raw or "")
    if not digits.isdigit() or len(digits) < 11:
        return ""
    merged = merge_comic_upc_decodes([digits])
    if merged:
        return merged
    if len(digits) >= 17 and digits.isdigit():
        return digits[:17]
    return sanitize_vision_barcode(raw)


def sanitize_vision_barcode(raw: str | None) -> str:
    """Digits-only UPC when check digit validates; otherwise empty (unread / hallucinated)."""
    normalized = normalize_upc(raw or "")
    if len(normalized) < 11:
        return ""
    if not upc_check_digit_valid(normalized):
        return ""
    return normalized


def barcode_needs_focus_pass(raw: str | None) -> bool:
    """True when we should run a slow, cropped barcode-only vision pass."""
    return not sanitize_vision_barcode(raw)


def crop_upc_region_bytes(image_bytes: bytes) -> bytes:
    """Crop lower-left where UPC boxes usually appear; upscale small crops for legibility."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            w, h = img.size
            left = 0
            top = max(0, int(h * 0.52))
            right = max(1, int(w * 0.88))
            bottom = h
            crop = img.crop((left, top, right, bottom))
            cw, ch = crop.size
            target = 1600
            longest = max(cw, ch)
            if longest < target and longest > 0:
                scale = target / float(longest)
                crop = crop.resize(
                    (max(1, int(cw * scale)), max(1, int(ch * scale))),
                    Image.Resampling.LANCZOS,
                )
            out = io.BytesIO()
            crop.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue()
    except Exception:
        return image_bytes


def parse_barcode_focus_payload(payload: dict) -> tuple[str, float, str]:
    raw = str(payload.get("barcode") or payload.get("barcode_text") or "")
    digits = re.sub(r"\D", "", raw)
    code = normalize_comic_scan_barcode(digits)
    try:
        confidence = max(0.0, min(1.0, float(payload.get("confidence") or 0.0)))
    except (TypeError, ValueError):
        confidence = 0.0
    reasoning = str(payload.get("reasoning") or "").strip()
    return code, confidence, reasoning
