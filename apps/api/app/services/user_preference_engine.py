from __future__ import annotations

import re

from sqlmodel import Session, select

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Order, Variant
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.release_watchlist import ReleaseWatchlist, ReleaseWatchlistItem
from app.models.spec_intelligence import SpecRecommendation, SpecRecommendationReview
from app.models.user_preference_intelligence import (
    UserPreferenceProfile,
    UserPreferenceScore,
    UserPreferenceSignal,
)
DEFAULT_PREFERENCE_SCORE = 50.0
DEFAULT_CONFIDENCE = 0.25


def _normalize_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "unknown"


def _get_or_create_profile(
    session: Session,
    *,
    owner_user_id: int,
    preference_type: str,
    preference_key: str,
    preference_label: str,
) -> UserPreferenceProfile:
    row = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.owner_user_id == owner_user_id,
            UserPreferenceProfile.preference_type == preference_type,
            UserPreferenceProfile.preference_key == preference_key,
        )
    ).first()
    if row:
        if row.status == "DISABLED":
            row.status = "ACTIVE"
            row.preference_label = preference_label
            session.add(row)
        return row
    profile = UserPreferenceProfile(
        owner_user_id=owner_user_id,
        preference_type=preference_type,
        preference_key=preference_key,
        preference_label=preference_label,
        status="ACTIVE",
    )
    session.add(profile)
    session.flush()
    return profile


def _record_signal(
    session: Session,
    *,
    owner_user_id: int,
    profile_id: int,
    signal_type: str,
    strength: float,
    source_type: str,
) -> None:
    session.add(
        UserPreferenceSignal(
            owner_user_id=owner_user_id,
            preference_profile_id=profile_id,
            signal_type=signal_type,
            signal_strength=round(strength, 2),
            source_type=source_type,
        )
    )


def _record_score(
    session: Session,
    *,
    owner_user_id: int,
    profile: UserPreferenceProfile,
    score: float,
    confidence: float,
) -> None:
    session.add(
        UserPreferenceScore(
            owner_user_id=owner_user_id,
            preference_profile_id=int(profile.id or 0),
            preference_score=round(min(max(score, 0.0), 100.0), 2),
            confidence_score=round(min(max(confidence, 0.0), 1.0), 3),
        )
    )


def safe_default_preferences() -> list[dict[str, object]]:
    return [
        {
            "preference_type": "FRANCHISE",
            "preference_key": "neutral",
            "preference_label": "Neutral collector profile",
            "preference_score": DEFAULT_PREFERENCE_SCORE,
            "confidence_score": DEFAULT_CONFIDENCE,
            "status": "DEFAULT",
        }
    ]


def create_manual_preference(
    session: Session,
    *,
    owner_user_id: int,
    preference_type: str,
    preference_label: str,
    preference_score: float | None = None,
) -> UserPreferenceProfile:
    key = _normalize_key(preference_label)
    profile = _get_or_create_profile(
        session,
        owner_user_id=owner_user_id,
        preference_type=preference_type,
        preference_key=key,
        preference_label=preference_label.strip(),
    )
    score = preference_score if preference_score is not None else 75.0
    _record_signal(
        session,
        owner_user_id=owner_user_id,
        profile_id=int(profile.id or 0),
        signal_type="MANUAL_SET",
        strength=score,
        source_type="MANUAL",
    )
    _record_score(session, owner_user_id=owner_user_id, profile=profile, score=score, confidence=0.9)
    session.commit()
    session.refresh(profile)
    return profile


def disable_manual_preference(session: Session, *, owner_user_id: int, profile_id: int) -> UserPreferenceProfile:
    profile = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.id == profile_id,
            UserPreferenceProfile.owner_user_id == owner_user_id,
        )
    ).one()
    profile.status = "DISABLED"
    session.add(profile)
    _record_signal(
        session,
        owner_user_id=owner_user_id,
        profile_id=int(profile.id or 0),
        signal_type="MANUAL_DISABLED",
        strength=0.0,
        source_type="MANUAL",
    )
    session.commit()
    session.refresh(profile)
    return profile


def _infer_from_watchlists(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], float]:
    weights: dict[tuple[str, str], float] = {}
    watchlists = session.exec(select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)).all()
    ids = [int(w.id or 0) for w in watchlists]
    if not ids:
        return weights
    items = session.exec(select(ReleaseWatchlistItem).where(ReleaseWatchlistItem.watchlist_id.in_(ids))).all()
    for item in items:
        if item.series_name:
            key = ("SERIES", _normalize_key(item.series_name))
            weights[key] = weights.get(key, 0.0) + 12.0
        if item.character_name:
            key = ("CHARACTER", _normalize_key(item.character_name))
            weights[key] = weights.get(key, 0.0) + 15.0
        if item.publisher:
            key = ("PUBLISHER", _normalize_key(item.publisher))
            weights[key] = weights.get(key, 0.0) + 8.0
        if item.creator_name:
            key = ("CREATOR", _normalize_key(item.creator_name))
            weights[key] = weights.get(key, 0.0) + 10.0
    return weights


