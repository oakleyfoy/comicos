from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.industry_release_signal import INDUSTRY_RELEASE_SIGNAL_TYPES
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.services.key_issue_catalog import MILESTONE_ISSUE_NUMBERS
from app.services.lunar_issue_identity import normalize_lunar_issue_number

TARGET_RATIO_VALUES = frozenset({10, 25, 50, 100})
RATIO_TEXT_PATTERN = re.compile(r"\b1\s*:\s*(10|25|50|100)\b", re.IGNORECASE)

FIRST_APPEARANCE_PATTERN = re.compile(
    r"\b(FIRST APPEARANCE|FIRST FULL APPEARANCE|1ST APPEARANCE)\b",
    re.IGNORECASE,
)
FACSIMILE_PATTERN = re.compile(r"\b(FACSIMILE|FACSIMILE EDITION)\b", re.IGNORECASE)
ANNIVERSARY_PATTERN = re.compile(r"\b(ANNIVERSARY|ANNIVERSARY EDITION|YEAR ANNIVERSARY)\b", re.IGNORECASE)
KEY_EVENT_PATTERN = re.compile(
    r"\b(MAJOR EVENT|KEY EVENT|EVENT TIE-IN|TIE-IN|EVENT)\b",
    re.IGNORECASE,
)
CROSSOVER_PATTERN = re.compile(
    r"\b(CROSSOVER|CROSS OVER|VS\.| VS |WAR OF|BATTLE OF)\b",
    re.IGNORECASE,
)
NEW_SERIES_PATTERN = re.compile(r"\b(NEW SERIES|SERIES LAUNCH|ALL NEW)\b", re.IGNORECASE)
ONE_SHOT_PATTERN = re.compile(r"\b(ONE-SHOT|ONE SHOT|1-SHOT)\b", re.IGNORECASE)


@dataclass(frozen=True)
class IndustrySignalDetection:
    signal_type: str
    confidence_score: float
    rationale: str


def _normalize_issue_number(value: str) -> str:
    return normalize_lunar_issue_number(value.strip().lstrip("#"))


def _build_haystack(
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variants: list[ReleaseVariant],
) -> str:
    parts = [series.series_name, issue.title, series.publisher, series.series_type]
    for variant in variants:
        parts.extend([variant.variant_name, variant.variant_type, variant.cover_artist or ""])
        if variant.ratio_value is not None:
            parts.append(f"1:{variant.ratio_value}")
    return " ".join(part for part in parts if part).upper()


def _metadata_first_appearance_signals(session: Session, *, release_id: int) -> list[IndustrySignalDetection]:
    rows = session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == release_id)).all()
    detections: list[IndustrySignalDetection] = []
    for row in rows:
        signal_type = row.signal_type.upper()
        if "FIRST_APPEARANCE" in signal_type or signal_type == "FIRST APPEARANCE":
            detections.append(
                IndustrySignalDetection(
                    signal_type="FIRST_APPEARANCE",
                    confidence_score=min(float(row.confidence_score), 0.95),
                    rationale=f"ReleaseKeySignal metadata: {row.signal_type}",
                )
            )
    return detections


def classify_industry_release_candidate(
    session: Session,
    *,
    candidate: IndustryReleaseCandidate,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variants: list[ReleaseVariant],
) -> list[IndustrySignalDetection]:
    haystack = _build_haystack(issue=issue, series=series, variants=variants)
    issue_number = _normalize_issue_number(candidate.issue_number or issue.issue_number)
    series_type = (series.series_type or "").strip().upper()
    detections: list[IndustrySignalDetection] = []

    if FACSIMILE_PATTERN.search(haystack):
        detections.append(
            IndustrySignalDetection(
                signal_type="FACSIMILE",
                confidence_score=0.9,
                rationale="Title or variant text contains facsimile language.",
            )
        )

    if issue_number == "1":
        confidence = 0.88
        rationale = "Issue number is #1."
        if any(d.signal_type == "FACSIMILE" for d in detections):
            confidence = 0.72
            rationale = "Issue number is #1 (facsimile language also present)."
        detections.append(
            IndustrySignalDetection(
                signal_type="NUMBER_ONE",
                confidence_score=confidence,
                rationale=rationale,
            )
        )

    detections.extend(_metadata_first_appearance_signals(session, release_id=int(candidate.release_id)))
    if FIRST_APPEARANCE_PATTERN.search(haystack):
        detections.append(
            IndustrySignalDetection(
                signal_type="FIRST_APPEARANCE",
                confidence_score=0.9,
                rationale="Issue or variant text includes first appearance language.",
            )
        )

    ratio_hits: set[int] = set()
    for variant in variants:
        if variant.ratio_value in TARGET_RATIO_VALUES:
            ratio_hits.add(int(variant.ratio_value))
        match = RATIO_TEXT_PATTERN.search(variant.variant_name or "")
        if match:
            ratio_hits.add(int(match.group(1)))
    if ratio_hits:
        ratios = ", ".join(f"1:{value}" for value in sorted(ratio_hits))
        detections.append(
            IndustrySignalDetection(
                signal_type="RATIO_VARIANT",
                confidence_score=0.92,
                rationale=f"Detected ratio variant(s): {ratios}.",
            )
        )

    if ANNIVERSARY_PATTERN.search(haystack):
        detections.append(
            IndustrySignalDetection(
                signal_type="ANNIVERSARY",
                confidence_score=0.85,
                rationale="Anniversary language detected in release metadata.",
            )
        )

    if issue_number in MILESTONE_ISSUE_NUMBERS:
        detections.append(
            IndustrySignalDetection(
                signal_type="MILESTONE",
                confidence_score=0.84,
                rationale=f"Issue number #{issue_number} matches milestone numbering rules.",
            )
        )

    if KEY_EVENT_PATTERN.search(haystack):
        detections.append(
            IndustrySignalDetection(
                signal_type="KEY_EVENT",
                confidence_score=0.74,
                rationale="Event or tie-in language detected in release metadata.",
            )
        )

    if CROSSOVER_PATTERN.search(haystack):
        detections.append(
            IndustrySignalDetection(
                signal_type="CROSSOVER",
                confidence_score=0.78,
                rationale="Crossover language detected in series or issue text.",
            )
        )

    if series_type in {"ONE_SHOT", "ONE-SHOT"} or ONE_SHOT_PATTERN.search(haystack):
        detections.append(
            IndustrySignalDetection(
                signal_type="ONE_SHOT",
                confidence_score=0.86,
                rationale="Series type or title indicates a one-shot release.",
            )
        )

    if (
        series_type in {"NEW", "NEW_SERIES"}
        or NEW_SERIES_PATTERN.search(haystack)
        or (issue_number == "1" and re.search(r"\bNEW\b", haystack))
    ):
        detections.append(
            IndustrySignalDetection(
                signal_type="NEW_SERIES",
                confidence_score=0.82,
                rationale="New series launch indicators present in metadata.",
            )
        )

    deduped: dict[str, IndustrySignalDetection] = {}
    for row in detections:
        if row.signal_type not in INDUSTRY_RELEASE_SIGNAL_TYPES:
            continue
        existing = deduped.get(row.signal_type)
        if existing is None or row.confidence_score > existing.confidence_score:
            deduped[row.signal_type] = row

    if not deduped:
        deduped["UNKNOWN"] = IndustrySignalDetection(
            signal_type="UNKNOWN",
            confidence_score=0.35,
            rationale="No collectible/spec keyword rules matched for this candidate.",
        )

    return list(deduped.values())
