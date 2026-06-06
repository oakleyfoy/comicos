from __future__ import annotations

from app.services.grade_probability_engine import estimate_grade_probabilities


def test_grade_probabilities_sum_to_one() -> None:
    dist = estimate_grade_probabilities(
        publisher="DC",
        release_year=2024,
        ownership_source="direct",
        condition_notes="Near mint, sharp corners",
    )
    total = sum(dist.as_dict().values())
    assert abs(total - 1.0) < 0.02
    assert dist.expected_grade_label in {"9.8", "9.6", "9.4", "9.2", "9.0"}
    assert 0.0 < dist.confidence <= 0.92


def test_defect_notes_shift_probability_down_from_9_8() -> None:
    clean = estimate_grade_probabilities(
        publisher="Marvel",
        release_year=2020,
        ownership_source=None,
        condition_notes="NM sharp",
    )
    rough = estimate_grade_probabilities(
        publisher="Marvel",
        release_year=2020,
        ownership_source=None,
        condition_notes="crease spine tear",
    )
    assert rough.grade_9_8 < clean.grade_9_8
    assert rough.grade_9_4 + rough.grade_9_2 > clean.grade_9_4 + clean.grade_9_2
