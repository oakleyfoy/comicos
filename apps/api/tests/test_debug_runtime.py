import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_debug_runtime_hidden_by_default(client: TestClient) -> None:
    response = client.get("/debug/runtime")

    assert response.status_code == 404


def test_debug_runtime_visible_when_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEBUG_RUNTIME", "true")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+pg8000://postgres:db-secret@localhost:5433/comic_os",
    )
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@localhost:6379/0")
    get_settings.cache_clear()

    response = client.get("/debug/runtime")

    assert response.status_code == 200

    payload = response.json()
    assert payload["app_name"] == "ComicOS API"
    assert payload["environment"] == "test"
    assert payload["database_url_safe"] == (
        "postgresql+pg8000://postgres:***@localhost:5433/comic_os"
    )
    assert payload["redis_url_safe"] == "redis://:***@localhost:6379/0"
    assert payload["pid"] > 0
    assert payload["cwd"]
    assert payload["started_at"]
    assert payload["git_commit"] is None or isinstance(payload["git_commit"], str)


def test_debug_runtime_masks_secrets_in_urls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEBUG_RUNTIME", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        (
            "postgresql+pg8000://postgres:db-secret@localhost:5433/comic_os"
            "?sslmode=require&password=query-secret"
        ),
    )
    monkeypatch.setenv(
        "REDIS_URL",
        "redis://:redis-secret@localhost:6379/0?token=redis-query-secret",
    )
    get_settings.cache_clear()

    response = client.get("/debug/runtime")

    assert response.status_code == 200

    payload = response.json()
    assert "db-secret" not in payload["database_url_safe"]
    assert "query-secret" not in payload["database_url_safe"]
    assert "redis-secret" not in payload["redis_url_safe"]
    assert "redis-query-secret" not in payload["redis_url_safe"]
    assert "sslmode=require" in payload["database_url_safe"]
    assert "password=***" in payload["database_url_safe"]
    assert "token=***" in payload["redis_url_safe"]
