from __future__ import annotations

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.user_preference_intelligence import UserPreferenceProfile
from app.services.user_preference_engine import (
    create_manual_preference,
    disable_manual_preference,
    refresh_user_preferences,
    safe_default_preferences,
)
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_user_preference_engine_empty_inventory_safe(client: TestClient) -> None:
    email = "market-user-pref-empty@example.com"
    register_and_login(client, email)
    defaults = safe_default_preferences()
    assert defaults[0]["preference_score"] == 50.0

    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        result = refresh_user_preferences(session, owner_user_id=owner_id)
    assert result["profiles_updated"] >= 0
    assert result["used_defaults"] in {0, 1}


def test_manual_preferences_create_and_disable(client: TestClient) -> None:
    email = "market-user-pref-manual@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        profile = create_manual_preference(
            session,
            owner_user_id=owner_id,
            preference_type="FRANCHISE",
            preference_label="Spider-Man",
            preference_score=88.0,
        )
        disabled = disable_manual_preference(session, owner_user_id=owner_id, profile_id=int(profile.id or 0))
        row = session.exec(select(UserPreferenceProfile).where(UserPreferenceProfile.id == profile.id)).one()
    assert disabled.status == "DISABLED"
    assert row.status == "DISABLED"
