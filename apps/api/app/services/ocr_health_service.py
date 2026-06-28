"""Tesseract availability probe for ops / Render health checks."""

from __future__ import annotations

from typing import Any

from app.services.cover_images import _resolve_ocr_engine_cmd, get_tesseract_engine_version


def probe_tesseract_health() -> dict[str, Any]:
    resolved_cmd = _resolve_ocr_engine_cmd()
    version = get_tesseract_engine_version()
    available = version is not None
    error: str | None = None
    if not available:
        error = "Local Tesseract OCR engine is unavailable on this host."
    return {
        "tesseract_available": available,
        "tesseract_cmd": resolved_cmd,
        "version": version,
        "error": error,
    }
