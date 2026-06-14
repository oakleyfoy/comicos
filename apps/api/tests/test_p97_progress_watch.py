from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from p97_progress_watch import (  # noqa: E402
    compute_bottleneck,
    compute_status,
    derive_progress,
    json_export,
    pct_of,
)


def test_pct_of_divide_by_zero() -> None:
    assert pct_of(5, 0) == 0.0
    assert pct_of(0, 0) == 0.0


def test_derive_progress_percent_math() -> None:
    report = derive_progress(
        total_issues=21804,
        total_images=21804,
        ready_covers=6356,
        pending_covers=15443,
        failed_covers=5,
        fingerprints=6356,
        ocr_rows=2556,
    )
    assert report["cover_ready_pct"] == pytest.approx(round(6356 / 21804 * 100, 1), abs=0.05)
    assert report["pending_cover_pct"] == pytest.approx(round(15443 / 21804 * 100, 1), abs=0.05)
    assert report["fingerprint_ready_pct"] == 100.0
    assert report["ocr_ready_pct"] == pytest.approx(round(2556 / 6356 * 100, 1), abs=0.05)
    assert report["visual_match_ready_pct"] == pytest.approx(round(6356 / 21804 * 100, 1), abs=0.05)
    assert report["ocr_catalog_pct"] == pytest.approx(round(2556 / 21804 * 100, 1), abs=0.05)


def test_bottleneck_cover_download_when_pending() -> None:
    assert (
        compute_bottleneck(
            pending_covers=10,
            ready_covers=100,
            fingerprints=100,
            ocr_rows=100,
        )
        == "COVER_DOWNLOAD"
    )


def test_bottleneck_fingerprint_generation() -> None:
    assert (
        compute_bottleneck(
            pending_covers=0,
            ready_covers=100,
            fingerprints=50,
            ocr_rows=0,
        )
        == "FINGERPRINT_GENERATION"
    )


def test_bottleneck_ocr_generation() -> None:
    assert (
        compute_bottleneck(
            pending_covers=0,
            ready_covers=100,
            fingerprints=100,
            ocr_rows=80,
        )
        == "OCR_GENERATION"
    )


def test_bottleneck_none_when_caught_up() -> None:
    assert (
        compute_bottleneck(
            pending_covers=0,
            ready_covers=100,
            fingerprints=100,
            ocr_rows=90,
        )
        == "NONE"
    )


def test_status_enrichment_backlog() -> None:
    assert compute_status(visual_match_ready_pct=29.1) == "ENRICHMENT_BACKLOG"


def test_status_partial_scan_ready() -> None:
    assert compute_status(visual_match_ready_pct=50.0) == "PARTIAL_SCAN_READY"
    assert compute_status(visual_match_ready_pct=89.9) == "PARTIAL_SCAN_READY"


def test_status_scanner_ready_for_validation() -> None:
    assert compute_status(visual_match_ready_pct=90.0) == "SCANNER_READY_FOR_VALIDATION"


def test_json_export_valid_json() -> None:
    report = derive_progress(
        total_issues=21804,
        total_images=21804,
        ready_covers=6356,
        pending_covers=15443,
        failed_covers=5,
        fingerprints=6356,
        ocr_rows=2556,
    )
    payload = json_export(report)
    text = json.dumps(payload)
    parsed = json.loads(text)
    assert parsed["bottleneck"] == "COVER_DOWNLOAD"
    assert parsed["status"] == "ENRICHMENT_BACKLOG"
    assert parsed["total_issues"] == 21804
