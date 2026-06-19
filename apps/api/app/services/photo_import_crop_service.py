"""P100-14A persist and serve per-detection crop images."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat

from app.services.photo_import_cover_boundary_service import log_boundary_result, refine_cover_boundary
from app.services.photo_import_storage_service import REPO_ROOT

logger = logging.getLogger(__name__)

API_ROOT = REPO_ROOT

# Per-side padding (12–18% range; use 15%).
CROP_EXPAND_SIDE_FRACTION = 0.15
# Typical comic cover width / height in normalized crop space.
COMIC_TARGET_WIDTH_HEIGHT_RATIO = 0.65
MIN_CROP_PIXELS = 72
MIN_BBOX_AREA_FRACTION = 0.015


@dataclass(frozen=True)
class CropSaveResult:
    relative_path: str
    width: int
    height: int
    expanded_bbox: dict[str, float]
    refined_bbox: dict[str, float]
    crop_quality: str
    crop_area_percent: float
    bbox_expansion_percent: float
    boundary_confidence: float
    boundary_method: str


def clamp_bbox01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bbox_components(bbox: dict[str, float]) -> tuple[float, float, float, float]:
    x = clamp_bbox01(bbox.get("x", 0.0))
    y = clamp_bbox01(bbox.get("y", 0.0))
    w = max(0.01, clamp_bbox01(bbox.get("width", 0.0)))
    h = max(0.01, clamp_bbox01(bbox.get("height", 0.0)))
    if w <= 0.01:
        w = 0.01
    if h <= 0.01:
        h = 0.01
    return x, y, w, h


def _bbox_dict(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {
        "x": clamp_bbox01(x),
        "y": clamp_bbox01(y),
        "width": clamp_bbox01(w),
        "height": clamp_bbox01(h),
    }


def _clamp_bbox_to_image_bounds(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    """Keep bbox inside [0,1]; shift inward when expansion crosses an edge."""
    w = max(0.01, min(1.0, w))
    h = max(0.01, min(1.0, h))
    if x < 0.0:
        w = max(0.01, w + x)
        x = 0.0
    if y < 0.0:
        h = max(0.01, h + y)
        y = 0.0
    if x + w > 1.0:
        overflow = x + w - 1.0
        if x >= overflow:
            x = max(0.0, x - overflow)
        else:
            x = 0.0
            w = 1.0
    if y + h > 1.0:
        overflow = y + h - 1.0
        if y >= overflow:
            y = max(0.0, y - overflow)
        else:
            y = 0.0
            h = 1.0
    w = max(0.01, min(1.0 - x, w))
    h = max(0.01, min(1.0 - y, h))
    return x, y, w, h


def expand_bbox_for_comic_crop(bbox: dict[str, float]) -> dict[str, float]:
    """Expand bbox for cropping; original bbox should remain stored separately in DB."""
    x, y, w, h = _bbox_components(bbox)
    cx = x + w / 2.0
    cy = y + h / 2.0

    pad = CROP_EXPAND_SIDE_FRACTION
    w = w * (1.0 + 2.0 * pad)
    h = h * (1.0 + 2.0 * pad)
    x = cx - w / 2.0
    y = cy - h / 2.0

    if h > 1e-6:
        wh = w / h
        target = COMIC_TARGET_WIDTH_HEIGHT_RATIO
        tolerance = 0.08
        if wh > target + tolerance:
            h = w / target
            y = cy - h / 2.0
        elif wh < target - tolerance:
            w = h * target
            x = cx - w / 2.0

    x, y, w, h = _clamp_bbox_to_image_bounds(x, y, w, h)
    return _bbox_dict(x, y, w, h)


def _bbox_area_fraction(bbox: dict[str, float]) -> float:
    return float(bbox.get("width", 0)) * float(bbox.get("height", 0))


def _expansion_percent(original: dict[str, float], expanded: dict[str, float]) -> float:
    orig = _bbox_area_fraction(original)
    if orig <= 0:
        return 0.0
    return round(((_bbox_area_fraction(expanded) - orig) / orig) * 100.0, 1)


def _background_uniformity_score(crop: Image.Image) -> float:
    """0 = varied (likely content), 1 = uniform (likely empty background)."""
    gray = crop.convert("L").resize((min(64, crop.width), min(64, crop.height)))
    stat = ImageStat.Stat(gray)
    if not stat.stddev:
        return 1.0
    std = stat.stddev[0]
    return max(0.0, min(1.0, 1.0 - std / 64.0))


def assess_crop_quality(
    *,
    pixel_width: int,
    pixel_height: int,
    expanded_bbox: dict[str, float],
    background_uniformity: float,
) -> str:
    if min(pixel_width, pixel_height) < MIN_CROP_PIXELS:
        return "poor"
    area = _bbox_area_fraction(expanded_bbox)
    if area < MIN_BBOX_AREA_FRACTION:
        return "poor"
    if pixel_width > 0 and pixel_height > 0:
        wh = pixel_width / pixel_height
        if wh > 1.35 or wh < 0.35:
            return "warning"
    if min(pixel_width, pixel_height) < 100:
        return "warning"
    if background_uniformity >= 0.92:
        return "poor"
    if background_uniformity >= 0.82:
        return "warning"
    return "good"


def crop_storage_dir(*, session_id: int) -> Path:
    path = REPO_ROOT / "data" / "photo_import" / "crops" / str(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_and_save_crop(
    image_path: Path,
    bbox: dict[str, float],
    *,
    session_id: int,
    image_id: int,
    idx: int,
) -> CropSaveResult:
    """Crop source photo with expanded bbox; return path, size, and quality metadata."""
    crop_dir = crop_storage_dir(session_id=session_id)
    crop_name = f"{image_id}_{idx}.jpg"
    crop_path = crop_dir / crop_name
    expanded = expand_bbox_for_comic_crop(bbox)
    with Image.open(image_path) as img:
        img_w, img_h = img.size
        boundary = refine_cover_boundary(
            image_path,
            original_bbox=bbox,
            expanded_bbox=expanded,
            image_width=img_w,
            image_height=img_h,
        )
        log_boundary_result(
            image_id=image_id,
            index=idx,
            original_bbox=bbox,
            expanded_bbox=expanded,
            result=boundary,
        )
        crop_bbox = boundary.refined_bbox if not boundary.used_fallback else expanded
        x = int(crop_bbox["x"] * img_w)
        y = int(crop_bbox["y"] * img_h)
        bw = max(1, int(crop_bbox["width"] * img_w))
        bh = max(1, int(crop_bbox["height"] * img_h))
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        right = min(img_w, x + bw)
        bottom = min(img_h, y + bh)
        cropped = img.crop((x, y, right, bottom))
        cropped.convert("RGB").save(crop_path, format="JPEG", quality=90)
        cw, ch = cropped.size
        bg_uniformity = _background_uniformity_score(cropped)
    expansion_pct = _expansion_percent(bbox, expanded)
    area_pct = round((cw * ch) / max(img_w * img_h, 1) * 100.0, 2)
    quality = assess_crop_quality(
        pixel_width=cw,
        pixel_height=ch,
        expanded_bbox=crop_bbox,
        background_uniformity=bg_uniformity,
    )
    if quality in {"poor", "warning"}:
        logger.warning(
            "photo_import.crop.quality image_id=%s index=%s crop_quality=%s crop_dimensions=%sx%s "
            "crop_area_percent=%s bbox_expansion_percent=%s background_uniformity=%.2f",
            image_id,
            idx,
            quality,
            cw,
            ch,
            area_pct,
            expansion_pct,
            bg_uniformity,
        )
    logger.info(
        "photo_import.crop.saved image_id=%s index=%s original_bbox=%s expanded_bbox=%s refined_bbox=%s "
        "crop_dimensions=%sx%s crop_area_percent=%s bbox_expansion_percent=%s crop_quality=%s "
        "boundary_confidence=%s boundary_method=%s",
        image_id,
        idx,
        bbox,
        expanded,
        boundary.refined_bbox,
        cw,
        ch,
        area_pct,
        expansion_pct,
        quality,
        boundary.boundary_confidence,
        boundary.boundary_method,
    )
    rel = str(crop_path.relative_to(REPO_ROOT)).replace("\\", "/")
    return CropSaveResult(
        relative_path=rel,
        width=cw,
        height=ch,
        expanded_bbox=expanded,
        refined_bbox=boundary.refined_bbox,
        crop_quality=quality,
        crop_area_percent=area_pct,
        bbox_expansion_percent=expansion_pct,
        boundary_confidence=boundary.boundary_confidence,
        boundary_method=boundary.boundary_method,
    )


def resolve_crop_abs_path(crop_path: str | None) -> Path | None:
    if not crop_path or not str(crop_path).strip():
        return None
    rel = str(crop_path).strip().lstrip("/")
    candidate = REPO_ROOT / rel
    if candidate.is_file():
        return candidate
    return None


def crop_api_path(*, detection_id: int) -> str:
    return f"/api/v1/photo-import/detections/{int(detection_id)}/crop-image"
