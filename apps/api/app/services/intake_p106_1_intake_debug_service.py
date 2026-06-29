"""Debug artifacts + structured logs for P106.1 / fingerprint review on intake scans."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.services.photo_import_storage_service import REPO_ROOT

logger = logging.getLogger(__name__)

P106_1_INTAKE_DEBUG_ROOT = REPO_ROOT / "data" / "debug" / "p106_1"


def p106_1_intake_debug_dir(*, intake_item_id: int) -> Path:
    return P106_1_INTAKE_DEBUG_ROOT / f"item_{int(intake_item_id)}"


def save_p106_1_intake_debug_bundle(
    *,
    intake_item_id: int,
    primary_path: Path,
    primary_bytes: bytes,
    recognition_path: Path,
    recognition_bytes: bytes,
    fingerprint_path: Path,
    barcode_crop_bytes: bytes | None,
    region_debug: dict[str, Any],
) -> Path:
    """Write input / recognition / fingerprint / barcode_crop images and region_debug.json."""
    dest = p106_1_intake_debug_dir(intake_item_id=intake_item_id)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "input.jpg").write_bytes(primary_bytes)
    (dest / "recognition_image.jpg").write_bytes(recognition_bytes)
    if fingerprint_path.is_file() and fingerprint_path.resolve() != recognition_path.resolve():
        shutil.copyfile(fingerprint_path, dest / "fingerprint_image.jpg")
    else:
        (dest / "fingerprint_image.jpg").write_bytes(recognition_bytes)
    if barcode_crop_bytes:
        (dest / "barcode_crop.jpg").write_bytes(barcode_crop_bytes)
    elif primary_path.is_file():
        shutil.copyfile(primary_path, dest / "barcode_crop.jpg")
    (dest / "region_debug.json").write_text(json.dumps(region_debug, indent=2, default=str), encoding="utf-8")
    return dest


def log_intake_fingerprint_review_instrumentation(payload: dict[str, Any]) -> None:
    logger.info("intake.fingerprint_review.pre_persist %s", json.dumps(payload, default=str))
