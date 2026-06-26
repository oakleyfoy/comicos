"""P105 geometry ROI debug visuals (labeled overlay, OCR word boxes).

Does not alter production OCR scoring — only runs an extra Tesseract TSV pass
on the geometry ``left_supplement`` crop for visualization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageDraw

from app.services.p105_comic_barcode_regions import (
    BarcodeRegionGeometry,
    Box,
    _OVERLAY_COLORS,
    _box_xywh,
    _clamp_box,
    pil_to_jpeg_bytes,
)
from app.services.p105_supplement_ocr import (
    TesseractWordBox,
    debug_tesseract_word_boxes,
    find_word_boxes_for_digits,
)

logger = logging.getLogger(__name__)

LEFT_SUPPLEMENT_CONTEXT_PAD_PX = 75


@dataclass
class GeometryOcrDebugVisuals:
    overlay_labeled: Image.Image
    context: Image.Image
    metadata: dict[str, Any] = field(default_factory=dict)


def _box_center(box: Box) -> tuple[int, int]:
    return (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))


def _union_box(boxes: list[Box]) -> Box | None:
    if not boxes:
        return None
    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = max(b[3] for b in boxes)
    return left, top, right, bottom


def _word_to_box(w: TesseractWordBox) -> Box:
    return w.left, w.top, w.left + w.width, w.top + w.height


def _offset_box(box: Box, dx: int, dy: int) -> Box:
    return box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy


def _point_in_box(x: int, y: int, box: Box) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _draw_crosshair(draw: ImageDraw.ImageDraw, cx: int, cy: int, *, color: tuple[int, int, int], size: int, width: int) -> None:
    draw.line((cx - size, cy, cx + size, cy), fill=color, width=width)
    draw.line((cx, cy - size, cx, cy + size), fill=color, width=width)
    r = max(2, width)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=width)


def draw_labeled_geometry_overlay(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
    *,
    ocr_hit_original: Box | None = None,
) -> Image.Image:
    """Full-frame overlay with region labels and a crosshair at the left-supplement OCR center."""
    overlay = pil.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    line_w = max(3, int(min(pil.size) * 0.005))

    entries: list[tuple[str, Box | None]] = [
        ("price_box", geometry.price_box),
        ("main_bars", geometry.main_bars),
        ("left_supplement", geometry.left_supplement),
        ("right_cover_digit", geometry.right_cover_digit),
    ]
    for label, box in entries:
        if box is None:
            continue
        color = _OVERLAY_COLORS.get(label, (255, 255, 255))
        draw.rectangle(box, outline=color, width=line_w)
        tx, ty = box[0] + 4, max(0, box[1] + 4)
        draw.rectangle((tx - 2, ty - 2, tx + 8 * len(label), ty + 14), fill=(0, 0, 0))
        draw.text((tx, ty), label, fill=color)

    ls = geometry.left_supplement
    cx, cy = _box_center(ls)
    _draw_crosshair(draw, cx, cy, color=(255, 0, 255), size=max(20, int(min(_box_xywh(ls)["width"], _box_xywh(ls)["height"]) * 0.4)), width=line_w)

    if ocr_hit_original is not None:
        draw.rectangle(ocr_hit_original, outline=(255, 0, 80), width=line_w + 1)
        hx, hy = ocr_hit_original[0], max(0, ocr_hit_original[1] - 16)
        draw.rectangle((hx - 2, hy - 2, hx + 120, hy + 14), fill=(0, 0, 0))
        draw.text((hx, hy), "ocr_digits_here", fill=(255, 0, 80))

    return overlay


def build_left_supplement_context_image(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
    *,
    word_boxes_original: list[TesseractWordBox],
    ocr_hit_original: Box | None,
    pad: int = LEFT_SUPPLEMENT_CONTEXT_PAD_PX,
) -> Image.Image:
    """Padded view around the left supplement ROI with Tesseract word rectangles."""
    w, h = pil.size
    ls = geometry.left_supplement
    context_box = _clamp_box(
        (ls[0] - pad, ls[1] - pad, ls[2] + pad, ls[3] + pad),
        w,
        h,
    )
    ctx = pil.crop(context_box).convert("RGB").copy()
    draw = ImageDraw.Draw(ctx)
    ox, oy = context_box[0], context_box[1]
    line_w = max(2, int(min(ctx.size) * 0.008))

    intended_local = (ls[0] - ox, ls[1] - oy, ls[2] - ox, ls[3] - oy)
    draw.rectangle(intended_local, outline=(0, 230, 90), width=line_w)
    draw.text((intended_local[0] + 2, intended_local[1] + 2), "intended left_supplement", fill=(0, 230, 90))

    icx = (intended_local[0] + intended_local[2]) // 2
    icy = (intended_local[1] + intended_local[3]) // 2
    _draw_crosshair(draw, icx, icy, color=(255, 0, 255), size=18, width=line_w)

    for word in word_boxes_original:
        wb = _offset_box(_word_to_box(word), -ox, -oy)
        draw.rectangle(wb, outline=(80, 160, 255), width=1)
        if word.text.strip():
            draw.text((wb[0], max(0, wb[1] - 10)), word.text[:12], fill=(80, 160, 255))

    if ocr_hit_original is not None:
        hit_local = _offset_box(ocr_hit_original, -ox, -oy)
        draw.rectangle(hit_local, outline=(255, 0, 80), width=line_w + 1)
        draw.text((hit_local[0], hit_local[3] + 2), "chosen OCR digits", fill=(255, 0, 80))

    return ctx


def build_geometry_ocr_debug_visuals(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
    left_supplement_crop: Image.Image,
    *,
    chosen_digits: str,
) -> GeometryOcrDebugVisuals:
    """Build labeled overlay + context crop and metadata for ocr_debug.json."""
    ls_origin = geometry.left_supplement
    ox, oy = ls_origin[0], ls_origin[1]

    tesseract_digits, tesseract_conf, words = debug_tesseract_word_boxes(left_supplement_crop, psm=7)
    words_original = [
        TesseractWordBox(
            text=w.text,
            left=w.left + ox,
            top=w.top + oy,
            width=w.width,
            height=w.height,
            confidence=w.confidence,
        )
        for w in words
    ]

    target = (chosen_digits or "").strip()
    hit_words = find_word_boxes_for_digits(words, target) if target else []
    if not hit_words and target and tesseract_digits:
        hit_words = find_word_boxes_for_digits(words, tesseract_digits)

    hit_crop_boxes = [_word_to_box(w) for w in hit_words]
    hit_union_crop = _union_box(hit_crop_boxes)
    ocr_hit_original: Box | None = None
    if hit_union_crop is not None:
        ocr_hit_original = _offset_box(hit_union_crop, ox, oy)

    intended = geometry.left_supplement
    ocr_outside = False
    compare_note = ""
    if ocr_hit_original is not None:
        hcx, hcy = _box_center(ocr_hit_original)
        ocr_outside = not _point_in_box(hcx, hcy, intended)
        compare_note = (
            "OCR digit center lies outside intended left_supplement ROI."
            if ocr_outside
            else "OCR digit center lies inside intended left_supplement ROI."
        )
    elif target:
        compare_note = (
            f"Could not locate '{target}' in Tesseract word boxes on the geometry left_supplement crop "
            f"(debug pass read '{tesseract_digits}'). Digits may come from a preprocessed OCR variant."
        )
        ocr_outside = True

    overlay_labeled = draw_labeled_geometry_overlay(pil, geometry, ocr_hit_original=ocr_hit_original)
    context = build_left_supplement_context_image(
        pil,
        geometry,
        word_boxes_original=words_original,
        ocr_hit_original=ocr_hit_original,
    )

    metadata: dict[str, Any] = {
        "chosen_ocr_digits": target,
        "debug_tesseract_on": "geometry.left_supplement crop (original, psm=7)",
        "debug_tesseract_digits": tesseract_digits,
        "debug_tesseract_confidence": round(tesseract_conf, 3),
        "intended_left_supplement": _box_xywh(intended),
        "ocr_hit_box_original": _box_xywh(ocr_hit_original) if ocr_hit_original else None,
        "ocr_hit_center_original": {"x": _box_center(ocr_hit_original)[0], "y": _box_center(ocr_hit_original)[1]}
        if ocr_hit_original
        else None,
        "ocr_outside_intended_left_supplement": ocr_outside,
        "intended_vs_detected_note": compare_note,
        "tesseract_word_boxes_original": [
            {
                "text": w.text,
                "x": w.left,
                "y": w.top,
                "width": w.width,
                "height": w.height,
                "confidence": round(w.confidence, 3),
            }
            for w in words_original
        ],
        "tesseract_word_boxes_crop_local": [
            {
                "text": w.text,
                "x": w.left,
                "y": w.top,
                "width": w.width,
                "height": w.height,
                "confidence": round(w.confidence, 3),
            }
            for w in words
        ],
        "context_padding_px": LEFT_SUPPLEMENT_CONTEXT_PAD_PX,
        "artifacts": {
            "overlay_labeled": "overlay_labeled.jpg",
            "left_supplement_context": "left_supplement_context.jpg",
        },
    }
    logger.info(
        "p105.geometry_viz chosen=%s debug_tesseract=%s outside_intended=%s words=%d",
        target or "(none)",
        tesseract_digits or "(none)",
        ocr_outside,
        len(words),
    )
    return GeometryOcrDebugVisuals(overlay_labeled=overlay_labeled, context=context, metadata=metadata)


def write_geometry_debug_images(base_dir: Any, visuals: GeometryOcrDebugVisuals) -> None:
    """Write labeled overlay + context JPEGs into an existing debug directory."""
    from pathlib import Path

    root = Path(base_dir)
    (root / "overlay_labeled.jpg").write_bytes(pil_to_jpeg_bytes(visuals.overlay_labeled))
    (root / "left_supplement_context.jpg").write_bytes(pil_to_jpeg_bytes(visuals.context))
