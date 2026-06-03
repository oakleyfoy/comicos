"""Phase-2 recommendation priority: franchise, publisher, demand, collector continuity."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlmodel import Session, func, select

from app.models import ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.services.lunar_issue_identity import normalize_lunar_issue_number
from app.services.recommendation_v2_scoring_context import RecommendationV2ScoringContext

KEY_SIGNAL_TYPES = frozenset(
    {
        "NEW_NUMBER_ONE",
        "KEY_ISSUE",
        "FIRST_APPEARANCE",
        "FIRST_FULL_APPEARANCE",
        "FIRST_CAMEO",
        "ORIGIN",
        "MILESTONE_NUMBERING",
        "UNIVERSE_LAUNCH",
        "RELAUNCH",
        "VARIANT_HOT",
        "RATIO_VARIANT",
        "INCENTIVE_VARIANT",
    }
)

NEW_ONE_SIGNALS = frozenset({"NEW_NUMBER_ONE", "UNIVERSE_LAUNCH", "RELAUNCH"})


def _is_number_one(issue_number: str) -> bool:
    raw = normalize_lunar_issue_number((issue_number or "").strip().lstrip("#").lower())
    return raw in {"1", "1.0"} or raw.startswith("1/")

# (regex pattern, priority bonus) — first match wins highest tier via max accumulation cap
_FRANCHISE_PATTERNS: tuple[tuple[re.Pattern[str], float, str], ...] = tuple(
    (
        re.compile(p, re.IGNORECASE),
        bonus,
        label,
    )
    for p, bonus, label in (
        (r"\bbatman\b", 14.0, "Batman"),
        (r"\bspider-?man\b", 13.5, "Spider-Man"),
        (r"\bx-?men\b", 12.5, "X-Men"),
        (r"\btransformers\b", 12.0, "Transformers"),
        (r"\bgi\s*joe\b|\bg\.?\s*i\.?\s*joe\b", 11.5, "GI Joe"),
        (r"\btmnt\b|teenage\s+mutant\s+ninja", 11.5, "TMNT"),
        (r"\bbattle\s+beast\b", 11.0, "Battle Beast"),
        (r"\bsuperman\b", 11.0, "Superman"),
        (r"\bwolverine\b", 10.5, "Wolverine"),
        (r"\bavengers\b", 10.0, "Avengers"),
        (r"\bstar\s+wars\b", 10.0, "Star Wars"),
        (r"\babsolute\b", 9.5, "Absolute edition"),
        (r"\bskybound\b", 7.5, "Skybound franchise"),
        (r"\binvincible\b", 8.5, "Invincible"),
        (r"\bwalking\s+dead\b", 8.0, "Walking Dead"),
    )
)

_PUBLISHER_TOKENS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("marvel", "marvel comics"), 9.0),
    (("dc comics", "dc"), 8.5),
    (("image comics", "image"), 7.5),
    (("skybound", "sky bound"), 7.0),
    (("boom studios", "boom! studios", "boom"), 6.5),
    (("dark horse", "dark horse comics"), 6.25),
    (("idw", "idw publishing"), 5.75),
    (("dynamite", "dynamite entertainment"), 5.25),
    (("oni press", "oni"), 4.75),
    (("mad cave", "mad cave studios"), 4.5),
)


@dataclass(frozen=True)
class OwnedSeriesInventoryStats:
    """Copies owned per (publisher, series) for continuity + demand proxies."""

    copies_by_series: dict[tuple[str, str], int] = field(default_factory=dict)
    avg_fmv_by_series: dict[tuple[str, str], float] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendationPriorityEnrichment:
    franchise_bonus: float = 0.0
    publisher_bonus: float = 0.0
    historical_demand_bonus: float = 0.0
    continuity_bonus: float = 0.0
    confidence_score: float = 0.58
    franchise_hits: tuple[str, ...] = ()
    rationale_bits: tuple[str, ...] = ()


def _normalize_publisher(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_series(value: str | None) -> str:
    return (value or "").strip().lower()


def franchise_strength_bonus(*, series_name: str, issue_title: str | None = None) -> tuple[float, tuple[str, ...]]:
    blob = f"{series_name} {issue_title or ''}"
    hits: list[str] = []
    bonus = 0.0
    for pattern, tier_bonus, label in _FRANCHISE_PATTERNS:
        if pattern.search(blob):
            hits.append(label)
            bonus = max(bonus, tier_bonus)
    return bonus, tuple(hits)


def publisher_strength_bonus(publisher: str | None) -> float:
    pub = _normalize_publisher(publisher)
    if not pub:
        return 0.0
    best = 0.0
    for tokens, score in _PUBLISHER_TOKENS:
        for token in tokens:
            if token in pub or pub in token:
                best = max(best, score)
    return best


def build_owned_series_inventory_stats(session: Session, *, owner_user_id: int) -> OwnedSeriesInventoryStats:
    rows = session.exec(
        select(
            Publisher.name,
            ComicTitle.name,
            func.count(InventoryCopy.id),
            func.avg(InventoryCopy.current_fmv),
        )
        .join(Variant, Variant.id == InventoryCopy.variant_id)
        .join(ComicIssue, ComicIssue.id == Variant.comic_issue_id)
        .join(ComicTitle, ComicTitle.id == ComicIssue.comic_title_id)
        .join(Publisher, Publisher.id == ComicTitle.publisher_id)
        .where(InventoryCopy.user_id == owner_user_id)
        .group_by(Publisher.name, ComicTitle.name)
    ).all()
    copies: dict[tuple[str, str], int] = {}
    avg_fmv: dict[tuple[str, str], float] = {}
    for publisher, series_name, count, mean_fmv in rows:
        key = (_normalize_publisher(str(publisher)), _normalize_series(str(series_name)))
        copies[key] = int(count or 0)
        if mean_fmv is not None and float(mean_fmv) > 0:
            avg_fmv[key] = float(mean_fmv)
    return OwnedSeriesInventoryStats(copies_by_series=copies, avg_fmv_by_series=avg_fmv)


def _historical_demand_bonus(
    *,
    series_key: tuple[str, str],
    owned_stats: OwnedSeriesInventoryStats | None,
    market_user: dict[str, float] | None,
) -> float:
    bonus = 0.0
    if market_user:
        combined = float(market_user.get("combined_market_user_score", 50.0))
        bonus += min(8.0, max(0.0, (combined - 50.0) * 0.22))
        market = float(market_user.get("market_demand_score", 50.0))
        bonus += min(4.0, max(0.0, (market - 50.0) * 0.12))
        velocity = float(market_user.get("liquidity_score", 50.0))
        bonus += min(3.5, max(0.0, (velocity - 50.0) * 0.1))
        franchise_pop = float(market_user.get("franchise_popularity", 0.0))
        bonus += min(4.0, franchise_pop * 0.08)
    if owned_stats:
        avg = owned_stats.avg_fmv_by_series.get(series_key)
        if avg is not None:
            bonus += min(5.0, max(0.0, (avg - 8.0) * 0.35))
        owned_count = owned_stats.copies_by_series.get(series_key, 0)
        if owned_count >= 3:
            bonus += min(2.5, 0.4 * owned_count)
    return round(bonus, 2)


def _continuity_bonus(*, owned_in_series: int, owns_run: bool) -> float:
    if owned_in_series <= 0 and not owns_run:
        return 0.0
    if owned_in_series >= 12:
        return 6.5
    if owned_in_series >= 6:
        return 5.0
    if owned_in_series >= 3:
        return 3.75
    if owns_run or owned_in_series >= 1:
        return 2.25
    return 0.0


def _confidence_from_signals(
    *,
    franchise_bonus: float,
    publisher_bonus: float,
    historical_bonus: float,
    continuity_bonus: float,
    key_signals: list[str],
    v2_confidence: float | None,
    spec_type: str | None,
    market_user: dict[str, float] | None,
) -> float:
    signal_set = {s.upper() for s in key_signals}
    base = float(v2_confidence) if v2_confidence is not None else 0.54
    base += franchise_bonus * 0.012
    base += publisher_bonus * 0.015
    base += historical_bonus * 0.018
    base += continuity_bonus * 0.02
    if signal_set.intersection(KEY_SIGNAL_TYPES):
        base += 0.06
    if spec_type == "STRONG_BUY":
        base += 0.12
    elif spec_type == "BUY":
        base += 0.08
    elif spec_type == "WATCH":
        base += 0.03
    if market_user:
        user_pref = float(market_user.get("user_preference_score", 50.0))
        base += min(0.14, max(0.0, (user_pref - 50.0) * 0.004))
    return round(max(0.38, min(0.97, base)), 3)


def build_recommendation_priority_enrichment(
    session: Session,
    *,
    owner_user_id: int,
    series_name: str,
    issue_title: str | None,
    publisher: str | None,
    key_signals: list[str],
    v2_confidence: float | None,
    spec_type: str | None,
    owns_series_run: bool,
    owned_stats: OwnedSeriesInventoryStats | None,
    scoring_ctx: RecommendationV2ScoringContext | None,
    issue_id: int,
    issue: object | None = None,
    series: object | None = None,
) -> RecommendationPriorityEnrichment:
    franchise_bonus, hits = franchise_strength_bonus(series_name=series_name, issue_title=issue_title)
    publisher_bonus = publisher_strength_bonus(publisher)
    series_key = (_normalize_publisher(publisher), _normalize_series(series_name))
    owned_in_series = owned_stats.copies_by_series.get(series_key, 0) if owned_stats else 0

    market_user: dict[str, float] | None = None
    if scoring_ctx is not None and issue is not None and series is not None:
        from app.models.release_intelligence import ReleaseIssue, ReleaseSeries

        if isinstance(issue, ReleaseIssue) and isinstance(series, ReleaseSeries):
            market_user = scoring_ctx.market_user_fit(session, issue=issue, series=series)

    historical_bonus = _historical_demand_bonus(
        series_key=series_key,
        owned_stats=owned_stats,
        market_user=market_user,
    )
    continuity_bonus = _continuity_bonus(owned_in_series=owned_in_series, owns_run=owns_series_run)

    confidence = _confidence_from_signals(
        franchise_bonus=franchise_bonus,
        publisher_bonus=publisher_bonus,
        historical_bonus=historical_bonus,
        continuity_bonus=continuity_bonus,
        key_signals=key_signals,
        v2_confidence=v2_confidence,
        spec_type=spec_type,
        market_user=market_user,
    )

    rationale: list[str] = []
    if hits:
        rationale.append(f"Franchise strength ({', '.join(hits)}).")
    if publisher_bonus >= 5.0:
        rationale.append("Core publisher catalog.")
    if historical_bonus >= 3.0:
        rationale.append("Historical series/market demand.")
    if continuity_bonus >= 2.0:
        rationale.append("Active run in your collection.")

    return RecommendationPriorityEnrichment(
        franchise_bonus=franchise_bonus,
        publisher_bonus=publisher_bonus,
        historical_demand_bonus=historical_bonus,
        continuity_bonus=continuity_bonus,
        confidence_score=confidence,
        franchise_hits=hits,
        rationale_bits=tuple(rationale),
    )


def generic_number_one_bonus(
    *,
    issue_number: str,
    key_signals: list[str],
    franchise_bonus: float,
) -> float:
    """Smaller #1 boost unless launch signals or established franchise."""
    if not _is_number_one(issue_number):
        return 0.0
    signal_set = {s.upper() for s in key_signals}
    if signal_set.intersection(NEW_ONE_SIGNALS):
        return 3.25
    if signal_set.intersection(KEY_SIGNAL_TYPES):
        return 2.0
    if franchise_bonus >= 8.0:
        return 2.5
    return 1.0
