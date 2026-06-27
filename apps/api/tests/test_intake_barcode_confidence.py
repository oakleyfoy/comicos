"""Tests for intake barcode confidence helpers."""

from __future__ import annotations

from app.services.intake_barcode_confidence import (
    has_full_direct_market_barcode,
    ocr_barcode_info_note,
)

FULL = "76194134192703921"


def test_has_full_direct_market_barcode() -> None:
    assert has_full_direct_market_barcode(FULL) is True
    assert has_full_direct_market_barcode("761941341927") is False


def test_ocr_info_note_when_issues_differ() -> None:
    note = ocr_barcode_info_note(
        normalized_barcode=FULL,
        ocr_supplement="01911",
        matched_series="Superman",
        matched_issue_number="39",
    )
    assert note is not None
    assert "OCR read issue #19" in note
    assert "Superman" in note
    assert "#39" in note


def test_ocr_info_note_absent_when_agrees() -> None:
    assert (
        ocr_barcode_info_note(
            normalized_barcode=FULL,
            ocr_supplement="03921",
            matched_series="Superman",
            matched_issue_number="39",
        )
        is None
    )
