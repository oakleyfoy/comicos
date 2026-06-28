"""Print intake runtime dependency status and exit non-zero if OCR is missing.

Usage (Render shell, or `docker run --rm <image> python scripts/ocr_runtime_selfcheck.py`):

    python scripts/ocr_runtime_selfcheck.py

Reports Python, Tesseract (OCR), OpenCV, ZXing, and the resolved TESSERACT_CMD.
Exit code 0 only when Tesseract, OpenCV, and ZXing are all available.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(API_ROOT))

    from app.services.intake_runtime_selfcheck import (
        collect_intake_runtime_report,
        format_intake_runtime_line,
    )

    report = collect_intake_runtime_report()
    print(format_intake_runtime_line(report), flush=True)
    print(json.dumps(report, indent=2, default=str), flush=True)

    ok = (
        report["tesseract_available"]
        and report["opencv_available"]
        and report["zxing_available"]
    )
    if not ok:
        print(
            "SELFCHECK FAILED: one or more intake dependencies are unavailable "
            "(tesseract/opencv/zxing).",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print("SELFCHECK OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
