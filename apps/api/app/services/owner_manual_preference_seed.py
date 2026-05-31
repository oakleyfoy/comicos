from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.services.user_preference_engine import create_manual_preference


@dataclass(frozen=True)
class ManualPreferenceSpec:
    preference_type: str
    preference_label: str
    preference_score: float


DEFAULT_COLLECTOR_PREFERENCE_SPECS: tuple[ManualPreferenceSpec, ...] = (
    ManualPreferenceSpec("FRANCHISE", "Batman", 92.0),
    ManualPreferenceSpec("FRANCHISE", "Spider-Man", 90.0),
    ManualPreferenceSpec("FRANCHISE", "TMNT", 88.0),
    ManualPreferenceSpec("FRANCHISE", "Invincible", 85.0),
    ManualPreferenceSpec("PUBLISHER", "Image Comics", 84.0),
    ManualPreferenceSpec("KEY_ISSUE_TYPE", "First appearances", 86.0),
    ManualPreferenceSpec("KEY_ISSUE_TYPE", "Milestone issues", 82.0),
    ManualPreferenceSpec("VARIANT_TYPE", "Affordable ratio variants", 78.0),
    ManualPreferenceSpec("SERIES", "Creator-owned #1s", 80.0),
    ManualPreferenceSpec("FRANCHISE", "Transformers", 83.0),
    ManualPreferenceSpec("FRANCHISE", "GI Joe", 81.0),
    ManualPreferenceSpec("FRANCHISE", "Spawn", 79.0),
    ManualPreferenceSpec("CHARACTER", "Venom", 77.0),
    ManualPreferenceSpec("FRANCHISE", "X-Men", 82.0),
)


def seed_manual_preferences_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    specs: tuple[ManualPreferenceSpec, ...] = DEFAULT_COLLECTOR_PREFERENCE_SPECS,
) -> int:
    """Idempotent manual preference seed via P51-03 create_manual_preference."""
    created_or_updated = 0
    for spec in specs:
        create_manual_preference(
            session,
            owner_user_id=owner_user_id,
            preference_type=spec.preference_type,
            preference_label=spec.preference_label,
            preference_score=spec.preference_score,
        )
        created_or_updated += 1
    return created_or_updated
