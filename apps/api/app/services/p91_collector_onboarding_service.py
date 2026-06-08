"""P91-01 collector onboarding wizard persistence and catalog search."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.asset_ledger import Publisher
from app.models.character_intelligence import CharacterProfile
from app.models.creator_intelligence import CreatorProfile
from app.models.p77_collector_profile import P77CollectorProfile
from app.schemas.p91_collector_onboarding import (
    P91InterestOptionListResponse,
    P91InterestOptionRead,
    P91OnboardingDraft,
    P91OnboardingStatusRead,
    P91RecommendationPreviewItem,
    P91RecommendationPreviewRead,
)
from app.schemas.p77_collector_profile import P77CollectorProfileUpdate, P77InterestItemWrite
from app.services.p77_collector_profile_service import get_collector_profile, update_collector_profile

POPULAR_PUBLISHERS = (
    "Marvel",
    "DC",
    "Image",
    "Dark Horse",
    "Boom",
    "IDW",
    "Dynamite",
    "Titan",
    "AWA",
)

POPULAR_CHARACTERS = (
    "Batman",
    "Spider-Man",
    "Wolverine",
    "Venom",
    "Deadpool",
    "Superman",
    "Nightwing",
    "Daredevil",
    "X-Men",
)

POPULAR_CREATORS = (
    "Todd McFarlane",
    "Jim Lee",
    "Scott Snyder",
    "Jonathan Hickman",
    "Frank Miller",
    "Jeph Loeb",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_profile(session: Session, *, owner_user_id: int) -> P77CollectorProfile:
    row = session.exec(select(P77CollectorProfile).where(P77CollectorProfile.owner_user_id == owner_user_id)).first()
    if row is not None:
        return row
    row = P77CollectorProfile(owner_user_id=owner_user_id)
    session.add(row)
    session.flush()
    return row


def _draft_from_json(raw: dict | None) -> P91OnboardingDraft:
    if not raw:
        return P91OnboardingDraft()
    try:
        return P91OnboardingDraft.model_validate(raw)
    except Exception:
        return P91OnboardingDraft()


def _draft_to_json(draft: P91OnboardingDraft) -> dict:
    return draft.model_dump(mode="json")


def _popular_rank(label: str, popular: tuple[str, ...]) -> int:
    key = label.strip().casefold()
    for index, name in enumerate(popular):
        if name.casefold() == key:
            return index
    return len(popular) + 1000


def _sort_by_popular_then_name(items: list[P91InterestOptionRead], popular: tuple[str, ...]) -> list[P91InterestOptionRead]:
    return sorted(items, key=lambda row: (_popular_rank(row.label, popular), row.label.casefold()))


def get_onboarding_status(session: Session, *, owner_user_id: int) -> P91OnboardingStatusRead:
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    completed = profile.onboarding_completed_at is not None
    draft = _draft_from_json(profile.onboarding_draft_json)
    if completed and draft.step < 7:
        draft = draft.model_copy(update={"step": 7})
    return P91OnboardingStatusRead(
        onboarding_completed=completed,
        onboarding_completed_at=profile.onboarding_completed_at,
        draft=draft,
    )


def _dedupe_labels(labels: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for label in labels:
        text = label.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


_COLLECTOR_TYPES = {"INVESTOR", "SPECULATOR", "COMPLETIONIST", "READER", "HYBRID"}
_RISK_PROFILES = {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"}
_TIME_HORIZONS = {"SHORT_TERM_FLIP", "MEDIUM_TERM", "LONG_TERM", "LEGACY_COLLECTION", "MIXED"}


def normalize_onboarding_draft(draft: P91OnboardingDraft) -> P91OnboardingDraft:
    collector_type = draft.collector_type if draft.collector_type in _COLLECTOR_TYPES else None
    risk_profile = draft.risk_profile if draft.risk_profile in _RISK_PROFILES else None
    time_horizon = draft.time_horizon if draft.time_horizon in _TIME_HORIZONS else None
    return draft.model_copy(
        update={
            "step": max(1, min(int(draft.step), 99)),
            "collector_type": collector_type,
            "risk_profile": risk_profile,
            "time_horizon": time_horizon,
            "publisher_labels": _dedupe_labels(draft.publisher_labels),
            "character_labels": _dedupe_labels(draft.character_labels),
            "creator_labels": _dedupe_labels(draft.creator_labels),
        }
    )


def save_onboarding_draft(session: Session, *, owner_user_id: int, draft: P91OnboardingDraft) -> P91OnboardingStatusRead:
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    normalized = normalize_onboarding_draft(draft)
    profile.onboarding_draft_json = _draft_to_json(normalized)
    profile.updated_at = _utc_now()
    session.add(profile)
    session.flush()
    return get_onboarding_status(session, owner_user_id=owner_user_id)


def _labels_to_interest_writes(labels: list[str], *, interest_type: str) -> list[P77InterestItemWrite]:
    items: list[P77InterestItemWrite] = []
    for index, label in enumerate(labels):
        text = label.strip()
        if not text:
            continue
        items.append(
            P77InterestItemWrite(
                interest_type=interest_type,  # type: ignore[arg-type]
                label=text,
                priority_rank=index + 1,
            )
        )
    return items


def complete_onboarding(
    session: Session,
    *,
    owner_user_id: int,
    draft: P91OnboardingDraft | None,
) -> P91OnboardingStatusRead:
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    effective = normalize_onboarding_draft(draft or _draft_from_json(profile.onboarding_draft_json))

    update_payload = P77CollectorProfileUpdate(
        collector_type=effective.collector_type or "HYBRID",  # type: ignore[arg-type]
        risk_profile=effective.risk_profile or "MODERATE",  # type: ignore[arg-type]
        time_horizon=effective.time_horizon or "LONG_TERM",  # type: ignore[arg-type]
        publishers=_labels_to_interest_writes(effective.publisher_labels, interest_type="PUBLISHER"),
        characters=_labels_to_interest_writes(effective.character_labels, interest_type="CHARACTER"),
        creators=_labels_to_interest_writes(effective.creator_labels, interest_type="CREATOR"),
    )
    update_collector_profile(session, owner_user_id=owner_user_id, payload=update_payload)

    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    profile.onboarding_completed_at = _utc_now()
    profile.onboarding_draft_json = _draft_to_json(effective.model_copy(update={"step": 7}))
    profile.updated_at = _utc_now()
    session.add(profile)
    session.flush()
    return get_onboarding_status(session, owner_user_id=owner_user_id)


def search_interest_options(
    session: Session,
    *,
    kind: str,
    query: str = "",
    limit: int = 40,
    offset: int = 0,
) -> P91InterestOptionListResponse:
    lim = max(1, min(limit, 100))
    off = max(0, offset)
    q = query.strip()
    q_fold = q.casefold()

    items: list[P91InterestOptionRead] = []

    if kind == "PUBLISHER":
        stmt = select(Publisher.name, Publisher.id).distinct()
        if q:
            stmt = stmt.where(func.lower(Publisher.name).contains(q_fold))
        rows = session.exec(stmt.order_by(Publisher.name.asc()).limit(lim + off + 200)).all()
        seen: set[str] = set()
        for name, pub_id in rows:
            label = str(name or "").strip()
            if not label:
                continue
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(P91InterestOptionRead(label=label, source_id=int(pub_id) if pub_id else None))
        items = _sort_by_popular_then_name(items, POPULAR_PUBLISHERS)

    elif kind == "CHARACTER":
        stmt = select(CharacterProfile).where(CharacterProfile.status == "ACTIVE")
        if q:
            stmt = stmt.where(func.lower(CharacterProfile.character_name).contains(q_fold))
        rows = session.exec(stmt.order_by(CharacterProfile.character_name.asc()).limit(lim + off + 400)).all()
        seen_char: set[str] = set()
        for row in rows:
            label = row.character_name.strip()
            if not label:
                continue
            key = label.casefold()
            if key in seen_char:
                continue
            seen_char.add(key)
            subtitle = row.publisher.strip() or None
            items.append(
                P91InterestOptionRead(label=label, subtitle=subtitle, source_id=int(row.id) if row.id else None)
            )
        items = _sort_by_popular_then_name(items, POPULAR_CHARACTERS)

    elif kind == "CREATOR":
        stmt = select(CreatorProfile.creator_name, func.min(CreatorProfile.id)).where(CreatorProfile.status == "ACTIVE")
        if q:
            stmt = stmt.where(func.lower(CreatorProfile.creator_name).contains(q_fold))
        stmt = stmt.group_by(CreatorProfile.creator_name).order_by(CreatorProfile.creator_name.asc())
        rows = session.exec(stmt.limit(lim + off + 400)).all()
        for name, creator_id in rows:
            label = str(name or "").strip()
            if not label:
                continue
            items.append(P91InterestOptionRead(label=label, source_id=int(creator_id) if creator_id else None))
        items = _sort_by_popular_then_name(items, POPULAR_CREATORS)

    total = len(items)
    page = items[off : off + lim]
    return P91InterestOptionListResponse(items=page, total_items=total, limit=lim, offset=off, query=q)


def build_recommendation_preview(draft: P91OnboardingDraft) -> P91RecommendationPreviewRead:
    collector = draft.collector_type or "HYBRID"
    risk = draft.risk_profile or "MODERATE"
    horizon = draft.time_horizon or "LONG_TERM"

    risk_label = {"CONSERVATIVE": "Conservative", "MODERATE": "Balanced", "AGGRESSIVE": "Aggressive"}.get(
        risk, risk.replace("_", " ").title()
    )
    horizon_label = {
        "SHORT_TERM_FLIP": "Short-Term",
        "MEDIUM_TERM": "Medium-Term",
        "LONG_TERM": "Long-Term",
        "LEGACY_COLLECTION": "Legacy",
        "MIXED": "Mixed",
    }.get(horizon, horizon.replace("_", " ").title())
    collector_label = collector.replace("_", " ").title()

    summary: dict[str, str | list[str]] = {
        "Collector Type": collector_label,
        "Risk": risk_label,
        "Time Horizon": horizon_label,
        "Publishers": draft.publisher_labels or [],
        "Characters": draft.character_labels or [],
        "Creators": draft.creator_labels or [],
    }

    priorities: list[P91RecommendationPreviewItem] = []

    if draft.collector_type in {"INVESTOR", "HYBRID", "SPECULATOR"}:
        priorities.append(P91RecommendationPreviewItem(text="Key appearances"))
    if draft.collector_type in {"COMPLETIONIST", "HYBRID"}:
        priorities.append(P91RecommendationPreviewItem(text="Run completion opportunities"))
    if draft.collector_type in {"READER", "HYBRID"}:
        priorities.append(P91RecommendationPreviewItem(text="Story-driven reading picks"))

    for character in draft.character_labels[:4]:
        priorities.append(P91RecommendationPreviewItem(text=f"{character} recommendations"))

    if draft.risk_profile == "CONSERVATIVE":
        priorities.append(P91RecommendationPreviewItem(text="Established blue-chip keys"))
    elif draft.risk_profile == "AGGRESSIVE":
        priorities.append(P91RecommendationPreviewItem(text="High-upside speculative releases"))
    else:
        priorities.append(P91RecommendationPreviewItem(text="Balanced mix of keys and emerging titles"))

    if draft.time_horizon in {"LONG_TERM", "LEGACY_COLLECTION"}:
        priorities.append(P91RecommendationPreviewItem(text="Long-term investment opportunities"))
    elif draft.time_horizon == "SHORT_TERM_FLIP":
        priorities.append(P91RecommendationPreviewItem(text="Near-term market momentum"))
    elif draft.time_horizon == "MIXED":
        priorities.append(P91RecommendationPreviewItem(text="Flexible short- and long-term picks"))

    if draft.publisher_labels:
        pub_text = ", ".join(draft.publisher_labels[:3])
        if len(draft.publisher_labels) > 3:
            pub_text += " and more"
        priorities.append(P91RecommendationPreviewItem(text=f"{pub_text} releases"))

    if draft.creator_labels:
        for creator in draft.creator_labels[:2]:
            priorities.append(P91RecommendationPreviewItem(text=f"New work from {creator}"))

    seen: set[str] = set()
    unique: list[P91RecommendationPreviewItem] = []
    for item in priorities:
        if item.text in seen:
            continue
        seen.add(item.text)
        unique.append(item)

    return P91RecommendationPreviewRead(summary=summary, priorities=unique[:12])


def seed_draft_from_profile(session: Session, *, owner_user_id: int) -> P91OnboardingDraft:
    profile = get_collector_profile(session, owner_user_id=owner_user_id)
    return P91OnboardingDraft(
        step=1,
        collector_type=profile.collector_type,  # type: ignore[arg-type]
        risk_profile=profile.risk_profile,  # type: ignore[arg-type]
        time_horizon=profile.time_horizon,  # type: ignore[arg-type]
        publisher_labels=[p.label for p in profile.publishers],
        character_labels=[p.label for p in profile.characters],
        creator_labels=[p.label for p in profile.creators],
    )
