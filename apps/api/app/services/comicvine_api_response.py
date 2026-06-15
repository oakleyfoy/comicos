"""ComicVine JSON API envelope parsing (status_code, limits, errors)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

# List endpoints: limit defaults to 100 and cannot exceed 100. Search: max 10.
COMICVINE_LIST_PAGE_MAX = 100
COMICVINE_SEARCH_PAGE_MAX = 10

COMICVINE_STATUS_OK = 1
COMICVINE_STATUS_INVALID_API_KEY = 100
COMICVINE_STATUS_NOT_FOUND = 101
COMICVINE_STATUS_URL_FORMAT = 102
COMICVINE_STATUS_JSONP = 103
COMICVINE_STATUS_FILTER_ERROR = 104
COMICVINE_STATUS_SUBSCRIBER_ONLY = 105

_STATUS_LABELS: dict[int, str] = {
    COMICVINE_STATUS_OK: "OK",
    COMICVINE_STATUS_INVALID_API_KEY: "Invalid API Key",
    COMICVINE_STATUS_NOT_FOUND: "Object Not Found",
    COMICVINE_STATUS_URL_FORMAT: "Error in URL Format",
    COMICVINE_STATUS_JSONP: "'jsonp' format requires a 'json_callback' argument",
    COMICVINE_STATUS_FILTER_ERROR: "Filter Error",
    COMICVINE_STATUS_SUBSCRIBER_ONLY: "Subscriber only video is for subscribers only",
}


class ComicVineApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def comicvine_status_code(payload: dict[str, Any]) -> int:
    raw = payload.get("status_code")
    if raw is None:
        # Legacy/alternate payloads sometimes only expose error text.
        if str(payload.get("error") or "").upper() == "OK":
            return COMICVINE_STATUS_OK
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def parse_comicvine_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload when status_code is OK (1); raise ComicVineApiError otherwise."""
    code = comicvine_status_code(payload)
    if code == COMICVINE_STATUS_OK:
        return payload
    label = _STATUS_LABELS.get(code) or str(payload.get("error") or "ComicVine API error")
    if code == COMICVINE_STATUS_INVALID_API_KEY:
        label = "Invalid API Key — check COMICVINE_API_KEY"
    raise ComicVineApiError(f"ComicVine API: {label}", status_code=code or None)


def clamp_page_limit(limit: int, *, path: str) -> int:
    normalized = path.strip("/").split("/")[0].lower()
    cap = COMICVINE_SEARCH_PAGE_MAX if normalized == "search" else COMICVINE_LIST_PAGE_MAX
    return max(1, min(int(limit), cap))


def comicvine_best_cover_url(image: Any) -> str | None:
    if isinstance(image, str) and image.strip():
        return image.strip()
    if not isinstance(image, dict):
        return None
    for key in (
        "super_url",
        "screen_large_url",
        "screen_url",
        "medium_url",
        "small_url",
        "thumb_url",
        "icon_url",
        "original_url",
    ):
        url = image.get(key)
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def payload_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def parse_comicvine_date(value: Any) -> date | None:
    """Parse ComicVine date or datetime strings into a calendar date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def comicvine_issue_dates_from_row(row: dict[str, Any]) -> tuple[date | None, date | None, date | None]:
    cover_date = parse_comicvine_date(row.get("cover_date"))
    store_date = parse_comicvine_date(row.get("store_date"))
    release_date = parse_comicvine_date(row.get("release_date"))
    if release_date is None:
        release_date = parse_comicvine_date(row.get("date_added"))
    return cover_date, store_date, release_date
