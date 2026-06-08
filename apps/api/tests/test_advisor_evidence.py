"""Tests for advisor evidence formatting (P90-06)."""

from app.services.advisor_evidence import (
    dedupe_evidence_string,
    format_evidence_for_display,
    split_evidence_segments,
)


def test_dedupe_evidence_removes_repeated_segments() -> None:
    raw = "55% below FMV · verified listing · 55% below FMV · verified listing · 26% below FMV"
    assert dedupe_evidence_string(raw) == "55% below FMV · verified listing · 26% below FMV"


def test_format_evidence_limits_visible_supporting() -> None:
    raw = " · ".join([f"signal {i}" for i in range(6)])
    primary, supporting, hidden = format_evidence_for_display(raw, max_visible=3)
    assert primary == "signal 0"
    assert supporting == ["signal 1", "signal 2"]
    assert hidden == 3


def test_split_evidence_handles_mixed_separators() -> None:
    parts = split_evidence_segments("A · B, C; D")
    assert parts == ["A", "B", "C", "D"]
