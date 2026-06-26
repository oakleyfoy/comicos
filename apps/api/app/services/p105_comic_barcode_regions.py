"""P105: expanded UPC box crops and sub-regions (bars vs supplemental OCR)."""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
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


# Minimum acceptable printed-supplement crop size (px). Below this OCR is hopeless.
MIN_LEFT_SUPPLEMENT_PX = 40
# A normal phone photo of a full cover is far larger than this on its long edge.
MIN_SANE_IMAGE_LONG_EDGE_PX = 200
# Cap the detection image size for speed; coords are mapped back to original.
_MAX_DETECT_LONG_EDGE_PX = 1600

# Known fallback_reason values when detection_method is "percentage".
FALLBACK_OPENCV_UNAVAILABLE = "opencv_unavailable"
FALLBACK_IMAGE_TOO_SMALL = "image_too_small"
FALLBACK_NO_BRIGHT_BOX_CANDIDATES = "no_bright_box_candidates"
FALLBACK_NO_VALID_PRICE_BOX_CONTOUR = "no_valid_price_box_contour"
FALLBACK_DETECTED_BOX_TOO_SMALL = "detected_box_too_small"
FALLBACK_LOW_CONTOUR_SCORE = "low_contour_score"
FALLBACK_COORDINATE_MAPPING_INVALID = "coordinate_mapping_invalid"
FALLBACK_EXCEPTION = "exception"


def opencv_import_status() -> tuple[bool, str | None]:
    """Return (opencv_available, import_error_message)."""
    try:
        import cv2  # noqa: F401

        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _box_xywh(box: Box) -> dict[str, int]:
    left, top, right, bottom = box
    return {"x": int(left), "y": int(top), "width": int(right - left), "height": int(bottom - top)}


def _box_w(box: Box) -> int:
    return int(box[2] - box[0])


def _box_h(box: Box) -> int:
    return int(box[3] - box[1])


@dataclass
class PriceBoxDetectionDiagnostics:
    """OpenCV price-box search diagnostics (coords are in ROI space when box is set)."""

    box: Box | None = None
    deskew_angle: float = 0.0
    detection_size: tuple[int, int] = (0, 0)
    detection_scale: float = 1.0
    opencv_available: bool = False
    contour_count: int = 0
    area_candidate_count: int = 0
    aspect_candidate_count: int = 0
    candidate_boxes: list[dict[str, Any]] = field(default_factory=list)
    chosen_candidate: dict[str, Any] | None = None
    coordinate_mapping_invalid: bool = False
    exception_message: str | None = None


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
    original_size: tuple[int, int] = (0, 0)
    working_size: tuple[int, int] = (0, 0)
    detection_size: tuple[int, int] = (0, 0)
    detection_scale: float = 1.0
    geometry_failed: bool = False
    min_region_px: int = MIN_LEFT_SUPPLEMENT_PX
    notes: list[str] = field(default_factory=list)
    geometry_attempted: bool = True
    opencv_available: bool = False
    fallback_reason: str = ""
    geometry_rejection_reason: str = ""
    exception_message: str | None = None
    contour_count: int = 0
    candidate_boxes: list[dict[str, Any]] = field(default_factory=list)
    chosen_candidate: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_size": {"width": self.original_size[0], "height": self.original_size[1]},
            "working_size": {"width": self.working_size[0], "height": self.working_size[1]},
            "detection_size": {"width": self.detection_size[0], "height": self.detection_size[1]},
            "detection_scale": self.detection_scale,
            "detection_method": self.detection_method,
            "geometry_attempted": self.geometry_attempted,
            "opencv_available": self.opencv_available,
            "fallback_reason": self.fallback_reason,
            "geometry_rejection_reason": self.geometry_rejection_reason,
            "exception_message": self.exception_message,
            "contour_count": self.contour_count,
            "candidate_boxes": list(self.candidate_boxes),
            "chosen_candidate": self.chosen_candidate,
            "deskew_angle": self.deskew_angle,
            "geometry_failed": self.geometry_failed,
            "min_region_px": self.min_region_px,
            "rectangles": {
                "full_expanded": _box_xywh(self.full_expanded),
                "price_box": _box_xywh(self.price_box) if self.price_box else None,
                "main_bars": _box_xywh(self.main_bars),
                "left_supplement": _box_xywh(self.left_supplement),
                "right_cover_digit": _box_xywh(self.right_cover_digit),
            },
            "notes": list(self.notes),
        }

    def report_lines(self) -> list[str]:
        lines = [
            f"original_size: {self.original_size[0]}x{self.original_size[1]}",
            f"working_size:  {self.working_size[0]}x{self.working_size[1]}",
            f"detection_size:{self.detection_size[0]}x{self.detection_size[1]} (scale={self.detection_scale:.4f})",
            f"detection_method: {self.detection_method}  deskew={self.deskew_angle:.1f}  failed={self.geometry_failed}",
            f"geometry_attempted: {self.geometry_attempted}  opencv_available: {self.opencv_available}",
            f"contour_count: {self.contour_count}  candidates: {len(self.candidate_boxes)}",
        ]
        if self.fallback_reason:
            lines.append(f"fallback_reason: {self.fallback_reason}")
        if self.geometry_rejection_reason:
            lines.append(f"geometry_rejection_reason: {self.geometry_rejection_reason}")
        if self.exception_message:
            lines.append(f"exception_message: {self.exception_message}")
        rects: list[tuple[str, Box | None]] = [
            ("full_expanded", self.full_expanded),
            ("price_box", self.price_box),
            ("main_bars", self.main_bars),
            ("left_supplement", self.left_supplement),
            ("right_cover_digit", self.right_cover_digit),
        ]
        for name, box in rects:
            if box is None:
                lines.append(f"  {name:18s} (none)")
                continue
            d = _box_xywh(box)
            lines.append(
                f"  {name:18s} x={d['x']:5d} y={d['y']:5d} w={d['width']:5d} h={d['height']:5d}"
            )
        for note in self.notes:
            lines.append(f"  note: {note}")
        return lines


