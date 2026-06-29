"""Classify intake scan crops so UPC/barcode strips do not drive cover fingerprint review."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.p105_comic_barcode_regions import (
    BarcodeRegionGeometry,
    compute_barcode_region_geometry,
    crops_from_geometry,
    is_likely_barcode_strip,
)

REGION_BARCODE_STRIP = "barcode_strip"
REGION_UPC_DOMINATED = "upc_region"
REGION_FULL_COVER = "full_cover"
REGION_UNKNOWN = "unknown"

SUPPRESSED_BARCODE_REGION = "barcode_region_crop"
SUPPRESSED_UPC_DOMINATED = "upc_dominated_crop"
SUPPRESSED_BARCODE_DOMINATED_FRAME = "barcode_dominated_frame"


@dataclass(frozen=True)
class FingerprintRegionAssessment:
    fingerprint_image_region: str
    fingerprint_region_safe: bool
    fingerprint_suppressed_reason: str | None
    width: int = 0
    height: int = 0
    barcode_crop_width: int = 0
    barcode_crop_height: int = 0
    barcode_region_overlap_percent: float = 0.0
    main_bars_overlap_percent: float = 0.0
    p105_barcode_strip_layout: bool = False


def _image_size(image_path: Path | None, image_bytes: bytes | None) -> tuple[int, int]:
    if image_bytes:
        try:
            from PIL import Image

            with Image.open(io.BytesIO(image_bytes)) as img:
                w, h = img.size
                return int(w), int(h)
        except Exception:
            pass
    if image_path is not None and image_path.is_file():
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                w, h = img.size
                return int(w), int(h)
        except Exception:
            pass
    return 0, 0


def _box_area(box: tuple[int, int, int, int]) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def _overlap_percent(box: tuple[int, int, int, int], *, width: int, height: int) -> float:
    total = max(1, width * height)
    return round(_box_area(box) / total * 100.0, 2)


def assess_fingerprint_image_region(
    image_path: Path | None,
    *,
    image_bytes: bytes | None = None,
    geometry: BarcodeRegionGeometry | None = None,
    force_full_cover: bool = False,
) -> FingerprintRegionAssessment:
    """Heuristic + P105 geometry: barcode/price-box dominated frames are unsafe for cover fingerprint."""
    if force_full_cover:
        w, h = _image_size(image_path, image_bytes)
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_FULL_COVER,
            fingerprint_region_safe=True,
            fingerprint_suppressed_reason=None,
            width=w,
            height=h,
        )

    w, h = _image_size(image_path, image_bytes)
    if geometry is None and image_bytes:
        try:
            from PIL import Image

            with Image.open(io.BytesIO(image_bytes)) as img:
                geometry = compute_barcode_region_geometry(img.convert("RGB"))
        except Exception:
            geometry = None

    crop_w = crop_h = 0
    fe_overlap = mb_overlap = 0.0
    strip_layout = is_likely_barcode_strip(w, h) if w > 0 and h > 0 else False
    if geometry is not None and w > 0 and h > 0:
        fe = geometry.full_expanded
        crop_w = max(0, fe[2] - fe[0])
        crop_h = max(0, fe[3] - fe[1])
        fe_overlap = _overlap_percent(fe, width=w, height=h)
        mb_overlap = _overlap_percent(geometry.main_bars, width=w, height=h)
        if strip_layout or fe_overlap >= 92.0:
            strip_layout = True

    if w <= 0 or h <= 0:
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_UNKNOWN,
            fingerprint_region_safe=True,
            fingerprint_suppressed_reason=None,
            width=w,
            height=h,
            barcode_crop_width=crop_w,
            barcode_crop_height=crop_h,
            barcode_region_overlap_percent=fe_overlap,
            main_bars_overlap_percent=mb_overlap,
            p105_barcode_strip_layout=strip_layout,
        )

    ratio = w / h
    dominated_frame = strip_layout or (
        fe_overlap >= 88.0 and mb_overlap >= 22.0 and max(w, h) < 1400
    )
    if dominated_frame or ratio >= 2.0 or (h < 350 and ratio >= 1.4):
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_BARCODE_STRIP,
            fingerprint_region_safe=False,
            fingerprint_suppressed_reason=SUPPRESSED_BARCODE_REGION
            if strip_layout or ratio >= 2.0
            else SUPPRESSED_BARCODE_DOMINATED_FRAME,
            width=w,
            height=h,
            barcode_crop_width=crop_w,
            barcode_crop_height=crop_h,
            barcode_region_overlap_percent=fe_overlap,
            main_bars_overlap_percent=mb_overlap,
            p105_barcode_strip_layout=strip_layout,
        )
    if h < 280 and ratio >= 1.15:
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_UPC_DOMINATED,
            fingerprint_region_safe=False,
            fingerprint_suppressed_reason=SUPPRESSED_UPC_DOMINATED,
            width=w,
            height=h,
            barcode_crop_width=crop_w,
            barcode_crop_height=crop_h,
            barcode_region_overlap_percent=fe_overlap,
            main_bars_overlap_percent=mb_overlap,
            p105_barcode_strip_layout=strip_layout,
        )
    if h >= 400 and 0.45 <= ratio <= 1.65 and fe_overlap < 55.0:
        region = REGION_FULL_COVER
    else:
        region = REGION_UNKNOWN
    return FingerprintRegionAssessment(
        fingerprint_image_region=region,
        fingerprint_region_safe=True,
        fingerprint_suppressed_reason=None,
        width=w,
        height=h,
        barcode_crop_width=crop_w,
        barcode_crop_height=crop_h,
        barcode_region_overlap_percent=fe_overlap,
        main_bars_overlap_percent=mb_overlap,
        p105_barcode_strip_layout=strip_layout,
    )


def merge_fingerprint_region_instrumentation(
    target: dict[str, Any],
    assessment: FingerprintRegionAssessment,
) -> None:
    target["fingerprint_image_region"] = assessment.fingerprint_image_region
    target["fingerprint_region_safe"] = assessment.fingerprint_region_safe
    target["recognition_image_width"] = assessment.width
    target["recognition_image_height"] = assessment.height
    target["barcode_crop_width"] = assessment.barcode_crop_width
    target["barcode_crop_height"] = assessment.barcode_crop_height
    target["barcode_region_overlap_percent"] = assessment.barcode_region_overlap_percent
    target["main_bars_overlap_percent"] = assessment.main_bars_overlap_percent
    target["p105_barcode_strip_layout"] = assessment.p105_barcode_strip_layout
    if assessment.fingerprint_suppressed_reason:
        target["fingerprint_suppressed_reason"] = assessment.fingerprint_suppressed_reason
    elif "fingerprint_suppressed_reason" in target and assessment.fingerprint_region_safe:
        target.pop("fingerprint_suppressed_reason", None)


def barcode_crop_jpeg_bytes(image_bytes: bytes, geometry: BarcodeRegionGeometry | None) -> bytes | None:
    if not image_bytes:
        return None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            pil = img.convert("RGB")
            geo = geometry or compute_barcode_region_geometry(pil)
            regions = crops_from_geometry(pil, geo)
            buf = io.BytesIO()
            regions["full_expanded"].save(buf, format="JPEG", quality=90)
            return buf.getvalue()
    except Exception:
        return None
