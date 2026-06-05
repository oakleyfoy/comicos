"""Cloudflare / security verification waits for LoCG browser capture."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

SECURITY_VERIFICATION_MAX_WAIT_SECONDS = 60.0
SECURITY_VERIFICATION_POLL_SECONDS = 2.0


class LocgSecurityVerificationTimeout(Exception):
    """Raised when Cloudflare/security verification does not clear in time."""

_VERIFICATION_TEXT_MARKERS = (
    "performing security verification",
    "not a bot",
)


@dataclass
class SecurityWaitAccumulator:
    cloudflare_wait_count: int = 0
    cloudflare_total_wait_seconds: float = 0.0

    def add(self, *, wait_count: int, wait_seconds: float) -> None:
        self.cloudflare_wait_count += wait_count
        self.cloudflare_total_wait_seconds = round(
            self.cloudflare_total_wait_seconds + wait_seconds, 3
        )


def _page_text_lower(page: Page) -> str:
    try:
        return (
            page.evaluate(
                "() => document.body && document.body.innerText ? document.body.innerText : ''"
            )
            or ""
        ).lower()
    except Exception:
        return ""


def _has_verification_text(text_lower: str) -> bool:
    return any(marker in text_lower for marker in _VERIFICATION_TEXT_MARKERS)


def is_security_verification_screen(page: Page, *, for_list_page: bool) -> bool:
    text_lower = _page_text_lower(page)
    if _has_verification_text(text_lower):
        return True
    if for_list_page:
        try:
            if page.locator("#comic-list-block").count() == 0:
                return True
        except Exception:
            return True
    return False


def wait_for_security_verification_clear(
    page: Page,
    *,
    for_list_page: bool,
    accumulator: SecurityWaitAccumulator | None = None,
    max_wait_seconds: float = SECURITY_VERIFICATION_MAX_WAIT_SECONDS,
    poll_interval_seconds: float = SECURITY_VERIFICATION_POLL_SECONDS,
) -> bool:
    """
    Wait until security verification clears. Returns True if clear, False if still blocked after max wait.
    """
    if not is_security_verification_screen(page, for_list_page=for_list_page):
        return True

    deadline = time.perf_counter() + max_wait_seconds
    wait_rounds = 0
    waited_seconds = 0.0

    while time.perf_counter() < deadline:
        wait_rounds += 1
        sleep_start = time.perf_counter()
        page.wait_for_timeout(int(poll_interval_seconds * 1000))
        waited_seconds += time.perf_counter() - sleep_start
        if not is_security_verification_screen(page, for_list_page=for_list_page):
            if accumulator is not None:
                accumulator.add(wait_count=wait_rounds, wait_seconds=waited_seconds)
            if wait_rounds > 0:
                print(
                    f"security verification cleared after {wait_rounds} poll(s), "
                    f"{waited_seconds:.1f}s",
                    flush=True,
                )
            return True

    if accumulator is not None:
        accumulator.add(wait_count=wait_rounds, wait_seconds=waited_seconds)
    print(
        f"security verification still present after {waited_seconds:.1f}s "
        f"({wait_rounds} polls)",
        flush=True,
    )
    return False
