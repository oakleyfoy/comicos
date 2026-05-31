from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.lunar_scheduler import LunarScheduleConfig
from app.tasks.lunar_import_task import run_daily_lunar_import


def test_run_daily_lunar_import_processes_due_configs(client, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    from app.models import User
    from test_inventory import register_and_login

    register_and_login(client, "lunar-daily@example.com")
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == "lunar-daily@example.com")).one()
        session.add(
            LunarScheduleConfig(
                owner_user_id=int(user.id),
                enabled=True,
                next_run_at=past,
            )
        )
        session.commit()
        owner_id = int(user.id)

    with patch("app.tasks.lunar_import_task.run_scheduled_lunar_import") as run_mock:
        from app.models.lunar_scheduler import LunarScheduledRun

        run_mock.return_value = LunarScheduledRun(
            owner_user_id=owner_id,
            trigger_type="SCHEDULED",
            status="NO_CHANGE",
        )
        result = run_daily_lunar_import(moment=datetime.now(timezone.utc))
        assert result["runs_started"] >= 1
        run_mock.assert_called()
