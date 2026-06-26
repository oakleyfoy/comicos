"""P105: expanded UPC box crops and sub-regions (bars vs supplemental OCR)."""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image

logger = logging.getLogger(__name__)

RegionName = Literal["full_expanded", "main_bars", "left_supplement", "right_cover_digit"]

P105_BARCODE_DEBUG_ROOT = Path("data/p105/debug/barcode_regions")


@dataclass(frozen=True)
class BarcodeCropConfig:
    """Expand barcode crops before decode/OCR (default 12% on each side)."""

    expand_ratio: float = 0.12

    def clamped_expand_ratio(self) -> float:
        return max(0.10, min(0.15, float(self.expand_ratio)))


DEFAULT_BARCODE_CROP_CONFIG = BarcodeCropConfig()


def expand_box(
    left: int,
    top: int,
    right: int,
    bottom: int,
    width: int,
    height: int,
    *,
    expand_ratio: float,
) -> tuple[int, int, int, int]:
    w = max(1, right - left)
    h = max(1, bottom - top)
    pad_x = int(w * expand_ratio)
    pad_y = int(h * expand_ratio)
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(width, right + pad_x),
        min(height, bottom + pad_y),
    )


def crop_upc_region_pil(pil: Image.Image, *, config: BarcodeCropConfig = DEFAULT_BARCODE_CROP_CONFIG) -> Image.Image:
    """Lower portion of cover where price/UPC box usually lives, with expanded margins."""
    w, h = pil.size
    left = 0
    top = max(0, int(h * 0.52))
    right = w
    bottom = h
    box = expand_box(left, top, right, bottom, w, h, expand_ratio=config.clamped_expand_ratio())
    return pil.crop(box)


def split_barcode_box_regions(
    upc_crop: Image.Image,
    *,
    config: BarcodeCropConfig = DEFAULT_BARCODE_CROP_CONFIG,
) -> dict[RegionName, Image.Image]:
    """Split expanded UPC crop: left human-readable supplement, center bars, right cover digit."""
    w, h = upc_crop.size
    row_top = max(0, int(h * 0.20))
    row_bottom = min(h, int(h * 0.82))
    left_end = max(12, int(w * 0.30))
    bars_left = max(left_end - 2, int(w * 0.16))
    right_start = min(w - 12, int(w * 0.74))
    regions: dict[RegionName, Image.Image] = {
        "full_expanded": upc_crop,
        "left_supplement": upc_crop.crop((0, row_top, left_end, row_bottom)),
        "main_bars": upc_crop.crop((bars_left, 0, right_start, h)),
        "right_cover_digit": upc_crop.crop((right_start, row_top, w, row_bottom)),
    }
    return regions


def pil_to_jpeg_bytes(pil: Image.Image, *, quality: int = 95) -> bytes:
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def crop_upc_region_bytes_expanded(
    image_bytes: bytes,
    *,
    config: BarcodeCropConfig = DEFAULT_BARCODE_CROP_CONFIG,
) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as img:
        crop = crop_upc_region_pil(img.convert("RGB"), config=config)
        return pil_to_jpeg_bytes(crop)


def save_barcode_region_debug_crops(
    intake_item_id: int,
    regions: dict[RegionName, Image.Image],
    *,
    ocr_debug: dict[str, Any],
) -> str:
    """Persist region crops and OCR metadata for intake debugging."""
    base = P105_BARCODE_DEBUG_ROOT / str(int(intake_item_id))
    base.mkdir(parents=True, exist_ok=True)
    for name, pil in regions.items():
        out = base / f"{name}.jpg"
        out.write_bytes(pil_to_jpeg_bytes(pil))
    meta_path = base / "ocr_debug.json"
    meta_path.write_text(json.dumps(ocr_debug, indent=2, default=str), encoding="utf-8")
    logger.info("p105.barcode_debug_saved item_id=%s dir=%s", intake_item_id, base)
    return str(base)