def _infer_from_inventory(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], float]:
    weights: dict[tuple[str, str], float] = {}
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    for copy in copies:
        variant = session.get(Variant, copy.variant_id)
        if not variant:
            continue
        issue = session.get(ComicIssue, variant.comic_issue_id)
        if not issue:
            continue
        title = session.get(ComicTitle, issue.comic_title_id)
        if title:
            key = ("SERIES", _normalize_key(title.name))
            weights[key] = weights.get(key, 0.0) + 6.0
        if variant.ratio:
            key = ("VARIANT_TYPE", "ratio-variant")
            weights[key] = weights.get(key, 0.0) + 10.0
        if variant.variant_type and "ratio" in variant.variant_type.lower():
            key = ("VARIANT_TYPE", "ratio-variant")
            weights[key] = weights.get(key, 0.0) + 10.0
    return weights


def _infer_from_orders(session: Session, *, owner_user_id: int) -> float:
    count = len(session.exec(select(Order).where(Order.user_id == owner_user_id)).all())
    return min(count * 2.0, 20.0)


def _infer_from_reviews(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], float]:
    weights: dict[tuple[str, str], float] = {}
    rows = session.exec(
        select(SpecRecommendationReview, SpecRecommendation, ReleaseIssue, ReleaseSeries)
        .join(SpecRecommendation, SpecRecommendationReview.recommendation_id == SpecRecommendation.id)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(SpecRecommendationReview.review_status == "ACCEPTED")
    ).all()
    for _review, rec, issue, series in rows:
        weights[("SERIES", _normalize_key(series.series_name))] = (
            weights.get(("SERIES", _normalize_key(series.series_name)), 0.0) + 14.0
        )
        if rec.recommendation_type == "IMAGE_LAUNCH" or "image" in series.publisher.lower():
            weights[("PUBLISHER", "image")] = weights.get(("PUBLISHER", "image"), 0.0) + 12.0
        if issue.issue_number in {"1", "001"}:
            weights[("KEY_ISSUE_TYPE", "first-appearance")] = (
                weights.get(("KEY_ISSUE_TYPE", "first-appearance"), 0.0) + 10.0
            )
    return weights


def refresh_user_preferences(session: Session, *, owner_user_id: int) -> dict[str, int]:
    combined: dict[tuple[str, str, str], float] = {}
    order_bonus = _infer_from_orders(session, owner_user_id=owner_user_id)

    def merge(source: dict[tuple[str, str], float], source_type: str) -> None:
        for (pref_type, pref_key), strength in source.items():
            label = pref_key.replace("-", " ").title()
            combined[(pref_type, pref_key, label)] = combined.get((pref_type, pref_key, label), 0.0) + strength

    merge(_infer_from_watchlists(session, owner_user_id=owner_user_id), "WATCHLIST")
    merge(_infer_from_inventory(session, owner_user_id=owner_user_id), "INVENTORY")

    purchase_weights = _infer_from_reviews(session, owner_user_id=owner_user_id)
    merge(purchase_weights, "RECOMMENDATION_REVIEW")

    profiles_touched = 0
    signals_added = 0

    if not combined and order_bonus == 0.0:
        existing = session.exec(
            select(UserPreferenceProfile).where(
                UserPreferenceProfile.owner_user_id == owner_user_id,
                UserPreferenceProfile.status == "ACTIVE",
            )
        ).first()
        if not existing:
            return {"profiles_updated": 0, "signals_added": 0, "used_defaults": 1}

    for (pref_type, pref_key, label), strength in combined.items():
        profile = _get_or_create_profile(
            session,
            owner_user_id=owner_user_id,
            preference_type=pref_type,
            preference_key=pref_key,
            preference_label=label,
        )
        score = DEFAULT_PREFERENCE_SCORE + strength + order_bonus
        confidence = 0.35 + min(strength / 100.0, 0.45)
        source = "WATCHLIST" if strength >= 12 else "INVENTORY"
        if pref_type == "KEY_ISSUE_TYPE":
            source = "RECOMMENDATION_REVIEW"
        _record_signal(
            session,
            owner_user_id=owner_user_id,
            profile_id=int(profile.id or 0),
            signal_type="INFERRED",
            strength=strength,
            source_type=source,
        )
        _record_score(session, owner_user_id=owner_user_id, profile=profile, score=score, confidence=confidence)
        profiles_touched += 1
        signals_added += 1

    manual_profiles = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.owner_user_id == owner_user_id,
            UserPreferenceProfile.status == "ACTIVE",
        )
    ).all()
    for profile in manual_profiles:
        latest = session.exec(
            select(UserPreferenceScore)
            .where(UserPreferenceScore.preference_profile_id == profile.id)
            .order_by(UserPreferenceScore.id.desc())
        ).first()
        if latest:
            continue
        _record_score(
            session,
            owner_user_id=owner_user_id,
            profile=profile,
            score=75.0,
            confidence=0.85,
        )
        profiles_touched += 1

    session.commit()
    return {
        "profiles_updated": profiles_touched,
        "signals_added": signals_added,
        "used_defaults": 0 if combined or order_bonus else 0,
    }


def latest_user_preference_score(
    session: Session,
    *,
    owner_user_id: int,
    preference_type: str,
    preference_key: str,
) -> float:
    profile = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.owner_user_id == owner_user_id,
            UserPreferenceProfile.preference_type == preference_type,
            UserPreferenceProfile.preference_key == preference_key,
            UserPreferenceProfile.status == "ACTIVE",
        )
    ).first()
    if not profile:
        return DEFAULT_PREFERENCE_SCORE
    row = session.exec(
        select(UserPreferenceScore)
        .where(UserPreferenceScore.preference_profile_id == profile.id)
        .order_by(UserPreferenceScore.id.desc())
    ).first()
    return float(row.preference_score) if row else DEFAULT_PREFERENCE_SCORE
