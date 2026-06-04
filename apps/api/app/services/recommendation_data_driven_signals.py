"""Registry- and owner-data-driven recommendation signals (no hardcoded franchise/publisher winners)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.intelligence_matching import match_release_issue
from app.services.popularity_engine import character_score, franchise_score
_KEY_SIGNAL_TYPES = frozenset(
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

_POPULARITY_FRANCHISE_THRESHOLD = 65.0
_MARKET_DEMAND_NAME_THRESHOLD = 72.0
_MAX_FRANCHISE_BONUS = 14.0


def _text_blob(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).lower()


def franchise_demand_bonus(
    session: Session,
    *,
    series_name: str,
    issue_title: str | None = None,
    issue: ReleaseIssue | None = None,
    series: ReleaseSeries | None = None,
    key_signals: list[str] | None = None,
    scoring_ctx=None,
) -> tuple[float, tuple[str, ...]]:
    """Franchise/character strength from intelligence registry + market demand profiles only."""
    hits: list[str] = []
    bonus = 0.0
    signal_set = {s.upper() for s in (key_signals or [])}

    if issue is not None and series is not None:
        if scoring_ctx is not None:
            match = scoring_ctx.match_release(session, issue=issue, series=series)
        else:
            match = match_release_issue(session, issue=issue, series=series)
        for entity in match.matched_entities:
            if entity.entity_type == "FRANCHISE":
                score = (
                    scoring_ctx.popularity_score(session, entity_type="FRANCHISE", entity_id=entity.entity_id)
                    if scoring_ctx is not None
                    else franchise_score(session, franchise_id=entity.entity_id)
                )
                if score >= _POPULARITY_FRANCHISE_THRESHOLD:
                    hits.append(entity.entity_name)
                    bonus = max(bonus, min(_MAX_FRANCHISE_BONUS, 4.0 + (score - _POPULARITY_FRANCHISE_THRESHOLD) * 0.12))
            elif entity.entity_type == "CHARACTER":
                score = (
                    scoring_ctx.popularity_score(session, entity_type="CHARACTER", entity_id=entity.entity_id)
                    if scoring_ctx is not None
                    else character_score(session, character_id=entity.entity_id)
                )
                if score >= _POPULARITY_FRANCHISE_THRESHOLD:
                    hits.append(entity.entity_name)
                    bonus = max(bonus, min(_MAX_FRANCHISE_BONUS, 3.5 + (score - _POPULARITY_FRANCHISE_THRESHOLD) * 0.1))

    blob = _text_blob(series_name, issue_title, series.publisher if series else None)
    for profile in session.exec(select(MarketDemandProfile)).all():
        name = (getattr(profile, "entity_name", None) or "").strip().lower()
        if not name or len(name) < 3:
            continue
        demand = float(getattr(profile, "demand_score", 0.0) or 0.0)
        if demand < _MARKET_DEMAND_NAME_THRESHOLD:
            continue
        if name in blob:
            hits.append(profile.entity_name)
            tier = min(10.0, (demand - 50.0) * 0.15)
            bonus = max(bonus, tier)

    if signal_set.intersection({"FIRST_APPEARANCE", "FIRST_FULL_APPEARANCE", "FIRST_CAMEO", "ORIGIN"}):
        bonus = max(bonus, 4.0)
    if signal_set.intersection({"UNIVERSE_LAUNCH", "RELAUNCH", "NEW_NUMBER_ONE"}):
        bonus = max(bonus, 3.5)
    if signal_set.intersection(_KEY_SIGNAL_TYPES):
        bonus = max(bonus, 2.0)

    return round(min(_MAX_FRANCHISE_BONUS, bonus), 2), tuple(dict.fromkeys(hits))


def publisher_engagement_bonus(
    *,
    publisher: str | None,
    owned_stats: object | None,
) -> float:
    """Publisher boost from owner inventory engagement only (not publisher brand lists)."""
    if owned_stats is None or not publisher:
        return 0.0
    copies_by = getattr(owned_stats, "copies_by_series", None)
    if not copies_by:
        return 0.0
    pub = (publisher or "").strip().lower()
    if not pub:
        return 0.0
    copies = sum(
        count
        for (p, _series), count in copies_by.items()
        if p == pub or pub in p or p in pub
    )
    if copies <= 0:
        return 0.0
    series_count = len([k for k in copies_by if k[0] == pub])
    return round(min(6.0, 0.35 * copies + min(2.0, series_count * 0.5)), 2)


def _normalize_publisher(value: str | None) -> str:
    return (value or "").strip().lower()
