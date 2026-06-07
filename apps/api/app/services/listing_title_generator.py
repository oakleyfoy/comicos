"""P89-03 rule-based marketplace listing titles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TitleInputs:
    series: str
    issue_number: str
    publisher: str
    year: str
    variant: str
    grade_label: str
    key_note: str
    marketplace: str


def _trim(text: str, max_len: int) -> str:
    t = " ".join(text.split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def generate_listing_title(inputs: TitleInputs) -> str:
    parts: list[str] = []
    series = inputs.series.strip()
    if series:
        parts.append(series)
    issue = inputs.issue_number.strip()
    if issue:
        parts.append(f"#{issue}" if not issue.startswith("#") else issue)
    if inputs.grade_label.strip():
        parts.append(inputs.grade_label.strip())
    variant = inputs.variant.strip()
    if variant and variant.lower() not in {"standard", "cover a", ""}:
        parts.append(variant)
    key = inputs.key_note.strip()
    if key:
        parts.append(key)
    pub = inputs.publisher.strip()
    if pub:
        parts.append(pub)
    year = inputs.year.strip()
    if year:
        parts.append(year)
    if inputs.marketplace.upper() == "EBAY" and "Comics" not in " ".join(parts):
        parts.append("Comics")
    title = " ".join(p for p in parts if p)
    limit = 80 if inputs.marketplace.upper() == "EBAY" else 120
    return _trim(title, limit)
