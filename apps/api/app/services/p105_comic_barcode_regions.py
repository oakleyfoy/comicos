"""P105: expanded UPC box crops and sub-regions (bars vs supplemental OCR)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

from PIL import Image

RegionName = Literal["full_expanded", "main_bars", "left_supplement", "right_cover_digit"]


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
    """Split expanded UPC crop: left supplement OCR, center bars decode, right cover digit OCR."""
    w, h = upc_crop.size
    pad = int(min(w, h) * config.clamped_expand_ratio() * 0.5)
    left_end = max(pad + 1, int(w * 0.22))
    right_start = min(w - pad - 1, int(w * 0.82))
    regions: dict[RegionName, Image.Image] = {
        "full_expanded": upc_crop,
        "left_supplement": upc_crop.crop((0, 0, left_end, h)),
        "main_bars": upc_crop.crop((left_end, 0, right_start, h)),
        "right_cover_digit": upc_crop.crop((right_start, 0, w, h)),
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
