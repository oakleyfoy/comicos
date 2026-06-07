"""P89-03 safe condition notes from inventory signals."""

from __future__ import annotations


def grade_display_label(grade_status: str) -> str:
    g = (grade_status or "raw").strip().lower()
    if g in {"raw", "ungraded", ""}:
        return "Raw"
    if g.startswith("cgc") or g.startswith("cbcs") or "graded" in g:
        return grade_status.upper().replace("_", " ")
    return grade_status


def is_slabs(grade_status: str) -> bool:
    g = (grade_status or "").lower()
    return g.startswith("cgc") or g.startswith("cbcs") or "slab" in g


def generate_condition_notes(
    *,
    grade_status: str,
    estimated_grade: str | None,
    inventory_condition_notes: str | None,
) -> str:
    if is_slabs(grade_status):
        base = "CGC/CBCS graded copy. See certification details in photos if available."
    elif (grade_status or "raw").lower() in {"raw", "ungraded", ""}:
        if estimated_grade:
            base = f"Raw book. Estimated grade: {estimated_grade} (collector estimate; not a professional grade)."
        else:
            base = "Raw book. Estimated grade not assigned."
    else:
        base = f"Condition: {grade_display_label(grade_status)}."
    inv = (inventory_condition_notes or "").strip()
    if inv:
        return f"{base} Condition notes available from inventory record: {inv}"
    return base
