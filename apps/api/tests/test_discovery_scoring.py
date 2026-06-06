from __future__ import annotations

from app.services.p81_discovery_scoring import P81ScoreInput, category_for_score, score_discovery_opportunity


def test_milestone_and_franchise_scoring() -> None:
    score, signals = score_discovery_opportunity(
        P81ScoreInput(
            opportunity_type="MILESTONE",
            title="Teenage Mutant Ninja Turtles #300",
            summary="",
            series_name="Teenage Mutant Ninja Turtles",
            issue_number="300",
            variant_label="",
            publisher="IDW",
            creators=[],
        )
    )
    assert score >= 60
    assert "Milestone" in " ".join(signals)
    assert category_for_score(score) in {"WATCH", "HIGH_OPPORTUNITY", "MUST_WATCH"}


def test_number_one_category() -> None:
    score, _ = score_discovery_opportunity(
        P81ScoreInput(
            opportunity_type="NEW_1",
            title="Absolute Batman #1",
            summary="",
            series_name="Absolute Batman",
            issue_number="1",
            variant_label="",
            publisher="DC",
            creators=["Ryan Stegman"],
        )
    )
    assert score >= 50
    assert category_for_score(score) in {"WATCH", "HIGH_OPPORTUNITY", "MUST_WATCH"}