def _clamp_box(box: Box, width: int, height: int) -> Box:
    left, top, right, bottom = box
    left = max(0, min(int(left), width - 1))
    top = max(0, min(int(top), height - 1))
    right = max(left + 1, min(int(right), width))
    bottom = max(top + 1, min(int(bottom), height))
    return left, top, right, bottom


def _resolve_percentage_fallback_reason(
    *,
    input_too_small: bool,
    det: PriceBoxDetectionDiagnostics,
    rejected_detected_box: bool,
) -> tuple[str, str]:
    """Return (fallback_reason, geometry_rejection_reason)."""
    rejection = ""
    if rejected_detected_box:
        rejection = FALLBACK_DETECTED_BOX_TOO_SMALL
        return FALLBACK_DETECTED_BOX_TOO_SMALL, rejection
    if input_too_small:
        return FALLBACK_IMAGE_TOO_SMALL, rejection
    if not det.opencv_available:
        return FALLBACK_OPENCV_UNAVAILABLE, rejection
    if det.exception_message and det.box is None:
        return FALLBACK_EXCEPTION, rejection
    if det.coordinate_mapping_invalid:
        return FALLBACK_COORDINATE_MAPPING_INVALID, rejection
    score_weak = any(
        c.get("passes_area") and c.get("passes_aspect") and not c.get("passes_score")
        for c in det.candidate_boxes
    )
    if score_weak and det.box is None and det.aspect_candidate_count > 0:
        return FALLBACK_LOW_CONTOUR_SCORE, rejection
    if det.contour_count == 0 or det.area_candidate_count == 0:
        return FALLBACK_NO_BRIGHT_BOX_CANDIDATES, rejection
    return FALLBACK_NO_VALID_PRICE_BOX_CONTOUR, rejection


