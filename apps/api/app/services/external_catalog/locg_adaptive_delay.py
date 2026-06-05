"""Adaptive delay between LoCG detail page navigations."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

CONSECUTIVE_CLEAN_PAGES_TO_DECREASE = 20
DELAY_INCREASE_ON_THROTTLE_SECONDS = 0.5
DELAY_DECREASE_ON_CLEAN_STREAK_SECONDS = 0.25


@dataclass
class AdaptiveDelayController:
    min_delay_seconds: float = 0.75
    max_delay_seconds: float = 1.5
    current_delay_seconds: float = 0.0
    consecutive_clean_pages: int = 0
    rate_limit_429_count: int = 0
    throttle_events: int = 0
    _last_logged_delay: float = -1.0

    def __post_init__(self) -> None:
        if self.current_delay_seconds <= 0:
            self.current_delay_seconds = round(
                (self.min_delay_seconds + self.max_delay_seconds) / 2, 3
            )
        self.current_delay_seconds = self._clamp(self.current_delay_seconds)

    def _clamp(self, value: float) -> float:
        return round(
            max(self.min_delay_seconds, min(self.max_delay_seconds, value)),
            3,
        )

    def sample_pre_goto_delay(self) -> float:
        """Random sleep duration before navigating to a detail page."""
        low = self.min_delay_seconds
        high = max(low, self.current_delay_seconds)
        return round(random.uniform(low, high), 3)

    def record_issue_outcome(
        self,
        *,
        had_429: bool,
        had_cloudflare: bool,
        succeeded: bool,
    ) -> None:
        """One throttle adjustment per detail page (429 and/or Cloudflare on that page)."""
        if had_429:
            self.rate_limit_429_count += 1
        if had_429 or had_cloudflare:
            self._on_throttle_event()
        elif succeeded:
            self.note_clean_page()

    def note_clean_page(self) -> None:
        self.consecutive_clean_pages += 1
        if self.consecutive_clean_pages >= CONSECUTIVE_CLEAN_PAGES_TO_DECREASE:
            self.current_delay_seconds = self._clamp(
                self.current_delay_seconds - DELAY_DECREASE_ON_CLEAN_STREAK_SECONDS
            )
            self.consecutive_clean_pages = 0
            self.log_status(force=True)

    def _on_throttle_event(self) -> None:
        self.throttle_events += 1
        self.consecutive_clean_pages = 0
        self.current_delay_seconds = self._clamp(
            self.current_delay_seconds + DELAY_INCREASE_ON_THROTTLE_SECONDS
        )
        self.log_status(force=True)

    def log_status(
        self,
        *,
        cloudflare_wait_count: int | None = None,
        force: bool = False,
    ) -> None:
        if (
            not force
            and abs(self.current_delay_seconds - self._last_logged_delay) < 0.001
        ):
            return
        self._last_logged_delay = self.current_delay_seconds
        cf = (
            cloudflare_wait_count
            if cloudflare_wait_count is not None
            else "—"
        )
        print(
            f"[throttle] delay={self.current_delay_seconds:.2f}s "
            f"(min={self.min_delay_seconds:.2f} max={self.max_delay_seconds:.2f}) "
            f"429_count={self.rate_limit_429_count} "
            f"cloudflare_waits={cf} "
            f"clean_streak={self.consecutive_clean_pages}/"
            f"{CONSECUTIVE_CLEAN_PAGES_TO_DECREASE}",
            flush=True,
        )

    def to_dict(self) -> dict[str, float | int]:
        return {
            "adaptive_delay_enabled": True,
            "min_delay_seconds": self.min_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "final_delay_seconds": self.current_delay_seconds,
            "rate_limit_429_count": self.rate_limit_429_count,
            "throttle_events": self.throttle_events,
            "consecutive_clean_pages": self.consecutive_clean_pages,
        }
