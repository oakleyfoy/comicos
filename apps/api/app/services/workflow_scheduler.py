from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def normalize_schedule_fields(
    *,
    schedule_enabled: bool,
    cron_expression: str | None,
    next_run_at: datetime | None,
) -> tuple[bool, str | None, datetime | None]:
    normalized_cron = cron_expression.strip() if cron_expression is not None else None
    if normalized_cron == "":
        normalized_cron = None
    normalized_next_run_at = _as_utc(next_run_at)
    if schedule_enabled and normalized_cron is None:
        raise HTTPException(status_code=422, detail="A cron expression is required when workflow scheduling is enabled.")
    if not schedule_enabled:
        normalized_next_run_at = None
    return schedule_enabled, normalized_cron, normalized_next_run_at
