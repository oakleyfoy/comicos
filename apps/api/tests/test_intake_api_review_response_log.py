"""Tests for intake API review response logging (UI source mirror)."""

from __future__ import annotations

from app.services.intake_api_review_response_log_service import (
    _gap_diagnosis_view,
    _ui_fingerprint_candidate_source,
)


def test_ui_source_prefers_barcode_gap_tops() -> None:
    barcode_read = {
        "barcode_gap": {
            "needs_review_top_candidates": [
                {"series": "A", "source": "fingerprint"},
                {"series": "B", "source": "fingerprint"},
            ],
        }
    }
    assert (
        _ui_fingerprint_candidate_source(
            item_status="needs_review",
            barcode_read=barcode_read,
            db_candidate_count=3,
            db_fingerprint_candidate_count=3,
        )
        == "barcode_gap.needs_review_top_candidates"
    )


def test_ui_source_falls_back_to_db_candidates() -> None:
    assert (
        _ui_fingerprint_candidate_source(
            item_status="needs_review",
            barcode_read={"barcode_gap": {}},
            db_candidate_count=2,
            db_fingerprint_candidate_count=2,
        )
        == "IntakeItemCandidate_rows"
    )


def test_ui_source_suppressed_for_full_cover() -> None:
    assert (
        _ui_fingerprint_candidate_source(
            item_status="needs_full_cover_photo",
            barcode_read={
                "barcode_gap": {
                    "needs_review_top_candidates": [{"series": "Stale"}],
                }
            },
            db_candidate_count=3,
            db_fingerprint_candidate_count=3,
        )
        == "none_suppressed_needs_full_cover_photo"
    )


def test_gap_diagnosis_view_from_barcode_read() -> None:
    view = _gap_diagnosis_view(
        {
            "needs_full_cover_photo": True,
            "fingerprint_region_safe": False,
            "fingerprint_image_region": "barcode_strip",
            "barcode_gap": {
                "review_decision": "fingerprint_review",
                "needs_review_top_candidates": [{"series": "X"}],
            },
        }
    )
    assert view["full_cover_followup_required"] is True
    assert view["needs_review_top_candidates_count"] == 1
    assert view["review_decision"] == "fingerprint_review"
