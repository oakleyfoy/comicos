from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.services.pull_list_scheduler import advance_schedule_after_run, get_platform_schedule, is_schedule_due


def test_pull_list_schedule_defaults_to_615_chicago(session: Session) -> None:
    config = get_platform_schedule(session)
    assert config.schedule_time == "06:15"
    assert config.timezone == "America/Chicago"
    assert config.enabled is True
    assert config.next_run_at is not None


def test_advance_schedule_after_run(session: Session) -> None:
    moment = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    config = get_platform_schedule(session)
    config.next_run_at = moment
    config.updated_at = moment
    session.add(config)
    session.commit()
    session.refresh(config)
    assert is_schedule_due(session, moment=moment) is True
    advanced = advance_schedule_after_run(session, moment=moment)
    assert advanced.next_run_at is not None
    assert advanced.next_run_at > moment
