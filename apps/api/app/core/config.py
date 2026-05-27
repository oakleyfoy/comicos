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
    rq_cover_pipeline_job_timeout_seconds: int = Field(default=420, alias="RQ_COVER_PIPELINE_JOB_TIMEOUT_SECONDS")
    rq_cover_pipeline_retry_max: int = Field(default=2, alias="RQ_COVER_PIPELINE_RETRY_MAX")
    rq_cover_pipeline_retry_interval_seconds: int = Field(default=45, alias="RQ_COVER_PIPELINE_RETRY_INTERVAL_SECONDS")

    cover_pipeline_max_image_bytes: int = Field(default=35 * 1024 * 1024, alias="COVER_PIPELINE_MAX_IMAGE_BYTES")
    cover_pipeline_max_image_side_px: int = Field(default=8000, alias="COVER_PIPELINE_MAX_IMAGE_SIDE_PX")
    cover_pipeline_max_image_pixels: int = Field(default=64_000_000, alias="COVER_PIPELINE_MAX_IMAGE_PIXELS")

    cover_ocr_tesseract_timeout_seconds: float = Field(default=60.0, alias="COVER_OCR_TESSERACT_TIMEOUT_SECONDS")
    cover_barcode_derive_regex_timeout_seconds: float = Field(default=10.0, alias="COVER_BARCODE_REGEX_TIMEOUT_SECONDS")
    cover_fingerprint_generation_thread_timeout_seconds: float = Field(default=45.0, alias="COVER_FINGERPRINT_THREAD_TIMEOUT_SECONDS")
    cover_quality_analysis_thread_timeout_seconds: float = Field(default=60.0, alias="COVER_QUALITY_THREAD_TIMEOUT_SECONDS")

    cover_ocr_max_raw_text_chars: int = Field(default=200_000, alias="COVER_OCR_MAX_RAW_TEXT_CHARS")
    cover_ocr_max_candidates_per_extract: int = Field(default=64, alias="COVER_OCR_MAX_CANDIDATES_PER_EXTRACT")
    cover_barcode_raw_derive_scan_max_chars: int = Field(default=120_000, alias="COVER_BARCODE_RAW_SCAN_MAX_CHARS")
    cover_barcode_candidate_emit_max_per_extract: int = Field(default=32, alias="COVER_BARCODE_EMIT_MAX_PER_EXTRACT")
    cover_ocr_replay_diff_max_chars: int = Field(default=32_768, alias="COVER_OCR_REPLAY_DIFF_MAX_CHARS")
    cover_ocr_batch_max_items: int = Field(default=250, alias="COVER_OCR_BATCH_MAX_ITEMS")
    cover_ocr_batch_item_max_enqueue_attempts: int = Field(default=5, alias="COVER_OCR_BATCH_ITEM_MAX_ENQUEUE_ATTEMPTS")

    ocr_health_window_hours: int = Field(default=24, alias="OCR_HEALTH_WINDOW_HOURS")
    cover_ocr_processing_stale_seconds: int = Field(default=7200, alias="COVER_OCR_PROCESSING_STALE_SECONDS")
    ocr_batch_item_orphan_seconds: int = Field(default=3600, alias="OCR_BATCH_ITEM_ORPHAN_SECONDS")
    ocr_replay_item_stuck_seconds: int = Field(default=7200, alias="OCR_REPLAY_ITEM_STUCK_SECONDS")

    cover_images_storage_root_raw: str = Field(default="", alias="COVER_IMAGES_STORAGE_ROOT")
    scan_ingestion_storage_root_raw: str = Field(default="", alias="SCAN_INGESTION_STORAGE_ROOT")
    scan_normalization_storage_root_raw: str = Field(default="", alias="SCAN_NORMALIZATION_STORAGE_ROOT")
    scan_boundary_storage_root_raw: str = Field(default="", alias="SCAN_BOUNDARY_STORAGE_ROOT")
    scan_ocr_storage_root_raw: str = Field(default="", alias="SCAN_OCR_STORAGE_ROOT")
    scan_reconciliation_storage_root_raw: str = Field(default="", alias="SCAN_RECONCILIATION_STORAGE_ROOT")
    scan_defects_storage_root_raw: str = Field(default="", alias="SCAN_DEFECTS_STORAGE_ROOT")
    listing_exports_storage_root_raw: str = Field(default="", alias="LISTING_EXPORTS_STORAGE_ROOT")
    operational_reports_storage_root_raw: str = Field(default="", alias="OPERATIONAL_REPORTS_STORAGE_ROOT")
    cover_images_max_bytes: int = Field(default=25 * 1024 * 1024, alias="COVER_IMAGES_MAX_BYTES")

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

    @property
    def cover_images_storage_root(self) -> Path:
        trimmed = self.cover_images_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "cover_images"

    @property
    def scan_ingestion_storage_root(self) -> Path:
        trimmed = self.scan_ingestion_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_ingestion"

    @property
    def scan_normalization_storage_root(self) -> Path:
        trimmed = self.scan_normalization_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_normalization"

    @property
    def scan_boundary_storage_root(self) -> Path:
        trimmed = self.scan_boundary_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_boundary"

    @property
    def scan_ocr_storage_root(self) -> Path:
        trimmed = self.scan_ocr_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_ocr"

    @property
    def scan_reconciliation_storage_root(self) -> Path:
        trimmed = self.scan_reconciliation_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_reconciliation"

    @property
    def scan_defects_storage_root(self) -> Path:
        trimmed = self.scan_defects_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_defects"

    @property
    def listing_exports_storage_root(self) -> Path:
        trimmed = self.listing_exports_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "listing_exports"

    @property
    def operational_reports_storage_root(self) -> Path:
        trimmed = self.operational_reports_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "operational_reports"


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
