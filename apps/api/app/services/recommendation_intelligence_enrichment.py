"""Collector-significance enrichment (milestones, creators, homage, audience) — registry-driven."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from sqlmodel import Session, select

from app.models.creator_intelligence import CreatorProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.lunar_issue_identity import normalize_lunar_issue_number
from app.services.popularity_engine import creator_score
from app.services.recommendation_priority_enrichment import (
    OwnedSeriesInventoryStats,
    RecommendationPriorityEnrichment,
    franchise_strength_bonus,
    publisher_strength_bonus,
)

# Milestone issue numbers (collector numbering conventions — not title-specific).
MILESTONE_ISSUE_NUMBERS: frozenset[int] = frozenset({25, 50, 75, 100, 150, 200, 300})

MILESTONE_NUMERIC_BONUS: dict[int, float] = {
    25: 2.0,
    50: 2.5,
    75: 3.0,
    100: 3.5,
    150: 4.0,
    200: 4.5,
    300: 5.0,
}

_ANNIVERSARY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\banniversary\b",
        r"\b\d{1,3}(?:st|nd|rd|th)\s+anniversary\b",
        r"\byears?\s+of\b",
        r"\blegacy\s+numbering\b",
        r"\blegacy\s+issue\b",
        r"\bcontinuity\s+milestone\b",
        r"\bcelebrat(?:e|ing|es)\s+\d+\s+years?\b",
    )
)

_LEGACY_NUMBERING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\blegacy\s+#",
        r"\blegacy\s+number",
        r"\boriginal\s+numbering\b",
        r"\bclassic\s+numbering\b",
    )
)

_SIGNAL_AUDIENCE_TAGS: dict[str, str] = {
    "FIRST_APPEARANCE": "key-issue collectors",
    "FIRST_FULL_APPEARANCE": "key-issue collectors",
    "FIRST_CAMEO": "key-issue collectors",
    "ORIGIN": "key-issue collectors",
    "KEY_ISSUE": "key-issue collectors",
    "MILESTONE_NUMBERING": "milestone collectors",
    "VARIANT_HOT": "variant collectors",
    "RATIO_VARIANT": "variant collectors",
    "INCENTIVE_VARIANT": "variant collectors",
    "NEW_NUMBER_ONE": "launch collectors",
    "UNIVERSE_LAUNCH": "launch collectors",
    "RELAUNCH": "launch collectors",
}

_HOMAGE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), label)
    for p, label in (
        (r"\bhomage\b", "homage cover"),
        (r"\btribute\b", "tribute cover"),
        (r"\bvariant\s+homage\b", "variant homage"),
        (r"\bretro\s+cover\b", "retro cover"),
        (r"\banniversary\s+cover\b", "anniversary cover"),
        (r"\bclassic\s+cover\s+homage\b", "classic cover homage"),
        (r"\bartist\s+homage\b", "artist homage"),
    )
)

_CREATOR_ROLE_WEIGHT: dict[str, float] = {
    "writer": 1.0,
    "artist": 1.05,
    "cover_artist": 1.1,
    "colorist": 0.85,
    "default": 0.9,
}


@dataclass(frozen=True)
class CollectorSignificanceScoreBreakdown:
    """Per-signal scores for ranking audits (registry-driven; not title-specific)."""

    base_score: float = 0.0
    franchise_score: float = 0.0
    publisher_score: float = 0.0
    historical_demand_score: float = 0.0
    continuity_score: float = 0.0
    creator_score: float = 0.0
    milestone_score: float = 0.0
    homage_score: float = 0.0
    audience_score: float = 0.0
    combo_bonus: float = 0.0
    ranking_boost: float = 0.0
    final_score: float = 0.0


@dataclass(frozen=True)
class CollectorSignificanceEnrichment:
    milestone_issue_number: int | None = None
    milestone_bonus: float = 0.0
    creator_bonus: float = 0.0
    homage_bonus: float = 0.0
    franchise_historical_bonus: float = 0.0
    audience_tags: tuple[str, ...] = ()
    investment_thesis: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    decision_boost: float = 0.0
    confidence_boost: float = 0.0
    score_breakdown: CollectorSignificanceScoreBreakdown | None = None


def parse_issue_number_milestone(issue_number: str) -> int | None:
    raw = normalize_lunar_issue_number((issue_number or "").strip().lstrip("#").lower())
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value != int(value):
        return None
    num = int(value)
    return num if num in MILESTONE_ISSUE_NUMBERS else None


def _text_blob(
    *,
    series: ReleaseSeries | None,
    issue: ReleaseIssue | None,
    variants: list[ReleaseVariant] | None,
    rationale: str,
) -> str:
    parts: list[str] = []
    if series is not None:
        parts.extend([series.publisher, series.series_name, series.series_type])
    if issue is not None:
        parts.extend([issue.title, issue.issue_number])
    if variants:
        for v in variants:
            parts.extend([v.variant_name, v.variant_type, v.cover_artist or ""])
    parts.append(rationale)
    return " ".join(p for p in parts if p).lower()


def _milestone_signals(issue_number: str, blob: str) -> tuple[int | None, float, list[str]]:
    num = parse_issue_number_milestone(issue_number)
    bonus = MILESTONE_NUMERIC_BONUS.get(num, 0.0) if num is not None else 0.0
    thesis: list[str] = []
    if num is not None:
        thesis.append(f"Milestone issue #{num}.")
    for pattern in _ANNIVERSARY_PATTERNS:
        if pattern.search(blob):
            bonus += 1.75
            thesis.append("Anniversary or legacy-numbering language in catalog text.")
            break
    for pattern in _LEGACY_NUMBERING_PATTERNS:
        if pattern.search(blob):
            bonus += 1.25
            if not any("legacy" in t.lower() for t in thesis):
                thesis.append("Legacy numbering positioning.")
            break
    return num, round(bonus, 2), thesis


def _homage_signals(blob: str) -> tuple[float, list[str], list[str]]:
    bonus = 0.0
    thesis: list[str] = []
    codes: list[str] = []
    for pattern, label in _HOMAGE_PATTERNS:
        if pattern.search(blob):
            bonus = max(bonus, 3.5)
            thesis.append(f"Homage/tribute signal ({label}).")
            if "HOMAGE_TRIBUTE" not in codes:
                codes.append("HOMAGE_TRIBUTE")
    return bonus, thesis, codes


def _match_notable_creators(session: Session, blob: str, *, min_popularity: float = 68.0) -> tuple[float, list[str], list[str]]:
    """Match CreatorProfile registry entries (not title-specific rules)."""
    matches: list[tuple[str, float, str]] = []
    lower = blob.lower()
    profiles = session.exec(
        select(CreatorProfile).where(CreatorProfile.status == "ACTIVE").limit(400)
    ).all()
    for profile in profiles:
        name = (profile.creator_name or "").strip()
        if len(name) < 3:
            continue
        token = re.escape(name.lower())
        if not re.search(rf"\b{token}\b", lower):
            continue
        cid = int(profile.id or 0)
        if cid <= 0:
            continue
        pop = creator_score(session, creator_id=cid)
        if pop < min_popularity:
            continue
        role = (profile.creator_role or "default").strip().lower()
        weight = _CREATOR_ROLE_WEIGHT.get(role, _CREATOR_ROLE_WEIGHT["default"])
        matches.append((name, pop * weight, role))
        if len(matches) >= 4:
            break
    if not matches:
        return 0.0, [], []
    best = max(matches, key=lambda m: m[1])
    bonus = min(8.5, 2.0 + (best[1] - min_popularity) * 0.12)
    thesis = [f"Notable {best[2]} ({best[0]}) in release metadata."]
    return round(bonus, 2), thesis, ["CREATOR_SIGNIFICANCE"]


def _audience_tags(
    blob: str,
    *,
    milestone_num: int | None,
    creator_bonus: float,
    key_signals: list[str] | None = None,
) -> tuple[tuple[str, ...], list[str]]:
    tags: list[str] = []
    for signal in key_signals or []:
        tag = _SIGNAL_AUDIENCE_TAGS.get(signal.upper())
        if tag and tag not in tags:
            tags.append(tag)
    if milestone_num is not None and milestone_num >= 100:
        if "nostalgia collectors" not in tags:
            tags.append("nostalgia collectors")
    if creator_bonus >= 3.0 and "creator collectors" not in tags:
        tags.append("creator collectors")
    return tuple(tags), []


def _franchise_historical_bonus(
    session: Session,
    *,
    series: ReleaseSeries,
    issue: ReleaseIssue,
    priority_enrichment: RecommendationPriorityEnrichment | None,
    owned_stats: OwnedSeriesInventoryStats | None,
    key_signals: list[str],
) -> tuple[float, list[str]]:
    franchise_bonus, hits = franchise_strength_bonus(
        session,
        series_name=series.series_name,
        issue_title=issue.title,
        issue=issue,
        series=series,
        key_signals=key_signals,
    )
    bonus = franchise_bonus * 0.35
    thesis: list[str] = []
    if hits:
        thesis.append(f"Franchise collector demand ({', '.join(hits)}).")
    if priority_enrichment is not None:
        bonus += priority_enrichment.historical_demand_bonus * 0.4
        bonus += priority_enrichment.continuity_bonus * 0.35
        if priority_enrichment.historical_demand_bonus >= 3.0:
            thesis.append("Historical market demand and liquidity signals.")
        if priority_enrichment.continuity_bonus >= 2.0:
            thesis.append("You already collect this series run.")
    if "MILESTONE_NUMBERING" in {s.upper() for s in key_signals}:
        bonus += 1.5
    pub = (series.publisher or "").strip().lower()
    if owned_stats and pub:
        key = (pub, series.series_name.strip().lower())
        if owned_stats.copies_by_series.get(key, 0) >= 2:
            thesis.append("Ownership overlap with an active collected run.")
            bonus += 1.25
    return round(min(10.0, bonus), 2), thesis


def _audience_score_value(
    tags: tuple[str, ...],
    *,
    milestone_num: int | None,
    creator_bonus: float,
    homage_bonus: float,
) -> float:
    score = min(4.0, len(tags) * 0.85)
    if milestone_num is not None and milestone_num >= 100:
        score += 1.0
    if creator_bonus >= 3.0:
        score += 0.75
    if homage_bonus >= 2.5:
        score += 0.75
    return round(min(5.5, score), 2)


def _ranking_combo_bonus(
    *,
    milestone_bonus: float,
    creator_bonus: float,
    homage_bonus: float,
) -> float:
    combo = 0.0
    if milestone_bonus >= 3.0 and (creator_bonus >= 2.5 or homage_bonus >= 2.5):
        combo += 4.0
    if creator_bonus >= 3.0 and homage_bonus >= 2.5:
        combo += 2.5
    return combo


def collector_ranking_boost(breakdown: CollectorSignificanceScoreBreakdown) -> float:
    """Ranking path: milestone + creator + homage outweigh franchise-only continuation."""
    core = (
        breakdown.milestone_score * 1.25
        + breakdown.creator_score * 1.2
        + breakdown.homage_score * 1.2
        + breakdown.audience_score
        + breakdown.franchise_score * 0.42
        + breakdown.publisher_score * 0.38
        + breakdown.historical_demand_score * 0.32
        + breakdown.continuity_score * 0.28
    )
    return round(min(22.0, core + breakdown.combo_bonus), 2)


def _combine_decision_boost(
    *,
    milestone_bonus: float,
    creator_bonus: float,
    homage_bonus: float,
    franchise_bonus: float,
    milestone_num: int | None,
) -> tuple[float, float]:
    """Generic milestones alone stay modest; strong combos can boost decisions."""
    raw = milestone_bonus + creator_bonus + homage_bonus + franchise_bonus * 0.65
    if milestone_num is not None and creator_bonus < 2.0 and homage_bonus < 2.0 and franchise_bonus < 4.0:
        raw = min(raw, milestone_bonus + 2.5)
    combo = 0.0
    if milestone_bonus >= 3.0 and (creator_bonus >= 2.5 or homage_bonus >= 2.5):
        combo += 3.0
    if creator_bonus >= 3.0 and homage_bonus >= 2.5:
        combo += 2.0
    total = min(14.0, raw + combo)
    confidence = min(0.12, total * 0.008 + (0.03 if combo > 0 else 0.0))
    return round(total, 2), round(confidence, 3)


def build_collector_significance_enrichment(
    session: Session,
    *,
    series: ReleaseSeries | None,
    issue: ReleaseIssue | None,
    variants: list[ReleaseVariant] | None,
    rationale: str,
    key_signals: list[str],
    priority_enrichment: RecommendationPriorityEnrichment | None = None,
    owned_stats: OwnedSeriesInventoryStats | None = None,
    base_score: float = 0.0,
) -> CollectorSignificanceEnrichment:
    enrichment, _ = build_collector_significance_with_breakdown(
        session,
        series=series,
        issue=issue,
        variants=variants,
        rationale=rationale,
        key_signals=key_signals,
        priority_enrichment=priority_enrichment,
        owned_stats=owned_stats,
        base_score=base_score,
    )
    return enrichment


def build_collector_significance_with_breakdown(
    session: Session,
    *,
    series: ReleaseSeries | None,
    issue: ReleaseIssue | None,
    variants: list[ReleaseVariant] | None,
    rationale: str,
    key_signals: list[str],
    priority_enrichment: RecommendationPriorityEnrichment | None = None,
    owned_stats: OwnedSeriesInventoryStats | None = None,
    base_score: float = 0.0,
) -> tuple[CollectorSignificanceEnrichment, CollectorSignificanceScoreBreakdown]:
    empty = CollectorSignificanceScoreBreakdown(base_score=round(float(base_score), 2))
    if issue is None or series is None:
        return CollectorSignificanceEnrichment(), empty

    blob = _text_blob(series=series, issue=issue, variants=variants, rationale=rationale)
    milestone_num, milestone_bonus, milestone_thesis = _milestone_signals(issue.issue_number, blob)
    homage_bonus, homage_thesis, homage_codes = _homage_signals(blob)
    creator_bonus, creator_thesis, creator_codes = _match_notable_creators(session, blob)
    franchise_bonus, franchise_thesis = _franchise_historical_bonus(
        session,
        series=series,
        issue=issue,
        priority_enrichment=priority_enrichment,
        owned_stats=owned_stats,
        key_signals=key_signals,
    )
    audience_tags, _ = _audience_tags(
        blob,
        milestone_num=milestone_num,
        creator_bonus=creator_bonus,
        key_signals=key_signals,
    )

    if priority_enrichment is not None:
        franchise_score = round(float(priority_enrichment.franchise_bonus), 2)
        publisher_score = round(float(priority_enrichment.publisher_bonus), 2)
        historical_demand_score = round(float(priority_enrichment.historical_demand_bonus), 2)
        continuity_score = round(float(priority_enrichment.continuity_bonus), 2)
    else:
        franchise_score, _ = franchise_strength_bonus(
            session,
            series_name=series.series_name,
            issue_title=issue.title,
            issue=issue,
            series=series,
            key_signals=key_signals,
        )
        franchise_score = round(franchise_score, 2)
        publisher_score = round(
            publisher_strength_bonus(series.publisher, owned_stats=owned_stats),
            2,
        )
        historical_demand_score = 0.0
        continuity_score = 0.0

    audience_score = _audience_score_value(
        audience_tags,
        milestone_num=milestone_num,
        creator_bonus=creator_bonus,
        homage_bonus=homage_bonus,
    )
    combo_bonus = _ranking_combo_bonus(
        milestone_bonus=milestone_bonus,
        creator_bonus=creator_bonus,
        homage_bonus=homage_bonus,
    )
    breakdown = CollectorSignificanceScoreBreakdown(
        base_score=round(float(base_score), 2),
        franchise_score=franchise_score,
        publisher_score=publisher_score,
        historical_demand_score=historical_demand_score,
        continuity_score=continuity_score,
        creator_score=creator_bonus,
        milestone_score=milestone_bonus,
        homage_score=homage_bonus,
        audience_score=audience_score,
        combo_bonus=combo_bonus,
        ranking_boost=0.0,
        final_score=0.0,
    )
    ranking_boost = collector_ranking_boost(breakdown)
    breakdown = replace(
        breakdown,
        ranking_boost=ranking_boost,
        final_score=round(base_score + ranking_boost, 2),
    )

    reason_codes: list[str] = []
    if milestone_num is not None or milestone_bonus >= 2.0:
        reason_codes.append("MILESTONE_ISSUE")
    reason_codes.extend(creator_codes)
    reason_codes.extend(homage_codes)
    if franchise_bonus >= 3.0:
        reason_codes.append("HISTORICAL_FRANCHISE")
    if audience_tags:
        reason_codes.append("COLLECTOR_AUDIENCE")

    thesis: list[str] = []
    thesis.extend(milestone_thesis)
    thesis.extend(creator_thesis)
    thesis.extend(homage_thesis)
    thesis.extend(franchise_thesis)
    if audience_tags:
        thesis.append(f"Collector audience: {', '.join(audience_tags)}.")
    if thesis:
        thesis.insert(0, "Why this matters:")

    boost, conf_boost = _combine_decision_boost(
        milestone_bonus=milestone_bonus,
        creator_bonus=creator_bonus,
        homage_bonus=homage_bonus,
        franchise_bonus=franchise_bonus,
        milestone_num=milestone_num,
    )

    enrichment = CollectorSignificanceEnrichment(
        milestone_issue_number=milestone_num,
        milestone_bonus=milestone_bonus,
        creator_bonus=creator_bonus,
        homage_bonus=homage_bonus,
        franchise_historical_bonus=franchise_bonus,
        audience_tags=audience_tags,
        investment_thesis=tuple(thesis[:8]),
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        decision_boost=boost,
        confidence_boost=conf_boost,
        score_breakdown=breakdown,
    )
    return enrichment, breakdown
