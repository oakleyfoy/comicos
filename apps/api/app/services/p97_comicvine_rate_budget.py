"""P97 ComicVine request rate budget — hard safety layer backed by the request ledger.

This module is the single source of truth for "may the volume queue runner make a
ComicVine API request right now?". It counts *real* recorded requests from
``p97_comicvine_request_ledger`` (never chunk counts) and enforces:

- a conservative max requests per rolling hour (default 120),
- a minimum spacing between requests (default 30 seconds),
- a long pause after any HTTP 420 (default 4 hours), with no immediate retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import P97ComicVineRequestLedger

DEFAULT_MAX_REQUESTS_PER_HOUR = 120
DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS = 30.0
DEFAULT_PAUSE_HOURS_ON_420 = 4.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class RateBudgetDecision:
    allowed: bool
    reason: str
    seconds_until_next_request: float
    requests_last_hour: int
    paused_for_420: bool
    pause_until: datetime | None


class ComicVineRateBudget:
    """Rate budget evaluator/recorder backed by the ComicVine request ledger."""

    def __init__(
        self,
        session: Session,
        *,
        max_requests_per_hour: int = DEFAULT_MAX_REQUESTS_PER_HOUR,
        min_seconds_between_requests: float = DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
        pause_hours_on_420: float = DEFAULT_PAUSE_HOURS_ON_420,
    ) -> None:
        self.session = session
        self.max_requests_per_hour = max(1, int(max_requests_per_hour))
        self.min_seconds_between_requests = max(0.0, float(min_seconds_between_requests))
        self.pause_hours_on_420 = max(0.0, float(pause_hours_on_420))

    # --- counting ---------------------------------------------------------

    def get_requests_last_hour(self, *, now: datetime | None = None) -> int:
        now = _as_utc(now) or _utc_now()
        cutoff = now - timedelta(hours=1)
        stmt = (
            select(func.count())
            .select_from(P97ComicVineRequestLedger)
            .where(P97ComicVineRequestLedger.created_at >= cutoff)
        )
        return int(self.session.exec(stmt).one())

    def get_requests_last_24h(self, *, now: datetime | None = None) -> int:
        now = _as_utc(now) or _utc_now()
        cutoff = now - timedelta(hours=24)
        stmt = (
            select(func.count())
            .select_from(P97ComicVineRequestLedger)
            .where(P97ComicVineRequestLedger.created_at >= cutoff)
        )
        return int(self.session.exec(stmt).one())

    def get_last_420(self) -> datetime | None:
        stmt = (
            select(P97ComicVineRequestLedger.created_at)
            .where(P97ComicVineRequestLedger.was_420 == True)  # noqa: E712
            .order_by(P97ComicVineRequestLedger.created_at.desc())
            .limit(1)
        )
        row = self.session.exec(stmt).first()
        return _as_utc(row)

    def get_last_request_at(self) -> datetime | None:
        stmt = (
            select(P97ComicVineRequestLedger.created_at)
            .order_by(P97ComicVineRequestLedger.created_at.desc())
            .limit(1)
        )
        row = self.session.exec(stmt).first()
        return _as_utc(row)

    # --- 420 pause --------------------------------------------------------

    def pause_until(self) -> datetime | None:
        last_420 = self.get_last_420()
        if last_420 is None or self.pause_hours_on_420 <= 0:
            return None
        return last_420 + timedelta(hours=self.pause_hours_on_420)

    def should_pause_for_420(self, *, now: datetime | None = None) -> bool:
        now = _as_utc(now) or _utc_now()
        pause_until = self.pause_until()
        if pause_until is None:
            return False
        return now < pause_until

    # --- decision ---------------------------------------------------------

    def seconds_until_next_request(self, *, now: datetime | None = None) -> float:
        now = _as_utc(now) or _utc_now()
        # 420 pause dominates everything else.
        pause_until = self.pause_until()
        if pause_until is not None and now < pause_until:
            return max(0.0, (pause_until - now).total_seconds())

        waits: list[float] = [0.0]

        # Minimum spacing between requests.
        last_request = self.get_last_request_at()
        if last_request is not None and self.min_seconds_between_requests > 0:
            elapsed = (now - last_request).total_seconds()
            waits.append(self.min_seconds_between_requests - elapsed)

        # Hourly budget: if full, wait until the oldest in-window request ages out.
        if self.get_requests_last_hour(now=now) >= self.max_requests_per_hour:
            cutoff = now - timedelta(hours=1)
            stmt = (
                select(func.min(P97ComicVineRequestLedger.created_at))
                .where(P97ComicVineRequestLedger.created_at >= cutoff)
            )
            oldest = _as_utc(self.session.exec(stmt).first())
            if oldest is not None:
                waits.append((oldest + timedelta(hours=1) - now).total_seconds())
            else:
                waits.append(60.0)

        return max(0.0, max(waits))

    def can_make_request(
        self,
        *,
        max_per_hour: int | None = None,
        now: datetime | None = None,
    ) -> bool:
        return self.evaluate(max_per_hour=max_per_hour, now=now).allowed

    def evaluate(
        self,
        *,
        max_per_hour: int | None = None,
        now: datetime | None = None,
    ) -> RateBudgetDecision:
        now = _as_utc(now) or _utc_now()
        cap = self.max_requests_per_hour if max_per_hour is None else max(1, int(max_per_hour))
        pause_until = self.pause_until()
        paused = pause_until is not None and now < pause_until
        requests_last_hour = self.get_requests_last_hour(now=now)
        wait = self.seconds_until_next_request(now=now)

        if paused:
            return RateBudgetDecision(
                allowed=False,
                reason="PAUSED_FOR_420",
                seconds_until_next_request=wait,
                requests_last_hour=requests_last_hour,
                paused_for_420=True,
                pause_until=pause_until,
            )
        if requests_last_hour >= cap:
            return RateBudgetDecision(
                allowed=False,
                reason="HOURLY_BUDGET_EXHAUSTED",
                seconds_until_next_request=wait,
                requests_last_hour=requests_last_hour,
                paused_for_420=False,
                pause_until=None,
            )
        if wait > 0:
            return RateBudgetDecision(
                allowed=False,
                reason="MIN_SPACING",
                seconds_until_next_request=wait,
                requests_last_hour=requests_last_hour,
                paused_for_420=False,
                pause_until=None,
            )
        return RateBudgetDecision(
            allowed=True,
            reason="OK",
            seconds_until_next_request=0.0,
            requests_last_hour=requests_last_hour,
            paused_for_420=False,
            pause_until=None,
        )

    # --- recording --------------------------------------------------------

    def record_request(
        self,
        *,
        request_type: str,
        endpoint: str | None = None,
        comicvine_volume_id: int | None = None,
        queue_id: int | None = None,
        status_code: int | None = None,
        was_420: bool = False,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> P97ComicVineRequestLedger:
        entry = P97ComicVineRequestLedger(
            request_type=request_type,
            endpoint=endpoint,
            comicvine_volume_id=comicvine_volume_id,
            queue_id=queue_id,
            status_code=status_code,
            was_420=bool(was_420),
            created_at=_as_utc(now) or _utc_now(),
            request_metadata=metadata,
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def record_420(
        self,
        *,
        request_type: str = "issue_import",
        endpoint: str | None = None,
        comicvine_volume_id: int | None = None,
        queue_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> P97ComicVineRequestLedger:
        return self.record_request(
            request_type=request_type,
            endpoint=endpoint,
            comicvine_volume_id=comicvine_volume_id,
            queue_id=queue_id,
            status_code=420,
            was_420=True,
            metadata=metadata,
            now=now,
        )
