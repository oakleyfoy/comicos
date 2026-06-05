from __future__ import annotations

from pathlib import Path

import pytest

from app.services.external_catalog.decision_signals import (
    FIELD_TO_DECISION_SIGNAL,
    build_decision_signals_from_normalized,
)
from app.services.external_catalog.league_of_comic_geeks import parse_issue_detail_page
from app.services.external_catalog.normalization import normalize_locg_issue

pytestmark = pytest.mark.usefixtures("client")

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "locg"


def test_field_to_decision_signal_map_covers_critical_fields() -> None:
    assert FIELD_TO_DECISION_SIGNAL["pull_count"] == "demand_score"
    assert FIELD_TO_DECISION_SIGNAL["foc_date"] == "preorder_urgency"
    assert FIELD_TO_DECISION_SIGNAL["variants"] == "cover_recommendation_and_ratio_risk"
    assert FIELD_TO_DECISION_SIGNAL["description"] == "narrative_catalyst_detection"


def test_build_decision_signals_from_youngblood_fixture() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    norm = normalize_locg_issue(parse_issue_detail_page(html), source_name="LEAGUE_OF_COMIC_GEEKS")
    assert norm.decision_signals_json is not None
    signals = norm.decision_signals_json
    assert signals["demand_score"] > 0
    assert signals["demand_components"]["pull_count"] == 842
    assert signals["foc_urgency"] is not None
    assert signals["buying_window"] is not None
    assert signals["creator_significance_score"] > 50
    assert signals["issue_position"]["is_milestone_issue"] is True
    assert any(v["ratio_value"] == 25 for v in signals["variant_intel"])
    assert signals["cover_review_assets"]["cover_image_url"]
    assert "first_appearance" in signals["narrative_catalysts"] or signals["issue_position"]["is_milestone_issue"]


def test_decision_signals_include_provenance_map() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    norm = normalize_locg_issue(parse_issue_detail_page(html), source_name="LEAGUE_OF_COMIC_GEEKS")
    assert norm.decision_signals_json["signal_field_map"]["want_count"] == "demand_score"
