from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]

try:
    from dotenv import load_dotenv
    import os

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(API_ROOT / ".env")
    extra_env_root = os.environ.get("COMICOS_API_ENV_ROOT", "").strip()
    if extra_env_root:
        load_dotenv(Path(extra_env_root) / ".env", override=False)
    else:
        companion_env = Path(r"C:\comic-os\apps\api\.env")
        if companion_env.is_file():
            load_dotenv(companion_env, override=False)
except ImportError:
    pass


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
    scan_spine_ticks_storage_root_raw: str = Field(default="", alias="SCAN_SPINE_TICKS_STORAGE_ROOT")
    scan_corner_edges_storage_root_raw: str = Field(default="", alias="SCAN_CORNER_EDGES_STORAGE_ROOT")
    scan_surface_defects_storage_root_raw: str = Field(default="", alias="SCAN_SURFACE_DEFECTS_STORAGE_ROOT")
    scan_structural_damage_storage_root_raw: str = Field(default="", alias="SCAN_STRUCTURAL_DAMAGE_STORAGE_ROOT")
    scan_defect_aggregation_storage_root_raw: str = Field(default="", alias="SCAN_DEFECT_AGGREGATION_STORAGE_ROOT")
    scan_grading_assistance_storage_root_raw: str = Field(default="", alias="SCAN_GRADING_ASSISTANCE_STORAGE_ROOT")
    scan_visual_evidence_storage_root_raw: str = Field(default="", alias="SCAN_VISUAL_EVIDENCE_STORAGE_ROOT")
    scan_review_storage_root_raw: str = Field(default="", alias="SCAN_REVIEW_STORAGE_ROOT")
    scan_historical_comparison_storage_root_raw: str = Field(default="", alias="SCAN_HISTORICAL_COMPARISON_STORAGE_ROOT")
    scan_authentication_storage_root_raw: str = Field(default="", alias="SCAN_AUTHENTICATION_STORAGE_ROOT")
    scan_intelligence_feed_storage_root_raw: str = Field(default="", alias="SCAN_INTELLIGENCE_FEED_STORAGE_ROOT")
    scan_replay_storage_root_raw: str = Field(default="", alias="SCAN_REPLAY_STORAGE_ROOT")
    automation_jobs_storage_root_raw: str = Field(default="", alias="AUTOMATION_JOBS_STORAGE_ROOT")
    automation_workers_storage_root_raw: str = Field(default="", alias="AUTOMATION_WORKERS_STORAGE_ROOT")
    automation_workflows_storage_root_raw: str = Field(default="", alias="AUTOMATION_WORKFLOWS_STORAGE_ROOT")
    automation_recovery_storage_root_raw: str = Field(default="", alias="AUTOMATION_RECOVERY_STORAGE_ROOT")
    automation_batch_storage_root_raw: str = Field(default="", alias="AUTOMATION_BATCH_STORAGE_ROOT")
    automation_notifications_storage_root_raw: str = Field(default="", alias="AUTOMATION_NOTIFICATIONS_STORAGE_ROOT")
    automation_ops_storage_root_raw: str = Field(default="", alias="AUTOMATION_OPS_STORAGE_ROOT")
    automation_rules_storage_root_raw: str = Field(default="", alias="AUTOMATION_RULES_STORAGE_ROOT")
    automation_analytics_storage_root_raw: str = Field(default="", alias="AUTOMATION_ANALYTICS_STORAGE_ROOT")
    listing_exports_storage_root_raw: str = Field(default="", alias="LISTING_EXPORTS_STORAGE_ROOT")
    operational_reports_storage_root_raw: str = Field(default="", alias="OPERATIONAL_REPORTS_STORAGE_ROOT")
    cover_images_max_bytes: int = Field(default=25 * 1024 * 1024, alias="COVER_IMAGES_MAX_BYTES")

    lunar_username_raw: str = Field(default="", alias="LUNAR_USERNAME")
    lunar_password_raw: str = Field(default="", alias="LUNAR_PASSWORD")

    p62_v3_preview_enabled: bool = Field(default=True, alias="P62_V3_PREVIEW_ENABLED")
    p62_v3_persist_enabled: bool = Field(default=False, alias="P62_V3_PERSIST_ENABLED")
    p62_read_only_get_enabled: bool = Field(default=True, alias="P62_READ_ONLY_GET")
    p62_foc_enabled: bool = Field(default=True, alias="P62_FOC_ENABLED")
    p62_pull_forecast_enabled: bool = Field(default=True, alias="P62_PULL_FORECAST_ENABLED")
    p62_auto_watchlist_enabled: bool = Field(default=True, alias="P62_AUTO_WATCHLIST_ENABLED")

    p63_market_intelligence_enabled: bool = Field(default=True, alias="P63_MARKET_INTELLIGENCE_ENABLED")
    p63_portfolio_performance_enabled: bool = Field(default=True, alias="P63_PORTFOLIO_PERFORMANCE_ENABLED")
    p63_sell_signals_enabled: bool = Field(default=True, alias="P63_SELL_SIGNALS_ENABLED")
    p63_acquisition_opportunities_enabled: bool = Field(default=True, alias="P63_ACQUISITION_OPPORTUNITIES_ENABLED")
    p63_market_signals_enabled: bool = Field(default=True, alias="P63_MARKET_SIGNALS_ENABLED")

    p64_collector_assistant_enabled: bool = Field(default=True, alias="P64_COLLECTOR_ASSISTANT_ENABLED")
    p64_llm_narration_enabled: bool = Field(default=False, alias="P64_LLM_NARRATION_ENABLED")

    p65_collector_workspace_enabled: bool = Field(default=True, alias="P65_COLLECTOR_WORKSPACE_ENABLED")
    p65_llm_narration_enabled: bool = Field(default=False, alias="P65_LLM_NARRATION_ENABLED")
    p65_automation_enabled: bool = Field(default=True, alias="P65_AUTOMATION_ENABLED")
    p65_notification_center_enabled: bool = Field(default=True, alias="P65_NOTIFICATION_CENTER_ENABLED")

    p66_variant_intelligence_enabled: bool = Field(default=True, alias="P66_VARIANT_INTELLIGENCE_ENABLED")
    p66_quantity_intelligence_enabled: bool = Field(default=True, alias="P66_QUANTITY_INTELLIGENCE_ENABLED")
    p66_market_pricing_enabled: bool = Field(default=True, alias="P66_MARKET_PRICING_ENABLED")
    p66_variant_decision_enabled: bool = Field(default=True, alias="P66_VARIANT_DECISION_ENABLED")

    p67_portfolio_analytics_enabled: bool = Field(default=True, alias="P67_PORTFOLIO_ANALYTICS_ENABLED")
    p67_collection_analytics_enabled: bool = Field(default=True, alias="P67_COLLECTION_ANALYTICS_ENABLED")
    p67_recommendation_performance_enabled: bool = Field(default=True, alias="P67_RECOMMENDATION_PERFORMANCE_ENABLED")
    p67_grading_analytics_enabled: bool = Field(default=True, alias="P67_GRADING_ANALYTICS_ENABLED")
    p67_investor_dashboard_enabled: bool = Field(default=True, alias="P67_INVESTOR_DASHBOARD_ENABLED")

    p68_market_pricing_enabled: bool = Field(default=True, alias="P68_MARKET_PRICING_ENABLED")
    p68_ebay_provider_enabled: bool = Field(default=False, alias="P68_EBAY_PROVIDER_ENABLED")
    ebay_api_client_id: str = Field(default="", alias="EBAY_API_CLIENT_ID")
    ebay_api_client_secret: str = Field(default="", alias="EBAY_API_CLIENT_SECRET")
    ebay_environment: str = Field(default="production", alias="EBAY_ENVIRONMENT")
    ebay_account_deletion_compliance_enabled: bool = Field(
        default=True,
        alias="EBAY_ACCOUNT_DELETION_COMPLIANCE_ENABLED",
    )
    ebay_account_deletion_verification_token: str = Field(
        default="",
        alias="EBAY_ACCOUNT_DELETION_VERIFICATION_TOKEN",
    )
    ebay_account_deletion_endpoint_url: str = Field(
        default="https://api.comicosapp.com/api/v1/ebay/account-deletion",
        alias="EBAY_ACCOUNT_DELETION_ENDPOINT_URL",
    )
    p68_manual_fmv_enabled: bool = Field(default=True, alias="P68_MANUAL_FMV_ENABLED")
    p68_auto_overwrite_inventory_fmv: bool = Field(default=False, alias="P68_AUTO_OVERWRITE_INVENTORY_FMV")

    p70_market_refresh_enabled: bool = Field(default=True, alias="P70_MARKET_REFRESH_ENABLED")
    p70_market_refresh_top_holdings_limit: int = Field(default=50, alias="P70_MARKET_REFRESH_TOP_HOLDINGS_LIMIT")

    p71_exit_recommendations_enabled: bool = Field(default=True, alias="P71_EXIT_RECOMMENDATIONS_ENABLED")
    p71_listing_intelligence_enabled: bool = Field(default=True, alias="P71_LISTING_INTELLIGENCE_ENABLED")
    p71_liquidity_enabled: bool = Field(default=True, alias="P71_LIQUIDITY_ENABLED")
    p71_exit_queue_enabled: bool = Field(default=True, alias="P71_EXIT_QUEUE_ENABLED")
    p71_sell_dashboard_enabled: bool = Field(default=True, alias="P71_SELL_DASHBOARD_ENABLED")

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
        from app.http_cors import resolve_cors_origins

        return resolve_cors_origins(self)

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
    def scan_spine_ticks_storage_root(self) -> Path:
        trimmed = self.scan_spine_ticks_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_spine_ticks"

    @property
    def scan_corner_edges_storage_root(self) -> Path:
        trimmed = self.scan_corner_edges_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_corner_edges"

    @property
    def scan_surface_defects_storage_root(self) -> Path:
        trimmed = self.scan_surface_defects_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_surface_defects"

    @property
    def scan_structural_damage_storage_root(self) -> Path:
        trimmed = self.scan_structural_damage_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_structural_damage"

    @property
    def scan_defect_aggregation_storage_root(self) -> Path:
        trimmed = self.scan_defect_aggregation_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_defect_aggregation"

    @property
    def scan_grading_assistance_storage_root(self) -> Path:
        trimmed = self.scan_grading_assistance_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_grading_assistance"

    @property
    def scan_visual_evidence_storage_root(self) -> Path:
        trimmed = self.scan_visual_evidence_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_visual_evidence"

    @property
    def scan_review_storage_root(self) -> Path:
        trimmed = self.scan_review_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_review"

    @property
    def scan_historical_comparison_storage_root(self) -> Path:
        trimmed = self.scan_historical_comparison_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_historical_comparison"

    @property
    def scan_authentication_storage_root(self) -> Path:
        trimmed = self.scan_authentication_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_authentication"

    @property
    def scan_intelligence_feed_storage_root(self) -> Path:
        trimmed = self.scan_intelligence_feed_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_intelligence_feed"

    @property
    def scan_replay_storage_root(self) -> Path:
        trimmed = self.scan_replay_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "scan_replay"

    @property
    def automation_jobs_storage_root(self) -> Path:
        trimmed = self.automation_jobs_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_jobs"

    @property
    def automation_workers_storage_root(self) -> Path:
        trimmed = self.automation_workers_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_workers"

    @property
    def automation_workflows_storage_root(self) -> Path:
        trimmed = self.automation_workflows_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_workflows"

    @property
    def automation_recovery_storage_root(self) -> Path:
        trimmed = self.automation_recovery_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_recovery"

    @property
    def automation_batch_storage_root(self) -> Path:
        trimmed = self.automation_batch_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_batch"

    @property
    def automation_notifications_storage_root(self) -> Path:
        trimmed = self.automation_notifications_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_notifications"

    @property
    def automation_ops_storage_root(self) -> Path:
        trimmed = self.automation_ops_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_ops"

    @property
    def automation_rules_storage_root(self) -> Path:
        trimmed = self.automation_rules_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_rules"

    @property
    def automation_analytics_storage_root(self) -> Path:
        trimmed = self.automation_analytics_storage_root_raw.strip()
        if trimmed:
            return Path(trimmed).expanduser()
        return REPO_ROOT / "data" / "automation_analytics"

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
        "EBAY_API_CLIENT_ID": settings.ebay_api_client_id,
        "EBAY_API_CLIENT_SECRET": settings.ebay_api_client_secret,
        "EBAY_ENVIRONMENT": settings.ebay_environment,
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

    from app.http_cors import COMIC_OS_PRODUCTION_WEB_ORIGINS, resolve_cors_origins

    allowed = set(resolve_cors_origins(settings))
    missing_web_origins = [origin for origin in COMIC_OS_PRODUCTION_WEB_ORIGINS if origin not in allowed]
    if missing_web_origins:
        raise RuntimeError(
            "Production CORS must allow ComicOS web origins: "
            + ", ".join(missing_web_origins)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
