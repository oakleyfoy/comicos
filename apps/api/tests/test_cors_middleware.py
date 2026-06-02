import pytest
from fastapi.testclient import TestClient

from app.http_cors import COMIC_OS_PRODUCTION_WEB_ORIGINS, resolve_cors_origins


def test_resolve_cors_origins_adds_production_web_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://comicosapp.com")
    monkeypatch.setenv("FRONTEND_URL", "https://comicosapp.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    origins = resolve_cors_origins(settings)

    for required in COMIC_OS_PRODUCTION_WEB_ORIGINS:
        assert required in origins


def test_cors_preflight_for_local_dev_origin(client: TestClient) -> None:
    response = client.options(
        "/inventory/summary",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_headers_on_unauthenticated_inventory_summary(client: TestClient) -> None:
    response = client.get(
        "/inventory/summary",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert response.json()["detail"] == "Not authenticated"


def test_cors_headers_on_validation_error(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "cors-user@example.com", "password": "supersecret123"})
    login = client.post(
        "/auth/login",
        json={"email": "cors-user@example.com", "password": "supersecret123"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/inventory?release_year=0",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 422
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
