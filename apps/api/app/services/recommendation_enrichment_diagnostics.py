"""Diagnostics for collector enrichment coverage (no ranking weight changes)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.creator_intelligence import CreatorProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.popularity_engine import creator_score
from app.services.recommendation_intelligence_enrichment import (
    _ANNIVERSARY_PATTERNS,
    _LEGACY_NUMBERING_PATTERNS,
    _text_blob,
    parse_issue_number_milestone,
)
from app.services.recommendation_title_index import resolve_release_pair
from app.services.recommendation_title_normalize import (
    display_title_key,
    normalize_recommendation_title_key,
)


@dataclass(frozen=True)
class RecommendationEnrichmentDiagnostics:
    title: str
    recommendation_type: str
    title_key: str
    release_index_key: str | None
    release_matched: bool
    enrichment_attempted: bool
    enrichment_successful: bool
    creator_score: float
    milestone_score: float
    creator_zero_reason: str | None
    milestone_zero_reason: str | None


def _legacy_title_key(title: str) -> str:
    key = title.strip().lower()
    if key.endswith(" (variants)"):
        key = key[: -len(" (variants)")]
    return key


def creator_zero_reason(
    session: Session,
    *,
    release_matched: bool,
    enrichment_attempted: bool,
    creator_score: float,
    series: ReleaseSeries | None,
    issue: ReleaseIssue | None,
    variants: list[ReleaseVariant] | None,
    rationale: str,
) -> str | None:
    if creator_score > 0:
        return None
    if not release_matched:
        return "title_index_miss"
    if not enrichment_attempted:
        return "enrichment_skipped"
    if issue is None or series is None:
        return "enrichment_skipped"
    blob = _text_blob(series=series, issue=issue, variants=variants, rationale=rationale)
    lower = blob.lower()
    profiles = session.exec(
        select(CreatorProfile).where(CreatorProfile.status == "ACTIVE").limit(400)
    ).all()
    any_name_in_blob = False
    any_below_threshold = False
    for profile in profiles:
        name = (profile.creator_name or "").strip()
        if len(name) < 3:
            continue
        token = re.escape(name.lower())
        if not re.search(rf"\b{token}\b", lower):
            continue
        any_name_in_blob = True
        cid = int(profile.id or 0)
        if cid <= 0:
            continue
        if creator_score(session, creator_id=cid) < 68.0:
            any_below_threshold = True
            continue
        return None
    if any_below_threshold:
        return "creator_metadata_below_threshold"
    if any_name_in_blob:
        return "creator_metadata_below_threshold"
    return "no_creator_metadata"


def milestone_zero_reason(
    *,
    release_matched: bool,
    enrichment_attempted: bool,
    milestone_score: float,
    issue: ReleaseIssue | None,
    series: ReleaseSeries | None,
    variants: list[ReleaseVariant] | None,
    rationale: str,
) -> str | None:
    if milestone_score > 0:
        return None
    if not release_matched:
        return "title_index_miss"
    if not enrichment_attempted or issue is None or series is None:
        return "enrichment_skipped"
    blob = _text_blob(series=series, issue=issue, variants=variants, rationale=rationale)
    num = parse_issue_number_milestone(issue.issue_number)
    if num is not None:
        return "no_milestone"
    for pattern in _ANNIVERSARY_PATTERNS + _LEGACY_NUMBERING_PATTERNS:
        if pattern.search(blob):
            return "parser_miss"
    return "no_milestone"


def build_enrichment_diagnostics_for_candidate(
    session: Session,
    *,
    title: str,
    recommendation_type: str,
    rationale: str,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
    variants_by_issue: dict[int, list[ReleaseVariant]] | None,
    collector_score_breakdown,
) -> RecommendationEnrichmentDiagnostics:
    title_key = normalize_recommendation_title_key(title)
    pair = resolve_release_pair(title, release_index)
    release_matched = pair is not None
    issue, series = pair if pair else (None, None)
    issue_id = int(issue.id) if issue and issue.id is not None else 0
    enrichment_attempted = release_matched and issue_id > 0
    enrichment_successful = collector_score_breakdown is not None
    creator_sc = float(getattr(collector_score_breakdown, "creator_score", 0.0) or 0.0) if collector_score_breakdown else 0.0
    milestone_sc = float(getattr(collector_score_breakdown, "milestone_score", 0.0) or 0.0) if collector_score_breakdown else 0.0
    variants = (variants_by_issue or {}).get(issue_id, []) if issue_id else []
    index_key = None
    if issue is not None and series is not None:
        index_key = display_title_key(series_name=series.series_name, issue_number=issue.issue_number)
    return RecommendationEnrichmentDiagnostics(
        title=title,
        recommendation_type=recommendation_type,
        title_key=title_key,
        release_index_key=index_key,
        release_matched=release_matched,
        enrichment_attempted=enrichment_attempted,
        enrichment_successful=enrichment_successful,
        creator_score=creator_sc,
        milestone_score=milestone_sc,
        creator_zero_reason=creator_zero_reason(
            session,
            release_matched=release_matched,
            enrichment_attempted=enrichment_attempted,
            creator_score=creator_sc,
            series=series,
            issue=issue,
            variants=variants,
            rationale=rationale,
        ),
        milestone_zero_reason=milestone_zero_reason(
            release_matched=release_matched,
            enrichment_attempted=enrichment_attempted,
            milestone_score=milestone_sc,
            issue=issue,
            series=series,
            variants=variants,
            rationale=rationale,
        ),
    )


def title_index_resolution_stats(
    *,
    candidates: list,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
) -> dict[str, object]:
    processed = len(candidates)
    matched = 0
    legacy_matched = 0
    unmatched_titles: list[str] = []
    normalization_samples: list[dict[str, str]] = []
    for cand in candidates:
        title = cand.title
        if resolve_release_pair(title, release_index) is not None:
            matched += 1
        else:
            unmatched_titles.append(title)
        legacy_key = _legacy_title_key(title)
        if release_index.get(legacy_key) is not None:
            legacy_matched += 1
        if len(normalization_samples) < 30 and normalize_recommendation_title_key(title) != legacy_key:
            pair = resolve_release_pair(title, release_index)
            release_key = None
            if pair:
                issue, series = pair
                release_key = display_title_key(series_name=series.series_name, issue_number=issue.issue_number)
            normalization_samples.append(
                {
                    "recommendation_title": title,
                    "legacy_key": legacy_key,
                    "normalized_key": normalize_recommendation_title_key(title),
                    "release_index_key": release_key or "",
                }
            )
    unmatched = processed - matched
    pct = round(100.0 * matched / processed, 2) if processed else 0.0
    legacy_pct = round(100.0 * legacy_matched / processed, 2) if processed else 0.0
    unmatched_sorted = sorted(unmatched_titles, key=lambda t: t.lower())
    return {
        "candidates_processed": processed,
        "candidates_matched": matched,
        "candidates_unmatched": unmatched,
        "match_percentage": pct,
        "legacy_match_percentage": legacy_pct,
        "top_unmatched_titles": unmatched_sorted[:100],
        "normalization_samples": normalization_samples,
    }
