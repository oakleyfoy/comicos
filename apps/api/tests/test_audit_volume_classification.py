"""Unit checks for volume classification audit helpers (no DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_audit_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_volume_classification.py"
    spec = importlib.util.spec_from_file_location("audit_volume_classification", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_numeric_issue_parsing() -> None:
    mod = _load_audit_module()
    assert mod._numeric_issue("100") == 100.0
    assert mod._numeric_issue("#100") == 100.0
    assert mod._numeric_issue("TP") is None


def test_vol_pattern_detection() -> None:
    mod = _load_audit_module()
    assert mod._vol_in_text("Youngblood Vol 6", "Youngblood #100")
    assert not mod._vol_in_text("Youngblood", "Youngblood #100")


def test_youngblood_vol6_classified_collected_not_single() -> None:
    from app.services.recommendation_catalog_quality import classify_catalog_text

    q = classify_catalog_text(
        series_name="Youngblood",
        issue_number="100",
        title="Youngblood Vol 6 #100",
        publisher="Image",
    )
    assert q.is_collected_edition
    assert not q.is_single_issue

    q2 = classify_catalog_text(
        series_name="Youngblood",
        issue_number="100",
        title="Youngblood #100",
        publisher="Image",
    )
    assert q2.is_single_issue
