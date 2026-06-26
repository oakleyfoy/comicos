"""P105: expanded UPC box crops and sub-regions (bars vs supplemental OCR)."""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

RegionName = Literal["full_expanded", "main_bars", "left_supplement", "right_cover_digit"]

Box = tuple[int, int, int, int]

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


# ---------------------------------------------------------------------------
# Geometry-based detection (price box -> bars -> printed left supplement)
# ---------------------------------------------------------------------------


@dataclass
class BarcodeRegionGeometry:
    """Region boxes in ORIGINAL image coordinates (for overlay + crops)."""

    full_expanded: Box
    main_bars: Box
    left_supplement: Box
    right_cover_digit: Box
    price_box: Box | None = None
    deskew_angle: float = 0.0
    detection_method: str = "percentage"

    def as_dict(self) -> dict[str, Any]:
        return {
            "full_expanded": list(self.full_expanded),
            "main_bars": list(self.main_bars),
            "left_supplement": list(self.left_supplement),
            "right_cover_digit": list(self.right_cover_digit),
            "price_box": list(self.price_box) if self.price_box else None,
            "deskew_angle": self.deskew_angle,
            "detection_method": self.detection_method,
        }


def _clamp_box(box: Box, width: int, height: int) -> Box:
    left, top, right, bottom = box
    left = max(0, min(int(left), width - 1))
    top = max(0, min(int(top), height - 1))
    right = max(left + 1, min(int(right), width))
    bottom = max(top + 1, min(int(bottom), height))
    return left, top, right, bottom


