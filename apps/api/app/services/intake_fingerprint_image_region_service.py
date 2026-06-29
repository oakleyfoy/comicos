"""Classify intake scan crops so UPC/barcode strips do not drive cover fingerprint review."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGION_BARCODE_STRIP = "barcode_strip"
REGION_UPC_DOMINATED = "upc_region"
REGION_FULL_COVER = "full_cover"
REGION_UNKNOWN = "unknown"

SUPPRESSED_BARCODE_REGION = "barcode_region_crop"
SUPPRESSED_UPC_DOMINATED = "upc_dominated_crop"


@dataclass(frozen=True)
class FingerprintRegionAssessment:
    fingerprint_image_region: str
    fingerprint_region_safe: bool
    fingerprint_suppressed_reason: str | None
    width: int = 0
    height: int = 0


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


def assess_fingerprint_image_region(
    image_path: Path | None,
    *,
    image_bytes: bytes | None = None,
    force_full_cover: bool = False,
) -> FingerprintRegionAssessment:
    """Heuristic: wide, short crops are UPC/barcode strips — unsafe for cover fingerprint review."""
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
    if w <= 0 or h <= 0:
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_UNKNOWN,
            fingerprint_region_safe=True,
            fingerprint_suppressed_reason=None,
            width=w,
            height=h,
        )

    ratio = w / h
    if ratio >= 2.2 or (h < 350 and ratio >= 1.4):
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_BARCODE_STRIP,
            fingerprint_region_safe=False,
            fingerprint_suppressed_reason=SUPPRESSED_BARCODE_REGION,
            width=w,
            height=h,
        )
    if h < 280 and ratio >= 1.15:
        return FingerprintRegionAssessment(
            fingerprint_image_region=REGION_UPC_DOMINATED,
            fingerprint_region_safe=False,
            fingerprint_suppressed_reason=SUPPRESSED_UPC_DOMINATED,
            width=w,
            height=h,
        )
    if h >= 400 and 0.45 <= ratio <= 1.65:
        region = REGION_FULL_COVER
    else:
        region = REGION_UNKNOWN
    return FingerprintRegionAssessment(
        fingerprint_image_region=region,
        fingerprint_region_safe=True,
        fingerprint_suppressed_reason=None,
        width=w,
        height=h,
    )


def merge_fingerprint_region_instrumentation(
    target: dict[str, Any],
    assessment: FingerprintRegionAssessment,
) -> None:
    target["fingerprint_image_region"] = assessment.fingerprint_image_region
    target["fingerprint_region_safe"] = assessment.fingerprint_region_safe
    if assessment.fingerprint_suppressed_reason:
        target["fingerprint_suppressed_reason"] = assessment.fingerprint_suppressed_reason
    elif "fingerprint_suppressed_reason" in target and assessment.fingerprint_region_safe:
        target.pop("fingerprint_suppressed_reason", None)
