from __future__ import annotations

import logging
import os

from alembic import command
from alembic.config import Config

from app.core.config import API_ROOT, get_settings

logger = logging.getLogger(__name__)


def run_startup_migrations() -> None:
    """Apply Alembic migrations on API boot (production Render deploys)."""
    settings = get_settings()
    if settings.app_env != "production":
        return
    if os.getenv("DISABLE_STARTUP_MIGRATIONS", "").strip().lower() in {"1", "true", "yes"}:
        logger.info("Startup migrations skipped (DISABLE_STARTUP_MIGRATIONS)")
        return

    alembic_ini = API_ROOT / "alembic.ini"
    if not alembic_ini.is_file():
        logger.warning("Startup migrations skipped: alembic.ini not found at %s", alembic_ini)
        return

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    logger.info("Running startup Alembic upgrade to head")
    command.upgrade(cfg, "head")
    logger.info("Startup Alembic upgrade complete")
