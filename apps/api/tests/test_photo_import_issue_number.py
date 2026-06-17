"""P100-13A photo issue number sanitizer tests."""

from __future__ import annotations

from app.services.photo_import_issue_number import apply_photo_issue_sanitization, normalize_photo_issue_number


def test_accepts_numeric_issue_formats() -> None:
    assert normalize_photo_issue_number("4") == "4"
    assert normalize_photo_issue_number("#4") == "4"
    assert normalize_photo_issue_number("No. 4") == "4"
    assert normalize_photo_issue_number("104") == "104"
    assert normalize_photo_issue_number("1/2") == "1/2"
    assert normalize_photo_issue_number("0") == "0"
    assert normalize_photo_issue_number("25.NOW") == "25.NOW"


def test_rejects_subtitles_and_phrases() -> None:
    assert normalize_photo_issue_number("THE INITIATIVE") is None
    assert normalize_photo_issue_number("INTRODUCING THE SPIRITS") is None
    assert normalize_photo_issue_number("No issue number visible") is None
    assert normalize_photo_issue_number("Special collector edition") is None
    assert normalize_photo_issue_number("?") is None


def test_sanitization_moves_rejected_issue_to_subtitle() -> None:
    book = apply_photo_issue_sanitization(
        {
            "issue_number_guess": "THE INITIATIVE",
            "subtitle_guess": "",
            "visible_issue_text": "",
            "uncertainty_reason": "",
        }
    )
    assert book["issue_number_guess"] is None
    assert "INITIATIVE" in str(book["subtitle_guess"]).upper()
    assert "Issue number not visible" in str(book["uncertainty_reason"])
