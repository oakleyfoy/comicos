"""User-requested skips for LoCG browser detail capture (blocked parents, etc.)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


def normalize_detail_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    path = parsed.path.rstrip("/") or parsed.path
    host = (parsed.netloc or "").lower()
    if host:
        return f"{parsed.scheme or 'https'}://{host}{path}".lower()
    return text.rstrip("/").lower()


@dataclass
class UserSkipMatcher:
    urls: set[str] = field(default_factory=set)
    title_needles: list[str] = field(default_factory=list)

    def matches(self, url: str, title: str) -> bool:
        if normalize_detail_url(url) in self.urls:
            return True
        title_lower = (title or "").strip().lower()
        if not title_lower:
            return False
        return any(needle in title_lower for needle in self.title_needles)

    @classmethod
    def from_cli(cls, *, urls: list[str], titles: list[str]) -> UserSkipMatcher:
        normalized_urls = {normalize_detail_url(u) for u in urls if normalize_detail_url(u)}
        needles = [t.strip().lower() for t in titles if t and t.strip()]
        return cls(urls=normalized_urls, title_needles=needles)


def record_skipped_blocked_detail(
    counters: Any,
    *,
    url: str,
    title: str,
    reason: str = "skipped_blocked_detail",
) -> None:
    entry = {
        "url": url,
        "title": title,
        "reason": reason,
    }
    details = getattr(counters, "skipped_blocked_details", None)
    if details is None:
        counters.skipped_blocked_details = [entry]
    else:
        details.append(entry)
    counters.intentional_parent_skips = int(getattr(counters, "intentional_parent_skips", 0) or 0) + 1
    counts = counters.variant_skipped_reason_counts
    if not isinstance(counts, dict):
        counts = {}
        counters.variant_skipped_reason_counts = counts
    counts["skipped_blocked_detail"] = int(counts.get("skipped_blocked_detail") or 0) + 1


SkipMatcherFn = Callable[[str, str], bool]
