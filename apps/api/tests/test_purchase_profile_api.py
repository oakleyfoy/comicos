from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.purchase_profile import PurchaseProfile
from app.services.purchase_profile_scoring import compute_engine_weights
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_default_profile_and_preferences(client: TestClient, session: Session) -> None:
    email = "pp-default@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    prof = client.get("/api/v1/purchase-profile", headers=auth_headers(token))
    assert prof.status_code == 200
    data = prof.json()["data"]
    assert data["profile_type"] == "COLLECTOR"
    assert data["owner_id"] == owner_id
    assert data["is_active"] is True

    prefs = client.get("/api/v1/purchase-profile/preferences", headers=auth_headers(token))
    assert prefs.status_code == 200
    p = prefs.json()["data"]
    assert p["risk_tolerance"] == 0.5
    assert p["variant_interest"] == 0.5


def test_profile_switch_and_preference_persist(client: TestClient, session: Session) -> None:
    email = "pp-switch@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)

    inv = client.patch(
        "/api/v1/purchase-profile",
        headers=auth_headers(token),
        json={"profile_type": "INVESTOR"},
    )
    assert inv.status_code == 200
    assert inv.json()["data"]["profile_type"] == "INVESTOR"

    patch_prefs = client.patch(
        "/api/v1/purchase-profile/preferences",
        headers=auth_headers(token),
        json={"speculation_score": 0.77, "risk_tolerance": 0.66},
    )
    assert patch_prefs.status_code == 200
    assert patch_prefs.json()["data"]["speculation_score"] == 0.77

    again = client.get("/api/v1/purchase-profile/preferences", headers=auth_headers(token))
    assert again.json()["data"]["speculation_score"] == 0.77

    profiles = session.exec(select(PurchaseProfile).where(PurchaseProfile.owner_user_id == owner_id)).all()
    assert len(profiles) == 1
    assert profiles[0].is_active is True


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "pp-a@example.com")
    token_b = register_and_login(client, "pp-b@example.com")
    client.patch(
        "/api/v1/purchase-profile/preferences",
        headers=auth_headers(token_a),
        json={"completionist_score": 0.91},
    )
    b_prefs = client.get("/api/v1/purchase-profile/preferences", headers=auth_headers(token_b))
    assert b_prefs.json()["data"]["completionist_score"] == 0.5


def test_engine_weights_normalized() -> None:
    w = compute_engine_weights(
        profile_type="VARIANT_HUNTER",
        risk_tolerance=0.5,
        variant_interest=0.9,
        grading_interest=0.5,
        completionist_score=0.5,
        speculation_score=0.4,
    )
    total = w.quantity_weight + w.variant_weight + w.budget_weight
    assert abs(total - 1.0) < 1e-5
    assert w.variant_weight > w.quantity_weight
