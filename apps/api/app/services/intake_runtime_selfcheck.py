"""Runtime self-check for intake-critical native dependencies.

Reports the facts that determine whether the barcode -> OCR -> fingerprint
pipeline can run on a given host: Python, Tesseract (OCR), OpenCV, and ZXing.
Used by the API startup log and by scripts/ocr_runtime_selfcheck.py so the
same report is available in Render service logs and in an interactive shell.
"""

from __future__ import annotations

import platform
from typing import Any


def collect_intake_runtime_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "python_version": platform.python_version(),
        "tesseract_cmd_configured": "",
        "tesseract_cmd_resolved": "",
        "tesseract_available": False,
        "tesseract_version": None,
        "opencv_available": False,
        "opencv_version": None,
        "zxing_available": False,
    }

    try:
        from app.core.config import get_settings

        report["tesseract_cmd_configured"] = (get_settings().tesseract_cmd or "").strip()
    except Exception:  # noqa: BLE001 - never block the report on settings
        report["tesseract_cmd_configured"] = ""

    try:
        from app.services.cover_images import (
            _resolve_ocr_engine_cmd,
            get_tesseract_engine_version,
        )

        report["tesseract_cmd_resolved"] = _resolve_ocr_engine_cmd()
        version = get_tesseract_engine_version()
        report["tesseract_version"] = version
        report["tesseract_available"] = version is not None
    except Exception:  # noqa: BLE001
        report["tesseract_available"] = False

    try:
        import cv2  # type: ignore

        report["opencv_available"] = True
        report["opencv_version"] = getattr(cv2, "__version__", None)
    except Exception:  # noqa: BLE001 - opencv import can fail on missing system libs
        report["opencv_available"] = False

    try:
        from app.services.p105_upc_addon_decoder import _zxing_available

        report["zxing_available"] = bool(_zxing_available())
    except Exception:  # noqa: BLE001
        report["zxing_available"] = False

    return report


def format_intake_runtime_line(report: dict[str, Any]) -> str:
    return (
        "intake.runtime.startup "
        f"python={report['python_version']} "
        f"tesseract_available={report['tesseract_available']} "
        f"tesseract_version={report['tesseract_version']!r} "
        f"TESSERACT_CMD={report['tesseract_cmd_configured']!r} "
        f"resolved={report['tesseract_cmd_resolved']!r} "
        f"opencv_available={report['opencv_available']} "
        f"opencv_version={report['opencv_version']!r} "
        f"zxing_available={report['zxing_available']}"
    )
