from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.key_issue_intelligence import (
    SOURCE_VERSION,
    KeyIssueClassification,
    KeyIssueEvidence,
    KeyIssueProfile,
    KeyIssueSignal,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.key_issue_catalog import MILESTONE_ISSUE_NUMBERS

TITLE_KEYWORD_RULES: tuple[tuple[str, str, float], ...] = (
    (r"\bFIRST APPEARANCE\b", "FIRST_APPEARANCE", 0.9),
    (r"\bFIRST FULL APPEARANCE\b", "FIRST_FULL_APPEARANCE", 0.92),
    (r"\bCAMEO\b", "FIRST_CAMEO", 0.78),
    (r"\bORIGIN OF\b", "ORIGIN", 0.88),
    (r"\bORIGIN\b", "ORIGIN", 0.82),
    (r"\bDEATH OF\b", "DEATH", 0.86),
    (r"\bDIES\b", "DEATH", 0.8),
    (r"\bRESURRECTION\b", "RESURRECTION", 0.84),
    (r"\bSTATUS QUO\b", "MAJOR_STATUS_CHANGE", 0.8),
    (r"\bANNIVERSARY\b", "ANNIVERSARY", 0.85),
    (r"\bFINAL ISSUE\b", "LAST_ISSUE", 0.87),
    (r"\bLAST ISSUE\b", "LAST_ISSUE", 0.87),
    (r"\bFINAL\b", "FINAL_STORYLINE", 0.75),
    (r"\bEVENT\b", "MAJOR_EVENT", 0.74),
    (r"\bNEW UNIVERSE\b", "UNIVERSE_LAUNCH", 0.88),
    (r"\bUNIVERSE LAUNCH\b", "UNIVERSE_LAUNCH", 0.9),
    (r"\bRELAUNCH\b", "RELAUNCH", 0.83),
    (r"\b#1 FOR\b", "RELAUNCH", 0.8),
    (r"\bTEAM-?UP\b", "FIRST_TEAM_APPEARANCE", 0.76),
    (r"\bVILLAIN\b", "FIRST_VILLAIN_APPEARANCE", 0.77),
)


@dataclass(frozen=True)
class KeyIssueDetection:
    key_issue_type: str
    confidence_score: float
    signal_strength: float
    evidence: str


def _normalize_issue_number(value: str) -> str:
    return value.strip().lstrip("#")


def _issue_text(issue: ReleaseIssue, series: ReleaseSeries, variant: ReleaseVariant | None) -> str:
    parts = [series.series_name, issue.title, series.publisher]
    if variant and variant.variant_name:
        parts.append(variant.variant_name)
    if variant and variant.cover_artist:
        parts.append(variant.cover_artist)
    return " ".join(parts).upper()


def detect_key_issues_for_issue(
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variant: ReleaseVariant | None = None,
) -> list[KeyIssueDetection]:
    detections: list[KeyIssueDetection] = []
    haystack = _issue_text(issue, series, variant)
    issue_number = _normalize_issue_number(issue.issue_number)

    for pattern, key_type, confidence in TITLE_KEYWORD_RULES:
        if re.search(pattern, haystack):
            detections.append(
                KeyIssueDetection(
                    key_issue_type=key_type,
                    confidence_score=confidence,
                    signal_strength=confidence,
                    evidence=f"title_match:{pattern}",
                )
            )

    if issue_number in MILESTONE_ISSUE_NUMBERS:
        detections.append(
            KeyIssueDetection(
                key_issue_type="MILESTONE_NUMBERING",
                confidence_score=0.84,
                signal_strength=0.84,
                evidence=f"milestone_issue_number:{issue_number}",
            )
        )

    if issue_number == "1":
        if re.search(r"\bNEW\b", haystack) or re.search(r"\bLAUNCH\b", haystack):
            detections.append(
                KeyIssueDetection(
                    key_issue_type="UNIVERSE_LAUNCH",
                    confidence_score=0.82,
                    signal_strength=0.82,
                    evidence="issue_one_universe_launch",
                )
            )
        detections.append(
            KeyIssueDetection(
                key_issue_type="RELAUNCH",
                confidence_score=0.7,
                signal_strength=0.7,
                evidence="issue_number_one",
            )
        )

    deduped: dict[str, KeyIssueDetection] = {}
    for row in detections:
        existing = deduped.get(row.key_issue_type)
        if existing is None or row.confidence_score > existing.confidence_score:
            deduped[row.key_issue_type] = row
    return list(deduped.values())


def _upsert_profile(
    session: Session,
    *,
    release_issue_id: int,
    key_issue_type: str,
    importance_score: float,
    confidence_score: float,
) -> KeyIssueProfile:
    row = session.exec(
        select(KeyIssueProfile)
        .where(KeyIssueProfile.release_issue_id == release_issue_id)
        .where(KeyIssueProfile.key_issue_type == key_issue_type)
    ).first()
    if row is None:
        row = KeyIssueProfile(
            release_issue_id=release_issue_id,
            key_issue_type=key_issue_type,
            importance_score=importance_score,
            confidence_score=confidence_score,
            source_version=SOURCE_VERSION,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    row.importance_score = max(float(row.importance_score), importance_score)
    row.confidence_score = max(float(row.confidence_score), confidence_score)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _upsert_signal(session: Session, *, release_issue_id: int, signal_type: str, signal_strength: float) -> None:
    existing = session.exec(
        select(KeyIssueSignal)
        .where(KeyIssueSignal.release_issue_id == release_issue_id)
        .where(KeyIssueSignal.signal_type == signal_type)
    ).first()
    if existing:
        existing.signal_strength = max(float(existing.signal_strength), signal_strength)
        session.add(existing)
        return
    session.add(
        KeyIssueSignal(
            release_issue_id=release_issue_id,
            signal_type=signal_type,
            signal_strength=signal_strength,
        )
    )


def _upsert_classification(session: Session, *, release_issue_id: int, classification: str) -> None:
    row = session.exec(
        select(KeyIssueClassification).where(KeyIssueClassification.release_issue_id == release_issue_id)
    ).first()
    if row:
        row.classification = classification
        session.add(row)
        return
    session.add(KeyIssueClassification(release_issue_id=release_issue_id, classification=classification))


def run_key_issue_detection_for_owner(session: Session, *, owner_user_id: int) -> int:
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    created = 0
    for issue, series in rows:
        variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue.id)).all()
        targets = [None, *variants]
        primary_classification: str | None = None
        best_importance = 0.0
        for variant in targets:
            for detection in detect_key_issues_for_issue(issue=issue, series=series, variant=variant):
                importance = round(detection.confidence_score * 100.0, 2)
                profile = _upsert_profile(
                    session,
                    release_issue_id=int(issue.id or 0),
                    key_issue_type=detection.key_issue_type,
                    importance_score=importance,
                    confidence_score=detection.confidence_score,
                )
                _upsert_signal(
                    session,
                    release_issue_id=int(issue.id or 0),
                    signal_type=detection.key_issue_type,
                    signal_strength=detection.signal_strength,
                )
                session.add(
                    KeyIssueEvidence(
                        key_issue_profile_id=int(profile.id or 0),
                        evidence_type="DETECTION",
                        evidence_value=detection.evidence,
                    )
                )
                created += 1
                if importance >= best_importance:
                    best_importance = importance
                    primary_classification = detection.key_issue_type
        if primary_classification:
            _upsert_classification(
                session,
                release_issue_id=int(issue.id or 0),
                classification=primary_classification,
            )
    session.commit()
    return created