def _detect_price_box(pil_roi: Image.Image) -> PriceBoxDetectionDiagnostics:
    """Detect the bright rectangular UPC/price box inside the ROI (OpenCV optional).

    Detection may run on a downscaled copy for speed; the returned box is mapped
    back to ROI coordinates.
    """
    roi_w, roi_h = pil_roi.size
    diag = PriceBoxDetectionDiagnostics(
        detection_size=(roi_w, roi_h),
        detection_scale=1.0,
    )
    opencv_ok, import_err = opencv_import_status()
    diag.opencv_available = opencv_ok
    if not opencv_ok:
        diag.exception_message = import_err
        return diag

    try:
        import cv2
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        diag.opencv_available = False
        diag.exception_message = str(exc)
        return diag

    scale = 1.0
    detect_img = pil_roi
    long_edge = max(roi_w, roi_h)
    if long_edge > _MAX_DETECT_LONG_EDGE_PX:
        scale = _MAX_DETECT_LONG_EDGE_PX / float(long_edge)
        detect_img = pil_roi.resize(
            (max(1, int(roi_w * scale)), max(1, int(roi_h * scale))),
            Image.Resampling.LANCZOS,
        )
    det_w, det_h = detect_img.size
    diag.detection_size = (det_w, det_h)
    diag.detection_scale = scale

    try:
        rgb = np.asarray(detect_img.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape[:2]
        _thr, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 60), max(3, h // 30)))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        diag.contour_count = len(contours)
        best: Box | None = None
        best_angle = 0.0
        best_area = 0.0
        best_meta: dict[str, Any] | None = None
        roi_area = float(w * h)
        min_area = roi_area * 0.05
        max_area = roi_area * 0.95
        min_score = roi_area * 0.08

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = float(bw * bh)
            aspect = bw / max(1, bh)
            score = area / roi_area if roi_area else 0.0
            passes_area = min_area <= area <= max_area
            passes_aspect = 1.3 <= aspect <= 7.0
            passes_score = area >= min_score
            entry: dict[str, Any] = {
                "x": int(x),
                "y": int(y),
                "width": int(bw),
                "height": int(bh),
                "area": int(area),
                "aspect": round(aspect, 3),
                "score": round(score, 4),
                "passes_area": passes_area,
                "passes_aspect": passes_aspect,
                "passes_score": passes_score,
                "selected": False,
            }
            diag.candidate_boxes.append(entry)
            if not passes_area:
                continue
            diag.area_candidate_count += 1
            if not passes_aspect:
                continue
            diag.aspect_candidate_count += 1
            if area > best_area:
                best_area = area
                best = (x, y, x + bw, y + bh)
                rect = cv2.minAreaRect(cnt)
                angle = float(rect[-1])
                if angle < -45:
                    angle += 90
                best_angle = max(-15.0, min(15.0, angle))
                best_meta = dict(entry)
                best_meta["selected"] = True

        if best is None:
            return diag

        inv = 1.0 / scale if scale else 1.0
        mapped = (
            int(best[0] * inv),
            int(best[1] * inv),
            int(best[2] * inv),
            int(best[3] * inv),
        )
        if mapped[2] <= mapped[0] or mapped[3] <= mapped[1]:
            diag.coordinate_mapping_invalid = True
            return diag
        if mapped[0] < 0 or mapped[1] < 0 or mapped[2] > roi_w or mapped[3] > roi_h:
            diag.coordinate_mapping_invalid = True
            return diag

        diag.box = mapped
        diag.deskew_angle = best_angle
        if best_meta is not None:
            diag.chosen_candidate = best_meta
            for entry in diag.candidate_boxes:
                entry["selected"] = (
                    entry["x"] == best_meta["x"]
                    and entry["y"] == best_meta["y"]
                    and entry["width"] == best_meta["width"]
                    and entry["height"] == best_meta["height"]
                )
        return diag
    except Exception as exc:  # noqa: BLE001
        logger.debug("p105.price_box_detect_fail err=%s", exc)
        diag.exception_message = str(exc)
        return diag


def _splits_from_base(base: Box, width: int, height: int) -> dict[str, Box]:
    bl, bt, br, bb = base
    bw = max(1, br - bl)
    bh = max(1, bb - bt)
    row_top = bt + int(bh * 0.16)
    row_bottom = bb - int(bh * 0.16)
    left_end = bl + int(bw * 0.32)
    bars_left = bl + int(bw * 0.16)
    bars_right = bl + int(bw * 0.74)
    right_start = bl + int(bw * 0.74)
    return {
        "main_bars": _clamp_box((bars_left, bt, bars_right, bb), width, height),
        "left_supplement": _clamp_box((bl, row_top, left_end, row_bottom), width, height),
        "right_cover_digit": _clamp_box((right_start, row_top, br, row_bottom), width, height),
    }


def compute_barcode_region_geometry(
    pil: Image.Image,
    *,
    config: BarcodeCropConfig = DEFAULT_BARCODE_CROP_CONFIG,
    min_region_px: int = MIN_LEFT_SUPPLEMENT_PX,
) -> BarcodeRegionGeometry:
    """Compute region boxes in ORIGINAL image coordinates, with size guards + diagnostics."""
    w, h = pil.size
    notes: list[str] = []
    input_too_small = max(w, h) < MIN_SANE_IMAGE_LONG_EDGE_PX
    if input_too_small:
        notes.append(
            f"input image is only {w}x{h}px (long edge < {MIN_SANE_IMAGE_LONG_EDGE_PX}); "
            "looks like a thumbnail, not a full-resolution capture"
        )
        logger.error(
            "p105.geometry_input_too_small original=%sx%s — supplement OCR cannot work on a thumbnail",
            w,
            h,
        )

    fe = _clamp_box(expand_box(0, int(h * 0.52), w, h, w, h, expand_ratio=config.clamped_expand_ratio()), w, h)

    price_box: Box | None = None
    deskew_angle = 0.0
    method = "percentage"
    fallback_reason = ""
    geometry_rejection_reason = ""
    rejected_detected_box = False
    roi = pil.crop(fe)
    det = _detect_price_box(roi)
    detected = det.box
    if detected is not None:
        dl, dt, dr, db = detected
        candidate_pb = _clamp_box((fe[0] + dl, fe[1] + dt, fe[0] + dr, fe[1] + db), w, h)
        candidate_splits = _splits_from_base(candidate_pb, w, h)
        ls = candidate_splits["left_supplement"]
        if _box_w(ls) >= min_region_px and _box_h(ls) >= min_region_px:
            price_box = candidate_pb
            deskew_angle = det.deskew_angle
            method = "geometry"
        else:
            rejected_detected_box = True
            notes.append(
                f"rejected detected price_box {_box_xywh(candidate_pb)}: "
                f"left_supplement {_box_w(ls)}x{_box_h(ls)} < {min_region_px}px; using percentage fallback"
            )
            logger.warning(
                "p105.geometry_rejected_tiny_box original=%sx%s box=%s left=%sx%s min=%s",
                w,
                h,
                _box_xywh(candidate_pb),
                _box_w(ls),
                _box_h(ls),
                min_region_px,
            )

    if method != "geometry":
        fallback_reason, geometry_rejection_reason = _resolve_percentage_fallback_reason(
            input_too_small=input_too_small,
            det=det,
            rejected_detected_box=rejected_detected_box,
        )
        logger.info(
            "p105.geometry_fallback original=%sx%s method=percentage fallback_reason=%s "
            "rejection=%s opencv=%s contours=%s candidates=%s",
            w,
            h,
            fallback_reason,
            geometry_rejection_reason,
            det.opencv_available,
            det.contour_count,
            len(det.candidate_boxes),
        )

    base = price_box if price_box is not None else fe
    splits = _splits_from_base(base, w, h)

    geometry = BarcodeRegionGeometry(
        full_expanded=fe,
        main_bars=splits["main_bars"],
        left_supplement=splits["left_supplement"],
        right_cover_digit=splits["right_cover_digit"],
        price_box=price_box,
        deskew_angle=deskew_angle,
        detection_method=method,
        original_size=(w, h),
        working_size=(w, h),
        detection_size=det.detection_size,
        detection_scale=det.detection_scale,
        min_region_px=min_region_px,
        notes=notes,
        geometry_attempted=True,
        opencv_available=det.opencv_available,
        fallback_reason=fallback_reason,
        geometry_rejection_reason=geometry_rejection_reason,
        exception_message=det.exception_message,
        contour_count=det.contour_count,
        candidate_boxes=list(det.candidate_boxes),
        chosen_candidate=det.chosen_candidate,
    )

    ls = geometry.left_supplement
    if _box_w(ls) < min_region_px or _box_h(ls) < min_region_px:
        geometry.geometry_failed = True
        geometry.notes.append(
            f"left_supplement crop {_box_w(ls)}x{_box_h(ls)} below minimum {min_region_px}px — "
            "geometry failed (input image is likely too small)"
        )
        logger.error(
            "p105.geometry_failed original=%sx%s left_supplement=%sx%s min=%s",
            w,
            h,
            _box_w(ls),
            _box_h(ls),
            min_region_px,
        )

    for line in geometry.report_lines():
        logger.info("p105.geometry %s", line)
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
