from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

READINESS_TIMEOUT_MS = 2500
SELECTOR_PROBE_MS = 600
BODY_MIN_TEXT_CHARS = 400
NAVIGATION_TIMEOUT_MS = 60_000

_DETAIL_SELECTORS: tuple[tuple[str, str], ...] = (
    ("h1", "h1"),
    ("main", "main"),
    ("article", "article"),
    ("meta", 'meta[property="og:title"]'),
)

_LIST_SELECTORS: tuple[tuple[str, str], ...] = (
    ("comic-list", "#comic-list-issues"),
    ("comic-link", "a[href*='/comic/']"),
    ("releases-block", "#comic-list-block"),
)


def _try_selector(page: Page, selector: str, timeout_ms: int) -> bool:
    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
        return True
    except Exception:
        return False


def _body_has_content(page: Page, *, min_chars: int) -> bool:
    try:
        length = page.evaluate(
            "() => { const t = document.body && document.body.innerText ? document.body.innerText : ''; return t.length; }"
        )
        return bool(length and int(length) >= min_chars)
    except Exception:
        return False


def wait_for_detail_readiness(page: Page) -> tuple[bool, str, float]:
    """Short readiness probe; caller always continues to page.content() regardless."""
    started = time.perf_counter()
    for method, selector in _DETAIL_SELECTORS:
        if _try_selector(page, selector, SELECTOR_PROBE_MS):
            elapsed = round(time.perf_counter() - started, 3)
            return True, method, elapsed
    if _body_has_content(page, min_chars=BODY_MIN_TEXT_CHARS):
        elapsed = round(time.perf_counter() - started, 3)
        return True, "body", elapsed
    elapsed = round(time.perf_counter() - started, 3)
    return False, "none", elapsed


def wait_for_list_readiness(page: Page) -> tuple[bool, str, float]:
    started = time.perf_counter()
    deadline = started + (READINESS_TIMEOUT_MS / 1000.0)
    for method, selector in _LIST_SELECTORS:
        if time.perf_counter() >= deadline:
            break
        remaining_ms = max(200, int((deadline - time.perf_counter()) * 1000))
        if _try_selector(page, selector, min(SELECTOR_PROBE_MS, remaining_ms)):
            elapsed = round(time.perf_counter() - started, 3)
            return True, method, elapsed
    if _body_has_content(page, min_chars=BODY_MIN_TEXT_CHARS):
        elapsed = round(time.perf_counter() - started, 3)
        return True, "body", elapsed
    elapsed = round(time.perf_counter() - started, 3)
    return False, "none", elapsed