def _detect_price_box(pil_roi: Image.Image) -> tuple[Box | None, float]:
    """Detect the bright rectangular UPC/price box inside the ROI (OpenCV optional).

    Returns ((left, top, right, bottom) in ROI coords, deskew_angle) or (None, 0.0).
    """
    try:
        import cv2
        import numpy as np
    except Exception:  # noqa: BLE001 - OpenCV optional; fall back to percentages
        return None, 0.0
    try:
        rgb = np.asarray(pil_roi.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape[:2]
        _thr, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 60), max(3, h // 30)))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best: Box | None = None
        best_angle = 0.0
        best_area = 0.0
        roi_area = float(w * h)
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = float(bw * bh)
            if area < roi_area * 0.05 or area > roi_area * 0.95:
                continue
            aspect = bw / max(1, bh)
            if aspect < 1.3 or aspect > 7.0:
                continue
            if area > best_area:
                best_area = area
                best = (x, y, x + bw, y + bh)
                rect = cv2.minAreaRect(cnt)
                angle = float(rect[-1])
                if angle < -45:
                    angle += 90
                best_angle = max(-15.0, min(15.0, angle))
        return best, best_angle
    except Exception as exc:  # noqa: BLE001
        logger.debug("p105.price_box_detect_fail err=%s", exc)
        return None, 0.0


def compute_barcode_region_geometry(
    pil: Image.Image,
    *,
    config: BarcodeCropConfig = DEFAULT_BARCODE_CROP_CONFIG,
) -> BarcodeRegionGeometry:
    """Compute region boxes in original-image coordinates, preferring detected price box."""
    w, h = pil.size
    fe = expand_box(0, int(h * 0.52), w, h, w, h, expand_ratio=config.clamped_expand_ratio())
    fe = _clamp_box(fe, w, h)

    price_box: Box | None = None
    deskew_angle = 0.0
    method = "percentage"
    roi = pil.crop(fe)
    detected, angle = _detect_price_box(roi)
    if detected is not None:
        dl, dt, dr, db = detected
        price_box = _clamp_box((fe[0] + dl, fe[1] + dt, fe[0] + dr, fe[1] + db), w, h)
        deskew_angle = angle
        method = "geometry"

    base = price_box if price_box is not None else fe
    bl, bt, br, bb = base
    bw = max(1, br - bl)
    bh = max(1, bb - bt)

    row_top = bt + int(bh * 0.16)
    row_bottom = bb - int(bh * 0.16)
    left_end = bl + int(bw * 0.32)
    bars_left = bl + int(bw * 0.16)
    bars_right = bl + int(bw * 0.74)
    right_start = bl + int(bw * 0.74)

    geometry = BarcodeRegionGeometry(
        full_expanded=fe,
        main_bars=_clamp_box((bars_left, bt, bars_right, bb), w, h),
        left_supplement=_clamp_box((bl, row_top, left_end, row_bottom), w, h),
        right_cover_digit=_clamp_box((right_start, row_top, br, row_bottom), w, h),
        price_box=price_box,
        deskew_angle=deskew_angle,
        detection_method=method,
    )
    return geometry


def crops_from_geometry(pil: Image.Image, geometry: BarcodeRegionGeometry) -> dict[RegionName, Image.Image]:
    return {
        "full_expanded": pil.crop(geometry.full_expanded),
        "main_bars": pil.crop(geometry.main_bars),
        "left_supplement": pil.crop(geometry.left_supplement),
        "right_cover_digit": pil.crop(geometry.right_cover_digit),
    }


def left_supplement_crop_variants(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
) -> list[tuple[str, Image.Image]]:
    """Geometry-shifted crop candidates for the printed left supplement digits."""
    w, h = pil.size
    left, top, right, bottom = geometry.left_supplement
    bw = max(1, right - left)
    bh = max(1, bottom - top)
    dx = max(4, int(bw * 0.18))
    dy = max(4, int(bh * 0.18))
    ex = max(4, int(bw * 0.30))
    ey = max(4, int(bh * 0.30))

    boxes: list[tuple[str, Box]] = [
        ("original", (left, top, right, bottom)),
        ("wider", (left - ex, top, right + ex, bottom)),
        ("taller", (left, top - ey, right, bottom + ey)),
        ("shift_left", (left - dx, top, right - dx, bottom)),
        ("shift_right", (left + dx, top, right + dx, bottom)),
        ("shift_up", (left, top - dy, right, bottom - dy)),
        ("shift_down", (left, top + dy, right, bottom + dy)),
    ]
    out: list[tuple[str, Image.Image]] = []
    for label, box in boxes:
        out.append((label, pil.crop(_clamp_box(box, w, h))))
    return out


_OVERLAY_COLORS: dict[str, tuple[int, int, int]] = {
    "full_expanded": (80, 160, 255),
    "price_box": (255, 80, 200),
    "main_bars": (255, 200, 0),
    "left_supplement": (0, 230, 90),
    "right_cover_digit": (255, 120, 0),
}


def draw_region_overlay(pil: Image.Image, geometry: BarcodeRegionGeometry) -> Image.Image:
    """Original capture with labeled rectangles for each detected region."""
    overlay = pil.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    width = max(2, int(min(pil.size) * 0.004))
    entries: list[tuple[str, Box | None]] = [
        ("full_expanded", geometry.full_expanded),
        ("price_box", geometry.price_box),
        ("main_bars", geometry.main_bars),
        ("left_supplement", geometry.left_supplement),
        ("right_cover_digit", geometry.right_cover_digit),
    ]
    for label, box in entries:
        if box is None:
            continue
        color = _OVERLAY_COLORS.get(label, (255, 255, 255))
        draw.rectangle(box, outline=color, width=width)
        text_y = max(0, box[1] - 14)
        try:
            draw.text((box[0] + 2, text_y), label, fill=color)
        except Exception:  # noqa: BLE001 - default font may be unavailable
            pass
    return overlay


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


def save_barcode_region_debug_to_dir(
    base: Path,
    regions: dict[RegionName, Image.Image],
    *,
    ocr_debug: dict[str, Any],
    overlay: Image.Image | None = None,
    left_variants: list[tuple[str, Image.Image]] | None = None,
) -> str:
    """Persist region crops, overlay, variant crops, and OCR metadata to an explicit dir."""
    base.mkdir(parents=True, exist_ok=True)
    for name, pil in regions.items():
        out = base / f"{name}.jpg"
        out.write_bytes(pil_to_jpeg_bytes(pil))
    if overlay is not None:
        (base / "overlay.jpg").write_bytes(pil_to_jpeg_bytes(overlay))
    if left_variants:
        variant_dir = base / "left_variants"
        variant_dir.mkdir(parents=True, exist_ok=True)
        for label, pil in left_variants:
            safe = label.replace("|", "_").replace("/", "_")
            (variant_dir / f"{safe}.jpg").write_bytes(pil_to_jpeg_bytes(pil))
    meta_path = base / "ocr_debug.json"
    meta_path.write_text(json.dumps(ocr_debug, indent=2, default=str), encoding="utf-8")
    logger.info("p105.barcode_debug_saved dir=%s", base)
    return str(base)


def save_barcode_region_debug_crops(
    intake_item_id: int,
    regions: dict[RegionName, Image.Image],
    *,
    ocr_debug: dict[str, Any],
    overlay: Image.Image | None = None,
    left_variants: list[tuple[str, Image.Image]] | None = None,
) -> str:
    """Persist intake-item debug crops under the standard P105 debug root."""
    base = P105_BARCODE_DEBUG_ROOT / str(int(intake_item_id))
    return save_barcode_region_debug_to_dir(
        base,
        regions,
        ocr_debug=ocr_debug,
        overlay=overlay,
        left_variants=left_variants,
    )
