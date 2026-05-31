from __future__ import annotations

from sqlmodel import Session, select

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.user_preference_intelligence import UserPreferenceProfile, UserPreferenceScore
from app.services.intelligence_matching import match_release_issue
from app.services.key_issue_scoring import score_key_issue_profile
from app.services.market_demand_engine import collector_demand_components, market_demand_score
from app.services.popularity_engine import (
    character_score,
    combined_popularity_score,
    creator_score,
    franchise_score,
)
from app.services.user_preference_engine import DEFAULT_PREFERENCE_SCORE, latest_user_preference_score


def _match_market_demand_for_text(session: Session, text: str) -> float:
    lowered = text.lower()
    best = 50.0
    for profile in session.exec(select(MarketDemandProfile)).all():
        name = profile.entity_name.lower()
        if name in lowered or lowered in name:
            best = max(best, float(profile.demand_score))
    return best


def _user_preference_for_text(session: Session, *, owner_user_id: int, text: str) -> float:
    lowered = text.lower()
    best = DEFAULT_PREFERENCE_SCORE
    profiles = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.owner_user_id == owner_user_id,
            UserPreferenceProfile.status == "ACTIVE",
        )
    ).all()
    for profile in profiles:
        label = profile.preference_label.lower()
        if label in lowered or profile.preference_key.replace("-", " ") in lowered:
            row = session.exec(
                select(UserPreferenceScore)
                .where(UserPreferenceScore.preference_profile_id == profile.id)
                .order_by(UserPreferenceScore.id.desc())
            ).first()
            if row:
                best = max(best, float(row.preference_score))
    return best


def combined_market_user_score(
    session: Session,
    *,
    owner_user_id: int,
    entity_type: str,
    entity_name: str,
) -> float:
    market = market_demand_score(session, entity_type=entity_type, entity_name=entity_name)
    user = latest_user_preference_score(
        session,
        owner_user_id=owner_user_id,
        preference_type=entity_type if entity_type in {"CHARACTER", "FRANCHISE", "CREATOR", "PUBLISHER", "SERIES"} else "FRANCHISE",
        preference_key=entity_name.lower().replace(" ", "-"),
    )
    if user == DEFAULT_PREFERENCE_SCORE:
        user = _user_preference_for_text(session, owner_user_id=owner_user_id, text=entity_name)
    return round((market * 0.55) + (user * 0.45), 2)


def score_release_market_user_fit(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> dict[str, float]:
    match = match_release_issue(session, issue=issue, series=series)
    char = 0.0
    franchise = 0.0
    creator = 0.0
    for entity in match.matched_entities:
        if entity.entity_type == "CHARACTER":
            char = max(char, character_score(session, character_id=entity.entity_id))
        elif entity.entity_type == "FRANCHISE":
            franchise = max(franchise, franchise_score(session, franchise_id=entity.entity_id))
        elif entity.entity_type == "CREATOR":
            creator = max(creator, creator_score(session, creator_id=entity.entity_id))
    popularity = match.combined_popularity_score or combined_popularity_score(
        character=char, franchise=franchise, creator=creator
    )

    key_row = session.exec(
        select(KeyIssueProfile).where(KeyIssueProfile.release_issue_id == issue.id)
    ).first()
    key_score = 50.0
    if key_row:
        breakdown = score_key_issue_profile(session, profile=key_row, issue=issue, series=series)
        key_score = float(breakdown.overall_key_issue_score)

    market_text = f"{series.series_name} {series.publisher} {issue.title}"
    market = _match_market_demand_for_text(session, market_text)
    user = _user_preference_for_text(session, owner_user_id=owner_user_id, text=market_text)

    combined = round(
        popularity * 0.2 + key_score * 0.2 + market * 0.35 + user * 0.25,
        2,
    )
    components = collector_demand_components(session, entity_type="FRANCHISE", entity_name=series.series_name)
    return {
        "combined_market_user_score": combined,
        "character_popularity": char,
        "franchise_popularity": franchise,
        "creator_popularity": creator,
        "key_issue_score": key_score,
        "market_demand_score": market,
        "user_preference_score": user,
        **components,
    }
