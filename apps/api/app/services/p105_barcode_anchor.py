"""P105: locate UPC bar strip and derive supplement crop by fixed math (no search)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from PIL import Image

from app.services.p105_comic_barcode_regions import Box, _clamp_box, _box_xywh

logger = logging.getLogger(__name__)

# Printed supplement sits immediately left of the vertical bar code.
BARCODE_SUPPLEMENT_GAP_PX = 4
BARCODE_SUPPLEMENT_WIDTH_RATIO = 0.28
BARCODE_COVER_DIGIT_WIDTH_RATIO = 0.14
BARCODE_COVER_DIGIT_GAP_PX = 4


@dataclass
class BarcodeBoundsDetection:
    """Axis-aligned UPC bar bounds in image coordinates."""

    box: Box | None = None
    source: str = ""
    opencv_barcode_module: bool = False
    exception_message: str | None = None
    corner_points: list[tuple[float, float]] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "box": _box_xywh(self.box) if self.box else None,
            "source": self.source,
            "opencv_barcode_module": self.opencv_barcode_module,
            "exception_message": self.exception_message,
            "corner_points": self.corner_points,
        }


def _box_from_points(points: list[tuple[float, float]], width: int, height: int) -> Box | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return _clamp_box((int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))), width, height)


def _detect_opencv_barcode_bounds(pil: Image.Image) -> BarcodeBoundsDetection:
    diag = BarcodeBoundsDetection()
    try:
        import cv2
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        diag.exception_message = str(exc)
        return diag

    if not hasattr(cv2, "barcode") or not hasattr(cv2.barcode, "BarcodeDetector"):
        diag.exception_message = "cv2.barcode.BarcodeDetector unavailable"
        return diag

    diag.opencv_barcode_module = True
    w, h = pil.size
    bgr = cv2.cvtColor(np.asarray(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
    det = cv2.barcode.BarcodeDetector()

    try:
        ok, points = det.detect(bgr)
        if ok and points is not None:
            flat = np.asarray(points, dtype=float).reshape(-1, 2)
            pts = [(float(x), float(y)) for x, y in flat]
            diag.corner_points = pts
            diag.box = _box_from_points(pts, w, h)
            if diag.box is not None:
                diag.source = "opencv_barcode_detector.detect"
                return diag
    except Exception as exc:  # noqa: BLE001
        logger.debug("p105.barcode_bounds.detect_fail err=%s", exc)

    try:
        ok, _infos, _types, corners = det.detectAndDecodeMulti(bgr)
        if ok and corners is not None:
            arr = np.asarray(corners, dtype=float)
            if arr.size >= 8:
                flat = arr.reshape(-1, 2)
                pts = [(float(x), float(y)) for x, y in flat]
                diag.corner_points = pts
                diag.box = _box_from_points(pts, w, h)
                if diag.box is not None:
                    diag.source = "opencv_barcode_detector.detectAndDecodeMulti"
                    return diag
    except Exception as exc:  # noqa: BLE001
        diag.exception_message = str(exc)

    return diag


def _detect_pyzbar_bounds(pil: Image.Image) -> BarcodeBoundsDetection:
    diag = BarcodeBoundsDetection(source="pyzbar")
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
    except Exception as exc:  # noqa: BLE001
        diag.exception_message = str(exc)
        return diag

    w, h = pil.size
    best_area = 0
    best_box: Box | None = None
    for sym in pyzbar_decode(pil):
        rect = sym.rect
        box = _clamp_box(
            (rect.left, rect.top, rect.left + rect.width, rect.top + rect.height),
            w,
            h,
        )
        area = (box[2] - box[0]) * (box[3] - box[1])
        if area > best_area:
            best_area = area
            best_box = box
    if best_box is not None:
        diag.box = best_box
        diag.source = "pyzbar.rect"
    return diag


def detect_upc_barcode_bounds(pil: Image.Image) -> BarcodeBoundsDetection:
    """Detect the UPC/EAN vertical bar region (anchor for supplement math)."""
    for fn in (_detect_opencv_barcode_bounds, _detect_pyzbar_bounds):
        diag = fn(pil)
        if diag.box is not None:
            logger.info(
                "p105.barcode_anchor detected box=%s source=%s",
                _box_xywh(diag.box),
                diag.source,
            )
            return diag
    logger.warning("p105.barcode_anchor no barcode bounds detected")
    return BarcodeBoundsDetection(source="none", exception_message="no barcode detected")


def compute_supplement_box_from_barcode(
    barcode: Box,
    image_width: int,
    image_height: int,
    *,
    gap_px: int = BARCODE_SUPPLEMENT_GAP_PX,
    width_ratio: float = BARCODE_SUPPLEMENT_WIDTH_RATIO,
) -> Box:
    """Derive left supplement ROI from measured bar edges (computed, not searched)."""
    bl, bt, br, bb = barcode
    bw = max(1, br - bl)
    bh = max(1, bb - bt)
    supplement_right = bl - gap_px
    supplement_width = max(1, int(bw * width_ratio))
    supplement_left = supplement_right - supplement_width
    return _clamp_box((supplement_left, bt, supplement_right, bb), image_width, image_height)


def compute_cover_digit_box_from_barcode(
    barcode: Box,
    image_width: int,
    image_height: int,
) -> Box:
    bl, bt, br, bb = barcode
    bw = max(1, br - bl)
    left = br + BARCODE_COVER_DIGIT_GAP_PX
    right = left + max(8, int(bw * BARCODE_COVER_DIGIT_WIDTH_RATIO))
    return _clamp_box((left, bt, right, bb), image_width, image_height)


def union_boxes(boxes: list[Box], image_width: int, image_height: int) -> Box:
    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = max(b[3] for b in boxes)
    return _clamp_box((left, top, right, bottom), image_width, image_height)
