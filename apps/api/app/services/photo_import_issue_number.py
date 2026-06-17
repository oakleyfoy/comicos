"""P100-13A — sanitize AI issue numbers (numeric comic identifiers only)."""

from __future__ import annotations

import re

_NOISE_PHRASES = {
    "?",
    "unknown",
    "none",
    "null",
    "n/a",
    "no issue number visible",
}

_PREFIX_RE = re.compile(r"^(no\.?\s*)", re.IGNORECASE)


def normalize_photo_issue_number(value: str | None) -> str | None:
    """Return a comic issue identifier string, or None if value is not a valid issue number."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in _NOISE_PHRASES:
        return None
    text = _PREFIX_RE.sub("", text).strip()
    text = re.sub(r"^#+\s*", "", text).strip()
    if not text:
        return None
    if not any(ch.isdigit() for ch in text):
        return None
    lower = text.lower()
    if "special collector" in lower or "no issue number" in lower:
        return None

    compact = text.replace(" ", "")
    if re.fullmatch(r"\d+", compact):
        return str(int(compact))
    if re.fullmatch(r"\d+/\d+", compact):
        left, right = compact.split("/", 1)
        return f"{int(left)}/{int(right)}"
    if re.fullmatch(r"\d+\.[A-Za-z]+", text):
        return text
    if re.fullmatch(r"\d+\.\d+", text):
        return text
    if re.fullmatch(r"\d+", text):
        return str(int(text))

    # Reject taglines / subtitles (words without a standalone issue token).
    if len(text.split()) > 1:
        return None
    return None


def apply_photo_issue_sanitization(book: dict[str, object]) -> dict[str, object]:
    """Normalize issue fields; move rejected issue text into subtitle / visible text."""
    out = dict(book)
    rejected_chunks: list[str] = []

    raw_issue = out.get("issue_number_guess")
    if raw_issue is not None and str(raw_issue).strip():
        sanitized = normalize_photo_issue_number(str(raw_issue))
        if sanitized:
            out["issue_number_guess"] = sanitized
        else:
            out["issue_number_guess"] = None
            rejected_chunks.append(str(raw_issue).strip())

    raw_visible_issue = out.get("visible_issue_text")
    if raw_visible_issue is not None and str(raw_visible_issue).strip():
        vis_san = normalize_photo_issue_number(str(raw_visible_issue))
        if vis_san:
            out["visible_issue_text"] = vis_san
        else:
            chunk = str(raw_visible_issue).strip()
            if chunk not in rejected_chunks:
                rejected_chunks.append(chunk)
            out["visible_issue_text"] = chunk

    for chunk in rejected_chunks:
        subtitle = str(out.get("subtitle_guess") or "").strip()
        if not subtitle:
            out["subtitle_guess"] = chunk
        elif chunk.lower() not in subtitle.lower():
            out["subtitle_guess"] = f"{subtitle} / {chunk}"
        uncertainty = str(out.get("uncertainty_reason") or "").strip()
        if not uncertainty:
            out["uncertainty_reason"] = "Issue number not visible."
        elif "issue number not visible" not in uncertainty.lower():
            out["uncertainty_reason"] = f"{uncertainty} Issue number not visible."

    return out
