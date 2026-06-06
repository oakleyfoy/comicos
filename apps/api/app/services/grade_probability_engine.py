"""P72-01 grade probability model (metadata-based; no image analysis)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

GRADE_KEYS = ("9.8", "9.6", "9.4", "9.2", "other")


@dataclass(frozen=True)
class GradeProbabilityDistribution:
    grade_9_8: float
    grade_9_6: float
    grade_9_4: float
    grade_9_2: float
    grade_other: float
    expected_grade_label: str
    confidence: float
    factors_json: dict

    def as_dict(self) -> dict[str, float]:
        return {
            "9.8": self.grade_9_8,
            "9.6": self.grade_9_6,
            "9.4": self.grade_9_4,
            "9.2": self.grade_9_2,
            "other": self.grade_other,
        }


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        n = len(weights)
        return {k: round(1.0 / n, 4) for k in weights}
    return {k: round(v / total, 4) for k, v in weights.items()}


def estimate_grade_probabilities(
    *,
    publisher: str,
    release_year: int | None,
    ownership_source: str | None,
    condition_notes: str | None,
    age_years: int | None = None,
) -> GradeProbabilityDistribution:
    today = date.today()
    if age_years is None and release_year is not None:
        age_years = max(0, today.year - release_year)

    weights = {"9.8": 0.15, "9.6": 0.35, "9.4": 0.25, "9.2": 0.15, "other": 0.10}
    notes = (condition_notes or "").lower()
    if any(k in notes for k in ("nm", "near mint", "sharp", "clean")):
        weights["9.8"] += 0.12
        weights["9.6"] += 0.08
        weights["other"] -= 0.1
    if any(k in notes for k in ("crease", "spine", "color break", "tear", "mark")):
        weights["9.4"] += 0.1
        weights["9.2"] += 0.08
        weights["9.8"] -= 0.12
        weights["9.6"] -= 0.06
    if age_years is not None and age_years >= 30:
        weights["9.2"] += 0.06
        weights["other"] += 0.04
        weights["9.8"] -= 0.05
    pub = (publisher or "").lower()
    if pub in {"marvel", "dc", "image"} and release_year is not None and release_year >= 2015:
        weights["9.8"] += 0.05
        weights["9.6"] += 0.03
    if ownership_source and "convention" in ownership_source.lower():
        weights["9.4"] += 0.04
        weights["9.2"] += 0.02

    norm = _normalize(weights)
    expected = max(norm.items(), key=lambda x: x[1])[0]
    confidence = min(0.92, 0.42 + norm.get(expected, 0.0) * 0.55)
    return GradeProbabilityDistribution(
        grade_9_8=norm["9.8"],
        grade_9_6=norm["9.6"],
        grade_9_4=norm["9.4"],
        grade_9_2=norm["9.2"],
        grade_other=norm["other"],
        expected_grade_label=expected if expected != "other" else "9.0",
        confidence=round(confidence, 3),
        factors_json={
            "publisher": publisher,
            "release_year": release_year,
            "ownership_source": ownership_source,
            "condition_notes_present": bool(condition_notes),
            "age_years": age_years,
        },
    )
