"""Canonical title keys for recommendation ↔ release index matching."""

from __future__ import annotations

import re
import unicodedata

from app.services.lunar_issue_identity import normalize_lunar_issue_number

_VARIANT_SUFFIX_RE = re.compile(r"\s*\(variants\)\s*$", re.I)
_VOLUME_IN_TITLE_RE = re.compile(
    r"\s+(?:vol\.?|volume|v)\s*(\d+)\s*(?:#|$)",
    re.I,
)
_TRAILING_VOLUME_RE = re.compile(r"\s+(?:vol\.?|volume|v)\s*\d+\s*$", re.I)


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_hash_format(text: str) -> str:
    """Collapse spacing around issue number markers."""
    out = normalize_whitespace(text)
    out = re.sub(r"\s*#\s*", " #", out)
    out = re.sub(r"#\s+(\d)", r"#\1", out)
    return out.strip()


def strip_variant_suffix(title: str) -> str:
    return _VARIANT_SUFFIX_RE.sub("", title or "").strip()


def strip_volume_suffix_from_series(series_part: str) -> str:
    return _TRAILING_VOLUME_RE.sub("", series_part or "").strip()


def normalize_recommendation_title_key(title: str) -> str:
    """Primary lookup key for release index and candidate title_key."""
    raw = strip_variant_suffix((title or "").strip())
    if not raw:
        return ""
    key = _ascii_fold(raw).lower()
    key = key.replace("–", "-").replace("—", "-")
    key = re.sub(r"[''`]", "'", key)
    key = normalize_hash_format(key)
    key = re.sub(r"\s*([,.;:!?])\s*", r"\1", key)
    return key.strip()


def title_key_aliases(title: str) -> tuple[str, ...]:
    """Extra keys that should resolve to the same release row."""
    primary = normalize_recommendation_title_key(title)
    if not primary:
        return ()
    aliases: list[str] = []
    seen = {primary}

    def add(key: str) -> None:
        k = key.strip()
        if k and k not in seen:
            seen.add(k)
            aliases.append(k)

    if " #" in primary:
        series_part, issue_part = primary.split(" #", 1)
        bare_series = strip_volume_suffix_from_series(series_part)
        if bare_series != series_part:
            add(f"{bare_series} #{issue_part}")
        no_punct_series = re.sub(r"[^\w\s#/-]", "", series_part).strip()
        no_punct_series = re.sub(r"\s+", " ", no_punct_series)
        if no_punct_series and no_punct_series != series_part:
            add(f"{no_punct_series} #{issue_part}")
    add(re.sub(r"[^\w\s#/-]", "", primary))
    return tuple(aliases)


def normalize_issue_number_for_match(issue_number: str | None) -> str | None:
    if issue_number is None:
        return None
    raw = normalize_whitespace(issue_number)
    if not raw:
        return None
    return normalize_lunar_issue_number(raw.lstrip("#"))


def normalize_series_name_for_match(series_name: str) -> str:
    name = normalize_whitespace(_ascii_fold(series_name or ""))
    name = strip_volume_suffix_from_series(name)
    return name.lower().strip()


def display_title_key(*, series_name: str, issue_number: str) -> str:
    series = normalize_whitespace(series_name)
    issue = normalize_issue_number_for_match(issue_number) or normalize_whitespace(issue_number)
    return normalize_recommendation_title_key(f"{series} #{issue}")


def parse_normalized_display_title(title: str) -> tuple[str, str | None]:
    """Parse series / issue from a recommendation title after normalization."""
    key = normalize_recommendation_title_key(title)
    if " #" not in key:
        if "#" in key:
            series, issue = key.split("#", 1)
            return series.strip(), (issue.strip() or None)
        return key, None
    series, issue = key.split(" #", 1)
    return series.strip(), (issue.strip() or None)
