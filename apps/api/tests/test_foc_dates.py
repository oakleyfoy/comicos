from __future__ import annotations

from datetime import date, timedelta

from app.services.foc_dates import days_until_foc, days_until_release, foc_status_bucket, utc_today


def test_days_until_foc_and_release() -> None:
    today = date(2026, 6, 1)
    foc = today + timedelta(days=7)
    rel = today + timedelta(days=14)
    assert days_until_foc(foc, today=today) == 7
    assert days_until_release(rel, today=today) == 14
    assert days_until_foc(None, today=today) is None


def test_foc_status_all_buckets() -> None:
    today = date(2026, 6, 1)
    assert foc_status_bucket(today - timedelta(days=2), today=today) == "MISSED"
    assert foc_status_bucket(today, today=today) == "DUE_NOW"
    assert foc_status_bucket(today + timedelta(days=5), today=today) == "THIS_WEEK"
    assert foc_status_bucket(today + timedelta(days=9), today=today) == "NEXT_WEEK"
    assert foc_status_bucket(today + timedelta(days=22), today=today) == "THIS_MONTH"
    assert foc_status_bucket(today + timedelta(days=45), today=today) is None


def test_utc_today_is_date() -> None:
    assert isinstance(utc_today(), date)
