"""Tests for marketplace monitoring runner script."""

from __future__ import annotations

import sys

import pytest


def test_runner_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import run_marketplace_monitoring as runner

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_marketplace_monitoring.py", "--email", "user@example.com"],
    )
    assert runner.main() == 1


def test_runner_dry_run_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock, patch

    from app.services.marketplace.marketplace_monitoring_service import MonitoringRunSummary
    from scripts import run_marketplace_monitoring as runner

    monkeypatch.setenv("DATABASE_URL", "sqlite:///test-runner.db")
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_marketplace_monitoring.py", "--email", "user@example.com", "--dry-run"],
    )

    class _SessionCtx:
        def __enter__(self):
            return MagicMock()

        def __exit__(self, *args: object) -> None:
            return None

    with patch("app.db.session.get_engine", return_value=MagicMock()):
        with patch("sqlmodel.Session", return_value=_SessionCtx()):
            with patch("scripts.owner_lookup.resolve_owner_user_id", return_value=1):
                with patch(
                    "app.services.marketplace.marketplace_monitoring_service.run_active_saved_searches",
                    return_value=MonitoringRunSummary(searches_run=2, listings_found=3),
                ) as mock_run:
                    assert runner.main() == 0
                    mock_run.assert_called_once()
                    assert mock_run.call_args.kwargs["dry_run"] is True
