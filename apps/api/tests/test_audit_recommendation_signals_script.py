"""Smoke test for audit_recommendation_signals script."""

from __future__ import annotations

from pathlib import Path


def test_audit_script_exists_and_has_cli() -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_recommendation_signals.py"
    source = path.read_text(encoding="utf-8")
    assert "creator_score_gt_0" in source
    assert "top_25_by_milestone_score" in source
    assert "--rebuild" in source
