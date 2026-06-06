from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_collector_profile_crud(client: TestClient) -> None:
    token = register_and_login(client, "p77-profile@example.com")

    loaded = client.get("/api/v1/collector-profile", headers=auth_headers(token))
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["data"]["collector_type"] == "HYBRID"

    updated = client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={
            "collector_type": "COMPLETIONIST",
            "risk_profile": "CONSERVATIVE",
            "time_horizon": "LEGACY_COLLECTION",
            "default_copy_count": 2,
            "key_issue_copy_count": 4,
            "grading_preference": "OPPORTUNISTIC",
            "hold_preference": "LONG_TERM",
            "publishers": [{"interest_type": "PUBLISHER", "label": "DC", "priority_rank": 1}],
            "characters": [{"interest_type": "CHARACTER", "label": "Batman", "priority_rank": 1}],
            "creators": [{"interest_type": "CREATOR", "label": "Daniel Warren Johnson", "priority_rank": 1}],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()["data"]
    assert body["collector_type"] == "COMPLETIONIST"
    assert body["publishers"][0]["label"] == "DC"
    assert body["characters"][0]["label"] == "Batman"


def test_collector_goals_and_progress(client: TestClient) -> None:
    token = register_and_login(client, "p77-goals@example.com")

    created = client.post(
        "/api/v1/collector-profile/goals",
        headers=auth_headers(token),
        json={
            "goal_type": "RUN_COMPLETION",
            "title": "Absolute Batman",
            "target_value": 30,
            "progress_value": 22,
            "metadata": {"series_name": "Absolute Batman"},
        },
    )
    assert created.status_code == 201, created.text
    goal_id = created.json()["data"]["id"]
    assert created.json()["data"]["completion_percent"] == 73.3

    patched = client.put(
        f"/api/v1/collector-profile/goals/{goal_id}",
        headers=auth_headers(token),
        json={"progress_value": 24},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["completion_percent"] == 80.0

    listed = client.get("/api/v1/collector-profile/goals", headers=auth_headers(token))
    assert listed.status_code == 200
    assert len(listed.json()["data"]["items"]) >= 1


def test_collector_budget_and_dashboard(client: TestClient) -> None:
    token = register_and_login(client, "p77-budget@example.com")

    budget = client.put(
        "/api/v1/collector-profile/budget",
        headers=auth_headers(token),
        json={
            "monthly_budget": 500,
            "budget_period": "MONTHLY",
            "publisher_allocations": [
                {"name": "DC", "amount": 150},
                {"name": "Marvel", "amount": 150},
                {"name": "Image", "amount": 200},
            ],
            "category_allocations": [
                {"name": "#1 Issues", "amount": 200},
                {"name": "Variants", "amount": 100},
            ],
        },
    )
    assert budget.status_code == 200, budget.text
    assert budget.json()["data"]["monthly_budget"] == 500
    assert len(budget.json()["data"]["publisher_allocations"]) == 3

    dashboard = client.get("/api/v1/collector-profile/dashboard", headers=auth_headers(token))
    assert dashboard.status_code == 200
    dash = dashboard.json()["data"]
    assert dash["budget"]["monthly_budget"] == 500
    assert "profile" in dash
    assert dash["goals_summary"]["publisher_budget_allocated"] == 500
