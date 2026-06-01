from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.industry_release_signal import IndustryReleaseSignal
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.key_issue_catalog import MILESTONE_ISSUE_NUMBERS
from app.services.lunar_issue_identity import normalize_lunar_issue_number
from app.services.opportunity_scoring import user_owns_series

PUBLISHER_STRENGTH_BY_CODE: dict[str, float] = {
    "MARVEL": 12.0,
    "DC": 11.0,
    "IMAGE": 10.0,
    "BOOM": 8.0,
    "DARK_HORSE": 7.0,
    "IDW": 7.0,
    "DYNAMITE": 6.0,
    "MAD_CAVE": 5.0,
    "ONI": 5.0,
    "MASSIVE": 4.0,
}

SIGNAL_WEIGHTS: dict[str, float] = {
    "NUMBER_ONE": 18.0,
    "FIRST_APPEARANCE": 24.0,
    "RATIO_VARIANT": 12.0,
    "FACSIMILE": -10.0,
    "ANNIVERSARY": 8.0,
    "KEY_EVENT": 10.0,
    "NEW_SERIES": 14.0,
    "ONE_SHOT": 6.0,
    "CROSSOVER": 9.0,
    "MILESTONE": 12.0,
    "UNKNOWN": 2.0,
}

FRANCHISE_KEYWORDS: tuple[str, ...] = (
    "SPIDER",
    "BATMAN",
    "SUPERMAN",
    "WOLVERINE",
    "X-MEN",
    "AVENGERS",
    "TRANSFORMERS",
    "TEENAGE MUTANT",
    "TMNT",
    "STAR WARS",
    "STAR TREK",
    "GI JOE",
    "TRANSFORMERS",
    "WONDER WOMAN",
    "FLASH",
    "GREEN LANTERN",
)

HIGH_RATIO_THRESHOLD = 25


@dataclass(frozen=True)
class IndustryOpportunityComputation:
    opportunity_score: float
    confidence_score: float
    risk_level: str
    rationale: str


def _normalize_issue_number(value: str) -> str:
    return normalize_lunar_issue_number(value.strip().lstrip("#"))


def _franchise_bonus(*, series_name: str, issue_title: str) -> tuple[float, list[str]]:
    haystack = f"{series_name} {issue_title}".upper()
    hits: list[str] = []
    bonus = 0.0
    for keyword in FRANCHISE_KEYWORDS:
        if keyword in haystack and keyword not in hits:
            hits.append(keyword)
            bonus += 4.0
    return min(bonus, 16.0), hits


def _variant_ratio_bonus(variants: list[ReleaseVariant]) -> tuple[float, bool]:
    bonus = 0.0
    high_ratio = False
    max_ratio: int | None = None
    for variant in variants:
        if variant.ratio_value is not None:
            ratio = int(variant.ratio_value)
            max_ratio = ratio if max_ratio is None else max(max_ratio, ratio)
            if ratio >= HIGH_RATIO_THRESHOLD:
                high_ratio = True
    if max_ratio is not None:
        bonus += min(float(max_ratio) / 5.0, 14.0)
    return bonus, high_ratio


def _issue_number_bonus(issue_number: str) -> tuple[float, list[str]]:
    notes: list[str] = []
    bonus = 0.0
    normalized = _normalize_issue_number(issue_number)
    if normalized == "1":
        bonus += 12.0
        notes.append("Issue #1 premium")
    if normalized in MILESTONE_ISSUE_NUMBERS:
        bonus += 8.0
        notes.append(f"Milestone issue #{normalized}")
    return bonus, notes


def _compute_risk_level(
    *,
    signal_types: set[str],
    opportunity_score: float,
    high_ratio: bool,
) -> str:
    if "FACSIMILE" in signal_types:
        return "HIGH"
    if signal_types == {"UNKNOWN"} or (len(signal_types) == 1 and "UNKNOWN" in signal_types):
        return "MEDIUM"
    if high_ratio and "FIRST_APPEARANCE" not in signal_types and "NUMBER_ONE" not in signal_types:
        return "MEDIUM"
    if opportunity_score >= 70.0 and "UNKNOWN" not in signal_types:
        return "LOW"
    if opportunity_score >= 40.0:
        return "MEDIUM"
    return "HIGH"


def compute_industry_opportunity_score(
    session: Session,
    *,
    owner_user_id: int,
    candidate: IndustryReleaseCandidate,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variants: list[ReleaseVariant],
    signals: list[IndustryReleaseSignal],
) -> IndustryOpportunityComputation:
    signal_types = {row.signal_type for row in signals}
    publisher_bonus = PUBLISHER_STRENGTH_BY_CODE.get(candidate.publisher_code.upper(), 5.0)
    rationale_parts = [f"Publisher strength ({candidate.publisher_name}): +{publisher_bonus:.1f}"]

    signal_points = 0.0
    confidences: list[float] = []
    for row in signals:
        weight = SIGNAL_WEIGHTS.get(row.signal_type, 0.0)
        weighted = weight * float(row.confidence_score)
        signal_points += weighted
        if row.signal_type != "UNKNOWN":
            confidences.append(float(row.confidence_score))
        rationale_parts.append(f"{row.signal_type} ({row.confidence_score:.2f}): +{weighted:.1f}")

    issue_bonus, issue_notes = _issue_number_bonus(candidate.issue_number)
    if issue_bonus:
        rationale_parts.extend(issue_notes)

    variant_bonus, high_ratio = _variant_ratio_bonus(variants)
    if variant_bonus:
        rationale_parts.append(f"Variant/ratio presence: +{variant_bonus:.1f}")

    franchise_bonus, franchise_hits = _franchise_bonus(series_name=candidate.series_name, issue_title=issue.title)
    if franchise_bonus:
        rationale_parts.append(f"Franchise keywords ({', '.join(franchise_hits)}): +{franchise_bonus:.1f}")

    collector_bonus = 0.0
    if user_owns_series(
        session,
        owner_user_id=owner_user_id,
        publisher=series.publisher,
        series_name=series.series_name,
    ):
        collector_bonus = 8.0
        rationale_parts.append("Collector relevance (series in collection): +8.0")

    raw_score = publisher_bonus + signal_points + issue_bonus + variant_bonus + franchise_bonus + collector_bonus
    opportunity_score = round(min(100.0, max(0.0, raw_score)), 2)

    if confidences:
        confidence_score = round(min(0.98, max(0.4, sum(confidences) / len(confidences))), 3)
    elif signals:
        confidence_score = round(float(signals[0].confidence_score), 3)
    else:
        confidence_score = 0.35

    risk_level = _compute_risk_level(
        signal_types=signal_types,
        opportunity_score=opportunity_score,
        high_ratio=high_ratio,
    )
    rationale_parts.append(f"Risk level: {risk_level}")

    return IndustryOpportunityComputation(
        opportunity_score=opportunity_score,
        confidence_score=confidence_score,
        risk_level=risk_level,
        rationale="; ".join(rationale_parts),
    )
