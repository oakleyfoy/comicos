"""P100-19 cover boundary refinement (document-scanner style, conservative fallback)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat

logger = logging.getLogger(__name__)

MIN_BOUNDARY_CONFIDENCE = 0.35


@dataclass(frozen=True)
class CoverBoundaryResult:
    refined_bbox: dict[str, float]
    boundary_confidence: float
    boundary_method: str
    cover_corners: dict[str, dict[str, float]] | None
    used_fallback: bool


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bbox_area(b: dict[str, float]) -> float:
    return float(b.get("width", 0)) * float(b.get("height", 0))


def _bbox_dict(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {"x": _clamp01(x), "y": _clamp01(y), "width": _clamp01(w), "height": _clamp01(h)}


def _corners_from_bbox(b: dict[str, float]) -> dict[str, dict[str, float]]:
    x, y, w, h = b["x"], b["y"], b["width"], b["height"]
    return {
        "top_left": {"x": x, "y": y},
        "top_right": {"x": x + w, "y": y},
        "bottom_right": {"x": x + w, "y": y + h},
        "bottom_left": {"x": x, "y": y + h},
    }


def _content_bbox_in_crop(crop: Image.Image) -> tuple[int, int, int, int] | None:
    """Find tight content bounds inside a crop using edge/variance heuristics (PIL only)."""
    gray = crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(gray)
    mean = stat.mean[0] if stat.mean else 128.0
    w, h = gray.size
    if w < 8 or h < 8:
        return None
    threshold = max(12.0, mean * 0.12)
    pixels = gray.load()
    edge_pixels = edges.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    found = False
    for yy in range(h):
        for xx in range(w):
            if edge_pixels[xx, yy] > threshold or abs(pixels[xx, yy] - mean) > threshold * 1.5:
                found = True
                min_x = min(min_x, xx)
                min_y = min(min_y, yy)
                max_x = max(max_x, xx)
                max_y = max(max_y, yy)
    if not found:
        return None
    pad_x = max(2, int(w * 0.02))
    pad_y = max(2, int(h * 0.02))
    min_x = max(0, min_x - pad_x)
    min_y = max(0, min_y - pad_y)
    max_x = min(w - 1, max_x + pad_x)
    max_y = min(h - 1, max_y + pad_y)
    if max_x - min_x < 4 or max_y - min_y < 4:
        return None
    return min_x, min_y, max_x + 1, max_y + 1


def refine_cover_boundary(
    image_path: Path,
    *,
    original_bbox: dict[str, float],
    expanded_bbox: dict[str, float],
    image_width: int,
    image_height: int,
) -> CoverBoundaryResult:
    """Refine bbox within expanded region; never return materially smaller than original."""
    fallback = CoverBoundaryResult(
        refined_bbox=dict(expanded_bbox),
        boundary_confidence=0.0,
        boundary_method="fallback_expanded_bbox",
        cover_corners=_corners_from_bbox(expanded_bbox),
        used_fallback=True,
    )
    if not image_path.is_file() or image_width <= 0 or image_height <= 0:
        return fallback

    try:
        with Image.open(image_path) as img:
            w, h = img.size
            ex = expanded_bbox
            x0 = int(_clamp01(ex["x"]) * w)
            y0 = int(_clamp01(ex["y"]) * h)
            x1 = int(_clamp01(ex["x"] + ex["width"]) * w)
            y1 = int(_clamp01(ex["y"] + ex["height"]) * h)
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(w, max(x0 + 1, x1)), min(h, max(y0 + 1, y1))
            region = img.crop((x0, y0, x1, y1))
            inner = _content_bbox_in_crop(region)
            if inner is None:
                return fallback
            ix0, iy0, ix1, iy1 = inner
            rw, rh = region.size
            rx = (x0 + ix0) / w
            ry = (y0 + iy0) / h
            rw_norm = (ix1 - ix0) / w
            rh_norm = (iy1 - iy0) / h
            refined = _bbox_dict(rx, ry, rw_norm, rh_norm)
            orig_area = _bbox_area(original_bbox)
            refined_area = _bbox_area(refined)
            expanded_area = _bbox_area(expanded_bbox)
            if refined_area < orig_area * 0.92:
                return fallback
            if refined_area < expanded_area * 0.85:
                return fallback
            wh = refined["width"] / max(refined["height"], 1e-6)
            if wh > 1.25 or wh < 0.35:
                return fallback
            confidence = min(0.95, 0.45 + (refined_area / max(expanded_area, 1e-6)) * 0.35)
            if confidence < MIN_BOUNDARY_CONFIDENCE:
                return fallback
            return CoverBoundaryResult(
                refined_bbox=refined,
                boundary_confidence=round(confidence, 3),
                boundary_method="pil_edge_contour",
                cover_corners=_corners_from_bbox(refined),
                used_fallback=False,
            )
    except OSError:
        return fallback


def log_boundary_result(
    *,
    image_id: int,
    index: int,
    original_bbox: dict[str, float],
    expanded_bbox: dict[str, float],
    result: CoverBoundaryResult,
) -> None:
    logger.info(
        "photo_import.boundary image_id=%s index=%s original_bbox=%s expanded_bbox=%s "
        "refined_bbox=%s confidence=%s method=%s fallback=%s corners=%s",
        image_id,
        index,
        original_bbox,
        expanded_bbox,
        result.refined_bbox,
        result.boundary_confidence,
        result.boundary_method,
        result.used_fallback,
        result.cover_corners,
    )
