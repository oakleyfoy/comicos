"""P106.1 barcode_gap observability and OCR health tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.p106_barcode_gap_resolver_service import barcode_gap_payload_from_diagnosis
from app.services.p106_1_gcd_non_barcode_recovery_service import P106_1_RECOVERY_STAGE
from app.services.recognition.ocr_matcher import OCR_UNAVAILABLE_MESSAGE, extract_ocr_signal
from app.services.scanner_barcode_field_test_service import (
    ScannerBarcodeResolutionTrace,
    build_scanner_barcode_event,
)
from app.models.intake_queue import IntakeSessionItem
from test_ops_admin import auth_headers, register_and_login


def test_barcode_gap_payload_includes_bounded_p106_1_diagnostics() -> None:
    long_ocr = "X" * 800
    candidates = [{"gcd_issue_id": i, "score": i} for i in range(15)]
    diagnosis = {
        "recovery_stage": P106_1_RECOVERY_STAGE,
        "recovery_reason": "insufficient_series_or_title_hint",
        "recovery_block_reason": "insufficient_series_or_title_hint",
        "recovery_hints": {
            "ocr_title": "Amazing Spider-Man",
            "raw_ocr_text_excerpt": long_ocr,
            "series_hint_reliable": False,
            "ocr_engine_available": False,
            "ocr_error": OCR_UNAVAILABLE_MESSAGE,
        },
        "p106_1_instrumentation": {
            "decision_reason": "insufficient_series_or_title_hint",
            "gcd_candidates": candidates,
            "ocr_engine_available": False,
            "ocr_error": OCR_UNAVAILABLE_MESSAGE,
        },
        "p106_1_skipped": False,
        "fingerprint_candidate_count": 3,
        "ocr_confidence": 0.42,
        "facsimile_or_reprint": True,
    }
    gap = barcode_gap_payload_from_diagnosis(diagnosis)
    assert gap["recovery_stage"] == P106_1_RECOVERY_STAGE
    assert gap["recovery_block_reason"] == "insufficient_series_or_title_hint"
    assert gap["p106_1_skipped"] is False
    assert gap["fingerprint_candidate_count"] == 3
    assert gap["facsimile_or_reprint"] is True
    assert gap["ocr_confidence"] == 0.42
    assert gap["raw_ocr_text_excerpt"] is not None
    assert len(gap["raw_ocr_text_excerpt"]) == 500
    assert len(gap["p106_1_instrumentation"]["gcd_candidates"]) == 10
    assert gap["recovery_hints"]["ocr_engine_available"] is False


def test_raw_ocr_excerpt_truncates_in_recovery_hints() -> None:
    diagnosis = {
        "recovery_hints": {"raw_ocr_text_excerpt": "A" * 600},
    }
    gap = barcode_gap_payload_from_diagnosis(diagnosis)
    assert len(gap["recovery_hints"]["raw_ocr_text_excerpt"]) == 500


def test_ocr_health_unavailable_when_binary_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ocr-health@example.com")
    token = register_and_login(client, "ocr-health@example.com")
    with patch("app.services.ocr_health_service.get_tesseract_engine_version", return_value=None):
        resp = client.get("/api/ops/ocr-health", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tesseract_available"] is False
    assert body["version"] is None
    assert body["error"] == OCR_UNAVAILABLE_MESSAGE


def test_ocr_health_available_when_mocked(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ocr-health-ok@example.com")
    token = register_and_login(client, "ocr-health-ok@example.com")
    with patch("app.services.ocr_health_service.get_tesseract_engine_version", return_value="tesseract 5.3.0"):
        with patch("app.services.ocr_health_service._resolve_ocr_engine_cmd", return_value="/usr/bin/tesseract"):
            resp = client.get("/api/ops/ocr-health", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tesseract_available"] is True
    assert body["tesseract_cmd"] == "/usr/bin/tesseract"
    assert body["version"] == "tesseract 5.3.0"
    assert body["error"] is None


def test_extract_ocr_signal_marks_engine_unavailable_on_tesseract_oserror() -> None:
    with patch(
        "app.services.recognition.ocr_matcher._run_tesseract_ocr_with_test_compat",
        side_effect=OSError("tesseract not found"),
    ):
        signal = extract_ocr_signal(b"fake", source_name="test")
    assert signal.ocr_engine_available is False
    assert signal.ocr_error == OCR_UNAVAILABLE_MESSAGE


def test_scanner_review_payload_exposes_recovery_block_reason() -> None:
    diagnosis = {
        "status": "review_required",
        "gcd_match_count": 0,
        "recovery_block_reason": "insufficient_series_or_title_hint",
        "recovery_stage": P106_1_RECOVERY_STAGE,
        "recovery_hints": {"series_hint_reliable": False},
        "p106_1_instrumentation": {"decision_reason": "insufficient_series_or_title_hint"},
    }
    trace = ScannerBarcodeResolutionTrace(intake_item_id=1)
    trace.apply_p106_diagnosis(diagnosis, gcd_path=None)
    item = IntakeSessionItem(id=1, session_id=1, user_id=1, storage_path="x.jpg", status="needs_review")
    event = build_scanner_barcode_event(
        trace=trace,
        item=item,
        final_status="needs_review",
        final_reason="review",
    )
    assert event["recovery_block_reason"] == "insufficient_series_or_title_hint"
