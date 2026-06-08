from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_onboarding_status_alias(client: TestClient) -> None:
    token = register_and_login(client, "p91-status-alias@example.com")
    resp = client.get("/api/v1/collector-profile/onboarding/status", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["onboarding_completed"] is False


def test_onboarding_draft_resume_and_dedupe(client: TestClient) -> None:
    token = register_and_login(client, "p91-draft-resume@example.com")
    draft = {
        "step": 5,
        "collector_type": "READER",
        "risk_profile": "CONSERVATIVE",
        "time_horizon": "MIXED",
        "publisher_labels": ["Marvel", "marvel", " DC "],
        "character_labels": ["Batman", "Batman"],
        "creator_labels": ["Jim Lee"],
    }
    saved = client.put(
        "/api/v1/collector-profile/onboarding/draft",
        headers=auth_headers(token),
        json={"draft": draft},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()["data"]["draft"]
    assert body["step"] == 5
    assert body["publisher_labels"] == ["Marvel", "DC"]
    assert body["character_labels"] == ["Batman"]

    reloaded = client.get("/api/v1/collector-profile/onboarding", headers=auth_headers(token))
    assert reloaded.json()["data"]["draft"]["step"] == 5
    assert reloaded.json()["data"]["draft"]["time_horizon"] == "MIXED"


def test_onboarding_complete_preserves_buying_defaults(client: TestClient) -> None:
    token = register_and_login(client, "p91-buying-defaults@example.com")
    patched = client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={"default_copy_count": 9, "key_issue_copy_count": 11, "grading_preference": "NEVER_GRADE"},
    )
    assert patched.status_code == 200, patched.text

    draft = {
        "step": 7,
        "collector_type": "HYBRID",
        "risk_profile": "MODERATE",
        "time_horizon": "LONG_TERM",
        "publisher_labels": ["Image"],
        "character_labels": [],
        "creator_labels": [],
    }
    done = client.post(
        "/api/v1/collector-profile/onboarding/complete",
        headers=auth_headers(token),
        json={"draft": draft},
    )
    assert done.status_code == 200, done.text

    profile = client.get("/api/v1/collector-profile", headers=auth_headers(token)).json()["data"]
    assert profile["default_copy_count"] == 9
    assert profile["key_issue_copy_count"] == 11
    assert profile["grading_preference"] == "NEVER_GRADE"
    assert profile["collector_type"] == "HYBRID"


def test_onboarding_preview_friendly_labels(client: TestClient) -> None:
    token = register_and_login(client, "p91-preview@example.com")
    preview = client.post(
        "/api/v1/collector-profile/onboarding/preview",
        headers=auth_headers(token),
        json={
            "step": 7,
            "collector_type": "SPECULATOR",
            "risk_profile": "MODERATE",
            "time_horizon": "MIXED",
            "publisher_labels": ["Marvel"],
            "character_labels": ["Spider-Man"],
            "creator_labels": [],
        },
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["summary"]["Risk"] == "Balanced"
    assert data["summary"]["Time Horizon"] == "Mixed"
    assert any("Spider-Man" in row["text"] for row in data["priorities"])


def test_interest_option_kinds_and_invalid_kind(client: TestClient) -> None:
    token = register_and_login(client, "p91-kinds@example.com")
    for kind in ("PUBLISHER", "CHARACTER", "CREATOR"):
        resp = client.get(
            "/api/v1/collector-profile/onboarding/interest-options",
            headers=auth_headers(token),
            params={"kind": kind},
        )
        assert resp.status_code == 200, resp.text
        assert "items" in resp.json()["data"]

    bad = client.get(
        "/api/v1/collector-profile/onboarding/interest-options",
        headers=auth_headers(token),
        params={"kind": "SERIES"},
    )
    assert bad.status_code == 422


def test_onboarding_invalid_enum_rejected_at_api(client: TestClient) -> None:
    token = register_and_login(client, "p91-invalid-enum@example.com")
    saved = client.put(
        "/api/v1/collector-profile/onboarding/draft",
        headers=auth_headers(token),
        json={
            "draft": {
                "step": 2,
                "collector_type": "NOT_A_TYPE",
                "risk_profile": "MODERATE",
                "time_horizon": "NOT_A_HORIZON",
                "publisher_labels": [],
                "character_labels": [],
                "creator_labels": [],
            }
        },
    )
    assert saved.status_code == 422
