"""Nightly P70 market refresh scan."""

from __future__ import annotations

from sqlmodel import Session

from app.db.session import get_engine
from app.services.market_refresh_service import run_nightly_market_refresh_scan

MARKET_REFRESH_JOB_TYPE = "scheduled_market_refresh"


def run_daily_market_refresh() -> dict[str, int]:
    with Session(get_engine()) as session:
        result = run_nightly_market_refresh_scan(session)
        session.commit()
        return result
