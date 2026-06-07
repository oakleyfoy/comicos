from __future__ import annotations

from app.services.condition_note_service import generate_condition_notes


def test_raw_without_grade() -> None:
    note = generate_condition_notes(grade_status="raw", estimated_grade=None, inventory_condition_notes=None)
    assert "Raw book" in note
    assert "not assigned" in note


def test_slab_note() -> None:
    note = generate_condition_notes(grade_status="cgc_9.8", estimated_grade=None, inventory_condition_notes=None)
    assert "graded" in note.lower()
