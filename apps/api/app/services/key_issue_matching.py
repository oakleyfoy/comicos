from __future__ import annotations

import re

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.intelligence_matching import match_release_issue
from app.services.key_issue_catalog import CANONICAL_KEY_ISSUE_CATALOG, KeyIssueCatalogEntry
from app.services.key_issue_engine import _upsert_classification, _upsert_profile, _upsert_signal


def _normalize_series(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _normalize_issue_number(value: str) -> str:
    return value.strip().lstrip("#")


def _catalog_matches_issue(entry: KeyIssueCatalogEntry, *, issue: ReleaseIssue, series: ReleaseSeries) -> bool:
    if _normalize_issue_number(issue.issue_number) != _normalize_issue_number(entry.issue_number):
        return False
    series_norm = _normalize_series(series.series_name)
    entry_norm = _normalize_series(entry.series_name)
    if series_norm == entry_norm or entry_norm in series_norm or series_norm in entry_norm:
        if entry.title_hint and entry.title_hint.upper() not in issue.title.upper():
            return False
        return True
    return False


def match_catalog_key_issues_for_owner(session: Session, *, owner_user_id: int) -> int:
    matched = 0
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    for issue, series in rows:
        intelligence = match_release_issue(session, issue=issue, series=series)
        for entry in CANONICAL_KEY_ISSUE_CATALOG:
            if not _catalog_matches_issue(entry, issue=issue, series=series):
                continue
            confidence = entry.confidence_score
            if intelligence.matched_entities:
                confidence = min(0.99, confidence + 0.02)
            profile = _upsert_profile(
                session,
                release_issue_id=int(issue.id or 0),
                key_issue_type=entry.key_issue_type,
                importance_score=entry.importance_score,
                confidence_score=confidence,
            )
            _upsert_signal(
                session,
                release_issue_id=int(issue.id or 0),
                signal_type=entry.key_issue_type,
                signal_strength=confidence,
            )
            _upsert_classification(
                session,
                release_issue_id=int(issue.id or 0),
                classification=entry.classification,
            )
            from app.models.key_issue_intelligence import KeyIssueEvidence

            session.add(
                KeyIssueEvidence(
                    key_issue_profile_id=int(profile.id or 0),
                    evidence_type="CATALOG_MATCH",
                    evidence_value=f"{entry.series_name} #{entry.issue_number}",
                )
            )
            matched += 1
    session.commit()
    return matched


def match_pattern_key_issues_for_owner(session: Session, *, owner_user_id: int) -> int:
    """Pattern-based matches for live Lunar-style titles without exact catalog rows."""
    matched = 0
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    for issue, series in rows:
        title = issue.title.upper()
        issue_number = _normalize_issue_number(issue.issue_number)
        patterns: list[tuple[str, str, float, float]] = []
        if "ANNIVERSARY" in title:
            patterns.append(("ANNIVERSARY", "ANNIVERSARY", 82.0, 0.86))
        if issue_number == "300" and ("TMNT" in series.series_name.upper() or "NINJA TURTLE" in series.series_name.upper()):
            patterns.append(("MILESTONE_NUMBERING", "MILESTONE_NUMBERING", 88.0, 0.89))
        if issue_number == "25" and "GI JOE" in series.series_name.upper():
            patterns.append(("MILESTONE_NUMBERING", "MILESTONE_NUMBERING", 84.0, 0.87))
        if issue_number == "1" and ("NEW UNIVERSE" in title or "NEW UNIVERSE" in series.series_name.upper()):
            patterns.append(("UNIVERSE_LAUNCH", "UNIVERSE_LAUNCH", 86.0, 0.88))
        for key_type, classification, importance, confidence in patterns:
            _upsert_profile(
                session,
                release_issue_id=int(issue.id or 0),
                key_issue_type=key_type,
                importance_score=importance,
                confidence_score=confidence,
            )
            _upsert_signal(
                session,
                release_issue_id=int(issue.id or 0),
                signal_type=key_type,
                signal_strength=confidence,
            )
            _upsert_classification(session, release_issue_id=int(issue.id or 0), classification=classification)
            matched += 1
    session.commit()
    return matched
