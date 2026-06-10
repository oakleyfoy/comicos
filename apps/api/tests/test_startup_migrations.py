from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.db import startup_migrations


def test_startup_migrations_skipped_outside_production() -> None:
    settings = MagicMock(app_env="development", database_url="postgresql://local/test")
    with patch.object(startup_migrations, "get_settings", return_value=settings):
        assert startup_migrations.should_run_startup_migrations() is False


def test_should_run_startup_migrations_in_production() -> None:
    settings = MagicMock(app_env="production", database_url="postgresql://prod/test")
    with patch.object(startup_migrations, "get_settings", return_value=settings):
        assert startup_migrations.should_run_startup_migrations() is True


def test_startup_migrations_runs_in_production() -> None:
    settings = MagicMock(app_env="production", database_url="postgresql://prod/test")
    fake_api_root = MagicMock()
    fake_ini = MagicMock()
    fake_ini.is_file.return_value = True
    with patch.object(startup_migrations, "get_settings", return_value=settings):
        with patch.object(startup_migrations, "API_ROOT", fake_api_root):
            fake_api_root.__truediv__.side_effect = lambda part: fake_ini if part == "alembic.ini" else MagicMock()
            with patch.object(startup_migrations, "command") as command:
                startup_migrations.run_startup_migrations()
    command.upgrade.assert_called_once()
