"""Normalize and dedupe advisor evidence strings (P90-06)."""

from __future__ import annotations

import re

_EVIDENCE_SPLIT = re.compile(r"\s*[·|;,]\s*|\s+/\s+")
_MAX_VISIBLE_EVIDENCE = 3


def split_evidence_segments(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in _EVIDENCE_SPLIT.split(raw) if p and p.strip()]
    return parts if parts else [raw]


def dedupe_evidence_segments(segments: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for segment in segments:
        text = re.sub(r"\s+", " ", (segment or "").strip())
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def dedupe_evidence_string(text: str) -> str:
    return " · ".join(dedupe_evidence_segments(split_evidence_segments(text)))


def format_evidence_for_display(
    text: str,
    *,
    max_visible: int = _MAX_VISIBLE_EVIDENCE,
) -> tuple[str, list[str], int]:
    """Return primary reason, supporting signals, and hidden overflow count."""
    unique = dedupe_evidence_segments(split_evidence_segments(text))
    if not unique:
        return "", [], 0
    primary = unique[0]
    visible_support = unique[1:max_visible]
    hidden = max(0, len(unique) - max_visible)
    return primary, visible_support, hidden
