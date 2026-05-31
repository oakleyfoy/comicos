from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app.models.lunar_scheduler import LunarScheduleConfig, LunarScheduledRun
from app.services.lunar_authenticated_client import LunarDownloadedCsv
from app.services.lunar_change_detection import LunarFileSnapshot, calculate_file_checksum
from app.services.lunar_scheduler import (
    STATUS_COMPLETED,
    STATUS_NO_CHANGE,
    disable_schedule,
    enable_schedule,
    run_scheduled_lunar_import,
)
from app.schemas.lunar_feed import LunarFeedImportSummaryRead


def _downloaded(content: bytes = b"a,b\n1,2\n") -> LunarDownloadedCsv:
    from datetime import datetime, timezone

    return LunarDownloadedCsv(
        file_name="lunar-2026-06.csv",
        file_period="2026-06",
        file_type="LUNAR_FORMAT",
        content_bytes=content,
        downloaded_at=datetime.now(timezone.utc),
        source_url="https://example.test/lunar.csv",
    )


def test_enable_disable_schedule(client, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    from test_inventory import register_and_login

    token = register_and_login(client, "lunar-sched@example.com")
    from test_inventory import auth_headers

    enable = client.post("/api/v1/lunar-scheduler/enable", headers=auth_headers(token))
    assert enable.status_code == 200
    assert enable.json()["data"]["enabled"] is True
    disable = client.post("/api/v1/lunar-scheduler/disable", headers=auth_headers(token))
    assert disable.status_code == 200
    assert disable.json()["data"]["enabled"] is False


def test_run_scheduled_import_no_change(client, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    from app.db.session import get_engine
    from app.models import User
    from test_inventory import register_and_login

    token = register_and_login(client, "lunar-nochange@example.com")
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == "lunar-nochange@example.com")).one()
        content = b"MainIdentifier,PublisherName,SeriesName\nA1,Image,Series\n"
        checksum = calculate_file_checksum(content)
        config = LunarScheduleConfig(
            owner_user_id=int(user.id),
            enabled=True,
            last_imported_file_name="lunar-2026-06.csv",
            last_imported_file_period="2026-06",
            last_imported_checksum=checksum,
        )
        session.add(config)
        session.commit()

    def fake_download():
        return _downloaded(content)

    with patch("app.services.lunar_scheduler.download_latest_monthly_products_csv", fake_download):
        with patch("app.services.lunar_scheduler.refresh_release_intelligence_after_lunar_import") as refresh_mock:
            from test_inventory import auth_headers

            resp = client.post("/api/v1/lunar-scheduler/run-now", headers=auth_headers(token))
            assert resp.status_code == 201
            assert resp.json()["data"]["status"] == STATUS_NO_CHANGE
            refresh_mock.assert_not_called()


def test_run_scheduled_import_changed_file(client, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    from app.db.session import get_engine
    from app.models import User
    from test_inventory import auth_headers, register_and_login

    token = register_and_login(client, "lunar-change@example.com")
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == "lunar-change@example.com")).one()
        config = LunarScheduleConfig(
            owner_user_id=int(user.id),
            enabled=True,
            last_imported_file_name="lunar-2026-06.csv",
            last_imported_file_period="2026-06",
            last_imported_checksum="old",
        )
        session.add(config)
        session.commit()
        owner_id = int(user.id)

    csv_body = (
        "MainIdentifier,PublisherName,SeriesName,IssueNumber,Title,FOCDate,InStoreDate,Retail\n"
        "A1,Image,Battle Beast,8,Battle Beast #8,2026-06-01,2026-06-24,4.99\n"
    )

    def fake_download():
        return _downloaded(csv_body.encode("utf-8"))

    with patch("app.services.lunar_scheduler.download_latest_monthly_products_csv", fake_download):
        with patch("app.services.lunar_scheduler.refresh_release_intelligence_after_lunar_import") as refresh_mock:
            resp = client.post("/api/v1/lunar-scheduler/run-now", headers=auth_headers(token))
            assert resp.status_code == 201
            assert resp.json()["data"]["status"] == STATUS_COMPLETED
            refresh_mock.assert_called_once()

    with Session(get_engine()) as session:
        run = session.exec(select(LunarScheduledRun).where(LunarScheduledRun.owner_user_id == owner_id)).first()
        assert run is not None
        assert run.status == STATUS_COMPLETED
