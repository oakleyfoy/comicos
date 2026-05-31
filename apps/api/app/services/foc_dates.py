from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

FocDateStatus = Literal["DUE_NOW", "THIS_WEEK", "NEXT_WEEK", "THIS_MONTH", "MISSED"]


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def days_until_foc(foc_date: date | None, *, today: date | None = None) -> int | None:
    if foc_date is None:
        return None
    ref = today or utc_today()
    return (foc_date - ref).days


def days_until_release(release_date: date | None, *, today: date | None = None) -> int | None:
    if release_date is None:
        return None
    ref = today or utc_today()
    return (release_date - ref).days


def foc_status_bucket(foc_date: date | None, *, today: date | None = None) -> FocDateStatus | None:
    days = days_until_foc(foc_date, today=today)
    if days is None:
        return None
    if days < 0:
        return "MISSED"
    if days == 0:
        return "DUE_NOW"
    if 1 <= days <= 7:
        return "THIS_WEEK"
    if 8 <= days <= 14:
        return "NEXT_WEEK"
    if 15 <= days <= 30:
        return "THIS_MONTH"
    return None
