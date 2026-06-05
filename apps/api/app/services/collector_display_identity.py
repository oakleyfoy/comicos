"""Canonical collector-facing issue titles (display only; no scoring impact)."""

from __future__ import annotations

import re
from datetime import date

from sqlmodel import Session

from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_catalog_quality import parse_recommendation_display_title

_VOLUME_TRAILING_RE = re.compile(r"^(.*?)\s+(?:vol\.?|volume|v)\s*(\d+)\s*$", re.I)
_VOLUME_EMBEDDED_RE = re.compile(r"\s+(?:vol\.?|volume|v)\s*(\d+)\b", re.I)
_YEAR_PAREN_RE = re.compile(r"\((20\d{2})\)")


def parse_series_volume(series_name: str) -> tuple[str, int | None]:
    name = (series_name or "").strip()
    if not name:
        return "", None
    m = _VOLUME_TRAILING_RE.match(name)
    if m:
        return (m.group(1).strip() or name), int(m.group(2))
    m2 = _VOLUME_EMBEDDED_RE.search(name)
    if m2:
        base = name[: m2.start()].strip()
        return (base or name), int(m2.group(1))
    return name, None


def _year_from_text(*parts: str | None) -> int | None:
    for part in parts:
        if not part:
            continue
        m = _YEAR_PAREN_RE.search(part)
        if m:
            return int(m.group(1))
    return None


def strip_year_parens(series_name: str) -> str:
    return re.sub(r"\s*\(20\d{2}\)\s*", " ", series_name or "").strip()


def split_series_and_issue(title: str, issue_number: str | None = None) -> tuple[str, str]:
    explicit = (issue_number or "").strip().lstrip("#")
    series, parsed = parse_recommendation_display_title(title or "")
    if explicit:
        if series:
            return series, explicit
        return (title or "Unknown").strip(), explicit
    if parsed:
        return series, parsed
    return (title or "Unknown").strip(), ""


def format_collector_issue_display(
    *,
    series_name: str,
    issue_number: str,
    title: str | None = None,
    release_date: date | None = None,
) -> str:
    """Prefer Vol N, else (start year), else full series name + issue."""
    series = (series_name or "").strip()
    issue = (issue_number or "").strip().lstrip("#")
    if not issue:
        return series or (title or "").strip() or "Unknown"

    base, vol = parse_series_volume(series)
    if vol is None and title:
        _, vol_title = parse_series_volume(title)
        if vol_title is not None:
            vol = vol_title
            if not base or base == series:
                base_from_title, _ = parse_series_volume(title)
                if base_from_title:
                    base = base_from_title

    year = release_date.year if release_date else None
    if year is None:
        year = _year_from_text(series, title)

    display_series = base if vol is not None else strip_year_parens(series)
    if not display_series:
        display_series = series or "Unknown"

    if vol is not None:
        return f"{display_series} Vol {vol} #{issue}"
    if year is not None:
        return f"{display_series} ({year}) #{issue}"
    return f"{display_series} #{issue}"


def format_from_release(*, series: ReleaseSeries, issue: ReleaseIssue) -> str:
    retail_date = issue.original_release_date or issue.release_date
    return format_collector_issue_display(
        series_name=series.series_name,
        issue_number=issue.issue_number,
        title=issue.title,
        release_date=retail_date,
    )


def resolve_collector_display_title(
    session: Session | None,
    *,
    release_issue_id: int | None = None,
    external_catalog_issue_id: int | None = None,
    title: str = "",
    issue_number: str = "",
    publisher: str = "",
    release_date: date | None = None,
) -> str:
    if session is not None and release_issue_id:
        issue = session.get(ReleaseIssue, release_issue_id)
        if issue is not None:
            series = session.get(ReleaseSeries, issue.series_id)
            if series is not None:
                return format_from_release(series=series, issue=issue)

    if session is not None and external_catalog_issue_id:
        ext = session.get(ExternalCatalogIssue, external_catalog_issue_id)
        if ext is not None:
            return format_collector_issue_display(
                series_name=ext.series_name,
                issue_number=ext.issue_number or issue_number,
                title=ext.title or ext.issue_title or title,
                release_date=ext.release_date or release_date,
            )

    series, issue = split_series_and_issue(title, issue_number)
    if publisher and series == title and not issue_number:
        series = title
    return format_collector_issue_display(
        series_name=series,
        issue_number=issue or issue_number,
        title=title,
        release_date=release_date,
    )
