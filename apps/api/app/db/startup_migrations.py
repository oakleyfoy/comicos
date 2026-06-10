from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import API_ROOT, get_settings

logger = logging.getLogger(__name__)


def should_run_startup_migrations() -> bool:
    settings = get_settings()
    return settings.app_env == "production"


def run_alembic_upgrade_head(*, cwd: Path | None = None) -> None:
    """Run Alembic upgrade in the current process (tests / explicit tooling)."""
    settings = get_settings()
    alembic_ini = API_ROOT / "alembic.ini"
    if not alembic_ini.is_file():
        logger.warning("Startup migrations skipped: alembic.ini not found at %s", alembic_ini)
        return

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    logger.info("Running Alembic upgrade to head")
    command.upgrade(cfg, "head")
    logger.info("Alembic upgrade complete")


def run_startup_migrations() -> None:
    """Apply Alembic migrations when APP_ENV=production (legacy in-process hook)."""
    if not should_run_startup_migrations():
        return
    run_alembic_upgrade_head()


def run_startup_migrations_subprocess(*, cwd: Path | None = None) -> None:
    """Apply migrations in a child process (Render boot — avoids OOM with app.main)."""
    if not should_run_startup_migrations():
        return
    workdir = cwd or API_ROOT
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=workdir,
        check=True,
    )
