from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.user_preference_intelligence import UserPreferenceProfile
from app.services.owner_manual_preference_seed import (
    DEFAULT_COLLECTOR_PREFERENCE_SPECS,
    seed_manual_preferences_for_owner,
)
from test_inventory import register_and_login


def test_owner_preference_seed_idempotent(client: TestClient, session: Session) -> None:
    email = "owner-pref-seed@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    first = seed_manual_preferences_for_owner(session, owner_user_id=owner_id)
    second = seed_manual_preferences_for_owner(session, owner_user_id=owner_id)
    assert first == len(DEFAULT_COLLECTOR_PREFERENCE_SPECS)
    assert second == len(DEFAULT_COLLECTOR_PREFERENCE_SPECS)
    profiles = session.exec(
        select(UserPreferenceProfile).where(UserPreferenceProfile.owner_user_id == owner_id)
    ).all()
    assert len(profiles) == len(DEFAULT_COLLECTOR_PREFERENCE_SPECS)
    keys = {p.preference_key for p in profiles}
    assert len(keys) == len(profiles)
