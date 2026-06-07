"""P88-02 candidate eBay search queries from buy opportunities."""

from __future__ import annotations

import re

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity

_ISSUE_RE = re.compile(r"^#?\s*(\d+[A-Za-z0-9.-]*)$")
_WS_RE = re.compile(r"\s+")


def _normalize_issue(issue: str) -> str:
    raw = (issue or "").strip()
    if not raw:
        return ""
    if raw.startswith("#"):
        return raw
    if raw.isdigit() or re.match(r"^\d+[A-Za-z]", raw):
        return f"#{raw}"
    return raw


def _normalize_query(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"[\"'`]", "", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned)
    return cleaned


def _issue_notation_variants(series: str, issue: str) -> list[str]:
    series = _normalize_query(series)
    issue_norm = _normalize_issue(issue)
    if not series and not issue_norm:
        return []
    queries: list[str] = []
    if series and issue_norm:
        queries.append(_normalize_query(f"{series} {issue_norm}"))
        queries.append(_normalize_query(f"{series} {issue_norm.lstrip('#')}"))
        match = _ISSUE_RE.match(issue_norm)
        if match:
            num = match.group(1)
            queries.append(_normalize_query(f"{series} #{num}"))
    elif series:
        queries.append(series)
    return queries


def candidate_searches_for_opportunity(opp: MarketplaceAcquisitionOpportunity) -> list[str]:
    """Build deduplicated search strings for live marketplace lookup."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(q: str) -> None:
        n = _normalize_query(q)
        if not n:
            return
        key = n.lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(n)

    title = _normalize_query(opp.title or "")
    series = _normalize_query(opp.series or "")
    issue = (opp.issue or "").strip()
    variant = _normalize_query(opp.variant or "")
    publisher = _normalize_query(opp.publisher or "")

    for q in _issue_notation_variants(series, issue):
        add(q)
        if variant:
            add(f"{q} {variant}")

    if title:
        add(title)
        if issue:
            add(f"{title} {_normalize_issue(issue)}")
        if variant:
            add(f"{title} {variant}")

    if series and not issue and title and title.lower() != series.lower():
        add(series)

    if publisher and series and issue:
        add(f"{publisher} {series} {_normalize_issue(issue)}")

    return ordered
