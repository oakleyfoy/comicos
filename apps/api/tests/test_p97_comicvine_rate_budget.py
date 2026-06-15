from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(API_ROOT), str(API_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.models  # noqa: F401,E402

from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    ComicVineRateBudget,
)

NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_records_count_in_last_hour_window(session: Session) -> None:
    budget = ComicVineRateBudget(session, max_requests_per_hour=120, min_seconds_between_requests=0)
    for i in range(5):
        budget.record_request(request_type="issue_import", now=NOW - timedelta(minutes=i))
    # Older-than-an-hour request must be excluded.
    budget.record_request(request_type="issue_import", now=NOW - timedelta(hours=2))
    assert budget.get_requests_last_hour(now=NOW) == 5
    assert budget.get_requests_last_24h(now=NOW) == 6


def test_default_max_requests_per_hour_is_150() -> None:
    assert DEFAULT_MAX_REQUESTS_PER_HOUR == 150


def test_hourly_budget_exhausted_at_151_with_default_cap(session: Session) -> None:
    budget = ComicVineRateBudget(session, min_seconds_between_requests=0)
    assert budget.max_requests_per_hour == 150
    for _ in range(149):
        budget.record_request(request_type="issue_import", now=NOW - timedelta(minutes=1))
    assert budget.can_make_request(now=NOW) is True
    budget.record_request(request_type="issue_import", now=NOW - timedelta(minutes=1))
    assert budget.get_requests_last_hour(now=NOW) == 150
    assert budget.can_make_request(now=NOW) is False
    budget.record_request(request_type="issue_import", now=NOW - timedelta(minutes=1))
    assert budget.get_requests_last_hour(now=NOW) == 151
    decision = budget.evaluate(now=NOW)
    assert decision.reason == "HOURLY_BUDGET_EXHAUSTED"
    assert decision.allowed is False


def test_cli_max_requests_per_hour_override(session: Session) -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    assert parser.parse_args([]).max_requests_per_hour == 150
    override = parser.parse_args(["--max-requests-per-hour", "200"]).max_requests_per_hour
    budget = ComicVineRateBudget(session, max_requests_per_hour=override, min_seconds_between_requests=0)
    assert budget.max_requests_per_hour == 200


def test_420_triggers_four_hour_pause(session: Session) -> None:
    budget = ComicVineRateBudget(
        session, max_requests_per_hour=120, min_seconds_between_requests=0, pause_hours_on_420=4
    )
    budget.record_420(now=NOW)
    assert budget.should_pause_for_420(now=NOW) is True
    assert budget.can_make_request(now=NOW) is False
    pause_until = budget.pause_until()
    assert pause_until == NOW + timedelta(hours=4)
    # Still paused just before the window ends...
    assert budget.should_pause_for_420(now=NOW + timedelta(hours=3, minutes=59)) is True
    # ...and clear once the window elapses.
    assert budget.should_pause_for_420(now=NOW + timedelta(hours=4, minutes=1)) is False


def test_no_immediate_retry_after_420(session: Session) -> None:
    budget = ComicVineRateBudget(
        session, max_requests_per_hour=120, min_seconds_between_requests=30, pause_hours_on_420=4
    )
    budget.record_420(now=NOW)
    wait = budget.seconds_until_next_request(now=NOW)
    # Pause dominates: wait should be ~4 hours, never a quick retry.
    assert wait > 3.5 * 3600
    decision = budget.evaluate(now=NOW)
    assert decision.reason == "PAUSED_FOR_420"
    assert decision.paused_for_420 is True


def test_min_spacing_between_requests(session: Session) -> None:
    budget = ComicVineRateBudget(session, max_requests_per_hour=120, min_seconds_between_requests=30)
    budget.record_request(request_type="issue_import", now=NOW)
    wait = budget.seconds_until_next_request(now=NOW + timedelta(seconds=10))
    assert 19.0 <= wait <= 21.0
    assert budget.can_make_request(now=NOW + timedelta(seconds=10)) is False
    assert budget.can_make_request(now=NOW + timedelta(seconds=31)) is True


def test_last_420_returns_latest(session: Session) -> None:
    budget = ComicVineRateBudget(session, pause_hours_on_420=4)
    budget.record_420(now=NOW - timedelta(hours=10))
    budget.record_420(now=NOW - timedelta(hours=1))
    last = budget.get_last_420()
    assert last is not None
    assert last == NOW - timedelta(hours=1)
