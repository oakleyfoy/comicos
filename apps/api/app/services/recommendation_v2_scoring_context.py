"""Preloaded caches for Recommendation V2 scoring (avoids N+1 in the issue loop)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.key_issue_intelligence import KeyIssueClassification, KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_watchlist import CollectionRun, ReleaseWatchlist, ReleaseWatchlistItem
from app.models.user_preference_intelligence import UserPreferenceProfile, UserPreferenceScore
from app.services.intelligence_matching import (
    ENTITY_CHARACTER,
    ENTITY_CREATOR,
    ENTITY_FRANCHISE,
    IntelligenceMatchCatalog,
    ReleaseMatchResult,
    build_intelligence_match_catalog,
    match_release_issue,
)
from app.services.market_demand_engine import collector_demand_components
from app.services.market_user_intelligence import score_release_market_user_fit
from app.services.popularity_engine import character_score, creator_score, franchise_score
from app.services.user_preference_engine import DEFAULT_PREFERENCE_SCORE


@dataclass
class RecommendationV2ScoringContext:
    owner_user_id: int
    market_demand_profiles: tuple[MarketDemandProfile, ...]
    variants_by_issue: dict[int, list[ReleaseVariant]]
    key_profiles_by_issue: dict[int, list[KeyIssueProfile]]
    classifications_by_issue: dict[int, str]
    signals_by_issue: dict[int, list[ReleaseKeySignal]]
    collection_run_series: frozenset[str]
    watchlist_series: frozenset[str]
    user_pref_profiles: tuple[UserPreferenceProfile, ...]
    user_pref_score_by_profile: dict[int, float]
    match_catalog: IntelligenceMatchCatalog
    _popularity_cache: dict[tuple[str, int], float] = field(default_factory=dict)
    _match_cache: dict[tuple[int, int | None], ReleaseMatchResult] = field(default_factory=dict)
    _market_user_fit_cache: dict[int, dict[str, float]] = field(default_factory=dict)
    _collector_demand_cache: dict[str, dict[str, float]] = field(default_factory=dict)

    def popularity_score(self, session: Session, *, entity_type: str, entity_id: int) -> float:
        key = (entity_type, entity_id)
        cached = self._popularity_cache.get(key)
        if cached is not None:
            return cached
        if entity_type == ENTITY_CHARACTER:
            value = character_score(session, character_id=entity_id)
        elif entity_type == ENTITY_FRANCHISE:
            value = franchise_score(session, franchise_id=entity_id)
        elif entity_type == ENTITY_CREATOR:
            value = creator_score(session, creator_id=entity_id)
        else:
            value = 0.0
        self._popularity_cache[key] = value
        return value

    def _popularity_fn(self, session: Session) -> Callable[[str, int], float]:
        ctx = self

        def _fn(entity_type: str, entity_id: int) -> float:
            return ctx.popularity_score(session, entity_type=entity_type, entity_id=entity_id)

        return _fn

    def match_release(
        self,
        session: Session,
        *,
        issue: ReleaseIssue,
        series: ReleaseSeries,
        variant: ReleaseVariant | None = None,
    ) -> ReleaseMatchResult:
        variant_id = int(variant.id) if variant and variant.id else None
        cache_key = (int(issue.id or 0), variant_id)
        cached = self._match_cache.get(cache_key)
        if cached is not None:
            return cached
        result = match_release_issue(
            session,
            issue=issue,
            series=series,
            variant=variant,
            catalog=self.match_catalog,
            popularity_fn=self._popularity_fn(session),
        )
        self._match_cache[cache_key] = result
        return result

    def variants_for(self, issue_id: int) -> list[ReleaseVariant]:
        return self.variants_by_issue.get(issue_id, [])

    def key_profiles_for(self, issue_id: int) -> list[KeyIssueProfile]:
        return self.key_profiles_by_issue.get(issue_id, [])

    def classification_for(self, issue_id: int) -> str | None:
        return self.classifications_by_issue.get(issue_id)

    def signals_for(self, issue_id: int) -> list[ReleaseKeySignal]:
        return self.signals_by_issue.get(issue_id, [])

    def market_demand_best_for_blob(self, blob: str) -> float:
        lowered = blob.lower()
        best = 50.0
        for profile in self.market_demand_profiles:
            name = profile.entity_name.lower()
            if name in lowered or lowered in name:
                best = max(best, float(profile.demand_score))
        return best

    def user_preference_best_for_text(self, text: str) -> float:
        lowered = text.lower()
        best = DEFAULT_PREFERENCE_SCORE
        for profile in self.user_pref_profiles:
            label = profile.preference_label.lower()
            if label in lowered or profile.preference_key.replace("-", " ") in lowered:
                pid = int(profile.id or 0)
                if pid in self.user_pref_score_by_profile:
                    best = max(best, self.user_pref_score_by_profile[pid])
        return best

    def collector_demand(self, session: Session, *, entity_name: str) -> dict[str, float]:
        key = entity_name.lower()
        cached = self._collector_demand_cache.get(key)
        if cached is not None:
            return cached
        payload = collector_demand_components(session, entity_type="FRANCHISE", entity_name=entity_name)
        self._collector_demand_cache[key] = payload
        return payload

    def market_user_fit(
        self,
        session: Session,
        *,
        issue: ReleaseIssue,
        series: ReleaseSeries,
    ) -> dict[str, float]:
        issue_id = int(issue.id or 0)
        cached = self._market_user_fit_cache.get(issue_id)
        if cached is not None:
            return cached
        match = self.match_release(session, issue=issue, series=series)
        char = 0.0
        franchise = 0.0
        creator = 0.0
        for entity in match.matched_entities:
            score = self.popularity_score(session, entity_type=entity.entity_type, entity_id=entity.entity_id)
            if entity.entity_type == ENTITY_CHARACTER:
                char = max(char, score)
            elif entity.entity_type == ENTITY_FRANCHISE:
                franchise = max(franchise, score)
            elif entity.entity_type == ENTITY_CREATOR:
                creator = max(creator, score)
        key_profiles = self.key_profiles_for(issue_id)
        key_score = 50.0
        if key_profiles:
            from app.services.key_issue_scoring import score_key_issue_profile

            for profile in key_profiles:
                breakdown = score_key_issue_profile(session, profile=profile, issue=issue, series=series)
                key_score = max(key_score, float(breakdown.overall_key_issue_score))

        market_text = f"{series.series_name} {series.publisher} {issue.title}"
        market = self.market_demand_best_for_blob(market_text)
        user = self.user_preference_best_for_text(market_text)
        popularity = match.combined_popularity_score
        combined = round(popularity * 0.2 + key_score * 0.2 + market * 0.35 + user * 0.25, 2)
        components = self.collector_demand(session, entity_name=series.series_name)
        payload = {
            "combined_market_user_score": combined,
            "character_popularity": char,
            "franchise_popularity": franchise,
            "creator_popularity": creator,
            "key_issue_score": key_score,
            "market_demand_score": market,
            "user_preference_score": user,
            **components,
        }
        self._market_user_fit_cache[issue_id] = payload
        return payload


def build_recommendation_v2_scoring_context(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: list[int],
) -> RecommendationV2ScoringContext:
    issue_id_set = sorted({iid for iid in issue_ids if iid > 0})

    variants_by_issue: dict[int, list[ReleaseVariant]] = {}
    if issue_id_set:
        for variant in session.exec(
            select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_id_set))
        ).all():
            variants_by_issue.setdefault(int(variant.issue_id), []).append(variant)

    key_profiles_by_issue: dict[int, list[KeyIssueProfile]] = {}
    classifications_by_issue: dict[int, str] = {}
    if issue_id_set:
        for profile in session.exec(
            select(KeyIssueProfile).where(KeyIssueProfile.release_issue_id.in_(issue_id_set))
        ).all():
            key_profiles_by_issue.setdefault(int(profile.release_issue_id), []).append(profile)
        for row in session.exec(
            select(KeyIssueClassification).where(KeyIssueClassification.release_issue_id.in_(issue_id_set))
        ).all():
            classifications_by_issue[int(row.release_issue_id)] = row.classification

    signals_by_issue: dict[int, list[ReleaseKeySignal]] = {}
    if issue_id_set:
        for signal in session.exec(
            select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id.in_(issue_id_set))
        ).all():
            signals_by_issue.setdefault(int(signal.issue_id), []).append(signal)

    market_profiles = tuple(session.exec(select(MarketDemandProfile)).all())

    user_pref_profiles = tuple(
        session.exec(
            select(UserPreferenceProfile).where(
                UserPreferenceProfile.owner_user_id == owner_user_id,
                UserPreferenceProfile.status == "ACTIVE",
            )
        ).all()
    )
    profile_ids = [int(p.id or 0) for p in user_pref_profiles if p.id is not None]
    user_pref_score_by_profile: dict[int, float] = {}
    if profile_ids:
        score_rows = session.exec(
            select(UserPreferenceScore)
            .where(UserPreferenceScore.preference_profile_id.in_(profile_ids))
            .order_by(UserPreferenceScore.id.desc())
        ).all()
        for row in score_rows:
            pid = int(row.preference_profile_id)
            if pid not in user_pref_score_by_profile:
                user_pref_score_by_profile[pid] = float(row.preference_score)

    run_series = frozenset(
        run.series_name.lower()
        for run in session.exec(
            select(CollectionRun).where(CollectionRun.owner_user_id == owner_user_id)
        ).all()
        if run.series_name
    )
    watchlists = session.exec(
        select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
    ).all()
    watchlist_ids = [int(w.id or 0) for w in watchlists if w.id is not None]
    watchlist_series: set[str] = set()
    if watchlist_ids:
        for item in session.exec(
            select(ReleaseWatchlistItem).where(ReleaseWatchlistItem.watchlist_id.in_(watchlist_ids))
        ).all():
            if item.series_name:
                watchlist_series.add(item.series_name.lower())

    return RecommendationV2ScoringContext(
        owner_user_id=owner_user_id,
        market_demand_profiles=market_profiles,
        variants_by_issue=variants_by_issue,
        key_profiles_by_issue=key_profiles_by_issue,
        classifications_by_issue=classifications_by_issue,
        signals_by_issue=signals_by_issue,
        collection_run_series=run_series,
        watchlist_series=frozenset(watchlist_series),
        user_pref_profiles=user_pref_profiles,
        user_pref_score_by_profile=user_pref_score_by_profile,
        match_catalog=build_intelligence_match_catalog(session),
    )
