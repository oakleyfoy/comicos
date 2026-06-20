"""P100-26 vision sandbox activation diagnostic."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_vision_sandbox_status_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("PHOTO_IMPORT_VISION_SANDBOX", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        client = TestClient(app)
        res = client.get("/api/v1/photo-import/admin/vision-sandbox-status")
        assert res.status_code == 200
        body = res.json()
        assert body["photo_import_vision_sandbox"] is True
        assert body["photo_import_vision_sandbox_model"]
        assert body["environment_value"] == "true"
        assert body["hostname"]
    finally:
        get_settings.cache_clear()
