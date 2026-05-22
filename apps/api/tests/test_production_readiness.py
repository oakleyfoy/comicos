import pytest

from app.core.config import Settings, validate_production_settings


def build_settings(**overrides) -> Settings:
    data = {
        "APP_ENV": "production",
        "database_url": "postgresql+pg8000://postgres:postgres@db.example.com/comic_os",
        "secret_key": "production-secret-key-0123456789abcdef",
        "redis_url": "redis://redis.example.com:6379/0",
        "frontend_url": "https://app.example.com",
        "cors_origins_raw": "https://app.example.com",
        "google_client_id": "google-client-id",
        "google_client_secret": "google-client-secret",
        "google_redirect_uri": "https://api.example.com/gmail/connect/callback",
        "openai_api_key": "sk-proj-example",
        "OPS_ADMIN_EMAILS": "ops@example.com",
    }
    data.update(overrides)
    return Settings(**data)


def test_validate_production_settings_accepts_complete_config() -> None:
    settings = build_settings()

    validate_production_settings(settings)


def test_validate_production_settings_rejects_missing_required_values() -> None:
    settings = build_settings(openai_api_key="", OPS_ADMIN_EMAILS="")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_settings(settings)

    assert "OPENAI_API_KEY" in str(exc_info.value)
    assert "OPS_ADMIN_EMAILS" in str(exc_info.value)


def test_validate_production_settings_rejects_default_secret_key() -> None:
    settings = build_settings(secret_key="change-me-in-development")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_settings(settings)

    assert "SECRET_KEY must be replaced" in str(exc_info.value)
