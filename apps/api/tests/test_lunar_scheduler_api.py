from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_lunar_scheduler_api(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    token = register_and_login(client, "lunar-sched-api@example.com")

    status = client.get("/api/v1/lunar-scheduler/status", headers=auth_headers(token))
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["credential_available"] is True
    assert "secret-value" not in str(body)

    enable = client.post("/api/v1/lunar-scheduler/enable", headers=auth_headers(token))
    assert enable.status_code == 200
    assert enable.json()["data"]["enabled"] is True
    assert enable.json()["data"]["schedule_time"] == "06:00"

    with patch("app.api.lunar_scheduler.run_scheduled_lunar_import") as run_mock:
        from app.models.lunar_scheduler import LunarScheduledRun

        run_mock.return_value = LunarScheduledRun(
            owner_user_id=1,
            trigger_type="MANUAL",
            status="NO_CHANGE",
            file_name="lunar-2026-06.csv",
            file_period="2026-06",
        )
        run_now = client.post("/api/v1/lunar-scheduler/run-now", headers=auth_headers(token))
        assert run_now.status_code == 201

    history = client.get("/api/v1/lunar-scheduler/history", headers=auth_headers(token))
    assert history.status_code == 200

    disable = client.post("/api/v1/lunar-scheduler/disable", headers=auth_headers(token))
    assert disable.status_code == 200
    assert disable.json()["data"]["enabled"] is False
