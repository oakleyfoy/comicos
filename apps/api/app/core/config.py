from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_name: str = "ComicOS API"
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
    debug_runtime: bool = False
    ops_admin_emails_raw: str = Field(default="", alias="OPS_ADMIN_EMAILS")
    secret_key: str = "change-me-in-development"
    access_token_expire_minutes: int = 60
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    openai_api_key: str | None = None
    openai_order_parser_model: str = "gpt-4o-mini"
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://127.0.0.1:5173"
    cors_origins_raw: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        alias="CORS_ORIGINS",
    )
    rq_ai_parse_queue_name: str = "ai_parse"
    rq_gmail_sync_queue_name: str = "gmail_sync"
    rq_job_timeout_seconds: int = 180
    rq_job_result_ttl_seconds: int = 86400
    rq_job_failure_ttl_seconds: int = 604800
    rq_job_retry_max: int = 3
    rq_job_retry_interval_seconds: int = 30

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", API_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ops_admin_emails(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.ops_admin_emails_raw.split(",")
            if email.strip()
        }

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


def validate_production_settings(settings: Settings) -> None:
    if settings.app_env.lower() != "production":
        return

    required_settings = {
        "SECRET_KEY": settings.secret_key,
        "DATABASE_URL": settings.database_url,
        "REDIS_URL": settings.redis_url,
        "FRONTEND_URL": settings.frontend_url,
        "CORS_ORIGINS": settings.cors_origins_raw,
        "GOOGLE_CLIENT_ID": settings.google_client_id or "",
        "GOOGLE_CLIENT_SECRET": settings.google_client_secret or "",
        "GOOGLE_REDIRECT_URI": settings.google_redirect_uri or "",
        "OPENAI_API_KEY": settings.openai_api_key or "",
        "OPS_ADMIN_EMAILS": settings.ops_admin_emails_raw,
    }
    missing = [name for name, value in required_settings.items() if not str(value).strip()]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            "Missing required production environment variables: "
            f"{missing_list}. Refuse to start with incomplete production configuration."
        )

    if settings.secret_key == "change-me-in-development":
        raise RuntimeError("SECRET_KEY must be replaced before starting in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
