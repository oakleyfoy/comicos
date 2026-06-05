from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

LOCG_BASE_URL = "https://leagueofcomicgeeks.com"
LOCG_SOURCE_NAME = "LEAGUE_OF_COMIC_GEEKS"
LOCG_USER_AGENT = (
    "ComicOS-ExternalCatalog/1.0 (+https://github.com/oakleyfoy/comicos; catalog-sync; contact=ops)"
)
LOCG_REQUEST_DELAY_SECONDS = 1.5
LOCG_MAX_DETAIL_PAGES_PER_RUN = 500
LOCG_HTTP_TIMEOUT_SECONDS = 30.0
LOCG_MAX_RETRIES = 3
LOCG_RETRY_BACKOFF_SECONDS = 2.0

# Primary calendar path used by LoCG new-comics week pages (may change; parser tolerates fixtures).
LOCG_NEW_COMICS_PATH_TEMPLATE = "/comics/new-comics/{date}"


class LocgHttpError(Exception):
    pass


class LocgAccessBlockedError(LocgHttpError):
    pass


@dataclass
class LocgListIssueStub:
    title: str
    publisher: str
    release_date: date | None
    price: float | None
    source_url: str
    cover_image_url: str | None
    variant_count: int | None
    foc_date: date | None


@dataclass
class LocgListVariantRowStub:
    """Variant row from release calendar list HTML (data-parent != 0)."""

    variant_comic_id: str
    parent_comic_id: str
    title: str
    variant_name: str
    publisher: str
    source_url: str
    parent_source_url: str
    cover_image_url: str | None
    price: float | None
    release_date: date | None


@dataclass
class LocgHttpClient:
    delay_seconds: float = LOCG_REQUEST_DELAY_SECONDS
    user_agent: str = LOCG_USER_AGENT
    timeout_seconds: float = LOCG_HTTP_TIMEOUT_SECONDS
    max_retries: int = LOCG_MAX_RETRIES
    _last_request_at: float = field(default=0.0, repr=False)
    _client: httpx.Client | None = field(default=None, repr=False)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _sleep_if_needed(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    def get_text(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._sleep_if_needed()
            try:
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=self.timeout_seconds,
                        headers={"User-Agent": self.user_agent, "Accept": "text/html,application/json"},
                        follow_redirects=True,
                    )
                response = self._client.get(url)
                self._last_request_at = time.monotonic()
                if response.status_code in {401, 403, 429}:
                    raise LocgAccessBlockedError(f"access blocked ({response.status_code}) for {url}")
                if response.status_code >= 500:
                    raise LocgHttpError(f"server error {response.status_code} for {url}")
                if response.status_code == 404:
                    return ""
                response.raise_for_status()
                return response.text
            except (httpx.HTTPError, LocgHttpError) as exc:
                last_error = exc
                if isinstance(exc, LocgAccessBlockedError):
                    raise
                time.sleep(LOCG_RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise LocgHttpError(f"failed to fetch {url}: {last_error}") from last_error


def _parse_date_value(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    cleaned = str(value).strip()
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            if fmt == "%Y-%m-%d":
                return date.fromisoformat(cleaned[:10])
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    iso = re.search(r"(\d{4}-\d{2}-\d{2})", cleaned)
    if iso:
        return date.fromisoformat(iso.group(1))
    return None


def _extract_json_script(html: str, script_id: str) -> dict[str, Any] | None:
    pattern = rf'<script[^>]+id="{re.escape(script_id)}"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None


def _abs_url(href: str, *, base: str = LOCG_BASE_URL) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return urljoin(base, href)


def _issue_id_from_url(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if "comic" in parts:
        idx = parts.index("comic")
        if idx + 1 < len(parts) and parts[idx + 1].isdigit():
            return parts[idx + 1]
    return None


class _LocgCardParser(HTMLParser):
    def __init__(self, *, default_release_date: date | None) -> None:
        super().__init__()
        self.default_release_date = default_release_date
        self.cards: list[LocgListIssueStub] = []
        self._in_card = False
        self._current: dict[str, Any] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        if tag == "article" and "locg-release-card" in attr.get("class", ""):
            self._in_card = True
            self._current = {
                "title": attr.get("data-title", ""),
                "publisher": attr.get("data-publisher", ""),
                "source_url": _abs_url(attr.get("data-issue-url", attr.get("href", ""))),
                "cover_image_url": attr.get("data-cover-image", ""),
                "variant_count": attr.get("data-variant-count"),
                "foc_date": attr.get("data-foc-date"),
                "price": attr.get("data-price"),
                "release_date": attr.get("data-release-date") or self.default_release_date,
            }
        if self._in_card and tag == "a" and attr.get("href", "").startswith("/comic/"):
            if not self._current.get("source_url"):
                self._current["source_url"] = _abs_url(attr["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self._in_card:
            title = (self._current.get("title") or "").strip()
            url = (self._current.get("source_url") or "").strip()
            if title and url:
                self.cards.append(
                    LocgListIssueStub(
                        title=title,
                        publisher=(self._current.get("publisher") or "").strip(),
                        release_date=_parse_date_value(self._current.get("release_date")),
                        price=_parse_price_stub(self._current.get("price")),
                        source_url=url,
                        cover_image_url=(self._current.get("cover_image_url") or "").strip() or None,
                        variant_count=_parse_int_stub(self._current.get("variant_count")),
                        foc_date=_parse_date_value(self._current.get("foc_date")),
                    )
                )
            self._in_card = False
            self._current = {}


def _parse_price_stub(value: Any) -> float | None:
    if value is None:
        return None
    cleaned = str(value).replace("$", "").strip()
    try:
        parsed = float(cleaned)
        return parsed if parsed > 0 else None
    except ValueError:
        return None


def _parse_int_stub(value: Any) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else None


def parse_release_date_page(html: str, *, page_date: date | None = None) -> list[LocgListIssueStub]:
    if not html.strip():
        return []
    payload = _extract_json_script(html, "locg-release-calendar")
    if payload and isinstance(payload.get("issues"), list):
        stubs: list[LocgListIssueStub] = []
        for row in payload["issues"]:
            if not isinstance(row, dict):
                continue
            url = _abs_url(str(row.get("source_url") or row.get("url") or ""))
            title = str(row.get("title") or "").strip()
            if not title or not url:
                continue
            stubs.append(
                LocgListIssueStub(
                    title=title,
                    publisher=str(row.get("publisher") or "").strip(),
                    release_date=_parse_date_value(row.get("release_date")) or page_date,
                    price=_parse_price_stub(row.get("price")),
                    source_url=url,
                    cover_image_url=str(row.get("cover_image_url") or "").strip() or None,
                    variant_count=_parse_int_stub(row.get("variant_count")),
                    foc_date=_parse_date_value(row.get("foc_date")),
                )
            )
        return stubs

    parser = _LocgCardParser(default_release_date=page_date)
    parser.feed(html)
    if parser.cards:
        return parser.cards

    # Fallback: anchor tags to comic detail pages with nearby title text.
    stubs = []
    for match in re.finditer(
        r'<a[^>]+href="(/comic/\d+[^"]*)"[^>]*>([^<]{2,200})</a>',
        html,
        re.IGNORECASE,
    ):
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if not title:
            continue
        stubs.append(
            LocgListIssueStub(
                title=title,
                publisher="",
                release_date=page_date,
                price=None,
                source_url=_abs_url(match.group(1)),
                cover_image_url=None,
                variant_count=None,
                foc_date=None,
            )
        )
    return stubs


def _finalize_issue_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.external_catalog.normalization import coalesce_issue_image_urls

    return coalesce_issue_image_urls(payload)


def parse_issue_detail_page(html: str) -> dict[str, Any]:
    if not html.strip():
        return {}
    payload = _extract_json_script(html, "locg-issue-data")
    if payload:
        return _finalize_issue_payload(payload)

    def _meta(prop: str) -> str | None:
        m = re.search(
            rf'<meta[^>]+property="{re.escape(prop)}"[^>]+content="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else None

    title = _meta("og:title") or ""
    if not title:
        h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
        if h1:
            title = h1.group(1).strip()

    pull_m = re.search(r'data-pull-count="(\d+)"', html) or re.search(
        r"Pulls?:\s*([0-9,]+)", html, re.IGNORECASE
    )
    want_m = re.search(r'data-want-count="(\d+)"', html) or re.search(
        r"Wants?:\s*([0-9,]+)", html, re.IGNORECASE
    )

    creators: list[dict[str, str]] = []
    for block in re.finditer(
        r'<li[^>]+class="[^"]*locg-creator[^"]*"[^>]*data-name="([^"]*)"[^>]*data-role="([^"]*)"',
        html,
        re.IGNORECASE,
    ):
        creators.append({"creator_name": block.group(1).strip(), "role": block.group(2).strip()})

    variants: list[dict[str, Any]] = []
    for block in re.finditer(
        r'<div[^>]+class="[^"]*locg-variant[^"]*"[^>]*data-cover="([^"]*)"[^>]*data-variant="([^"]*)"',
        html,
        re.IGNORECASE,
    ):
        variants.append(
            {
                "cover_label": block.group(1).strip() or None,
                "variant_name": block.group(2).strip() or None,
            }
        )

    result: dict[str, Any] = {
        "title": title,
        "publisher": _field(html, "publisher"),
        "release_date": _parse_date_value(_field(html, "release_date")),
        "foc_date": _parse_date_value(_field(html, "foc_date")),
        "cover_date": _parse_date_value(_field(html, "cover_date")),
        "price": _parse_price_stub(_field(html, "price")),
        "description": _field(html, "description"),
        "pull_count": int(pull_m.group(1).replace(",", "")) if pull_m else None,
        "want_count": int(want_m.group(1).replace(",", "")) if want_m else None,
        "variant_count": len(variants) if variants else None,
        "cover_image_url": _field(html, "cover_image_url"),
        "thumbnail_url": _field(html, "thumbnail_url"),
        "high_resolution_image_url": _field(html, "high_resolution_image_url"),
        "og_image": _meta("og:image"),
        "creators": creators,
        "variants": variants,
        "source_url": None,
    }
    finalized = _finalize_issue_payload(result)
    if finalized.get("pull_count") is None and "comic-details" in html:
        from app.services.external_catalog.locg_live_html import enrich_issue_detail_from_live_html

        finalized = enrich_issue_detail_from_live_html(html, finalized)
        finalized = _finalize_issue_payload(finalized)
    return finalized


def _field(html: str, name: str) -> str | None:
    m = re.search(rf'data-{re.escape(name)}="([^"]*)"', html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(rf"<[^>]+data-{re.escape(name)}[^>]*>([^<]+)<", html, re.IGNORECASE)
    return m.group(1).strip() if m else None


def normalize_locg_issue(raw: dict[str, Any]) -> dict[str, Any]:
    from app.services.external_catalog.normalization import normalize_locg_issue as _norm

    return _norm(raw, source_name=LOCG_SOURCE_NAME).__dict__


def calendar_url_for_date(d: date) -> str:
    return urljoin(LOCG_BASE_URL, LOCG_NEW_COMICS_PATH_TEMPLATE.format(date=d.isoformat()))


def fetch_release_date_page(
    page_date: date,
    *,
    client: LocgHttpClient | None = None,
    html_override: str | None = None,
) -> str:
    if html_override is not None:
        return html_override
    owns = client or LocgHttpClient()
    try:
        return owns.get_text(calendar_url_for_date(page_date))
    finally:
        if client is None:
            owns.close()


def fetch_issue_detail_page(
    issue_url: str,
    *,
    client: LocgHttpClient | None = None,
    html_override: str | None = None,
) -> str:
    if html_override is not None:
        return html_override
    owns = client or LocgHttpClient()
    try:
        return owns.get_text(issue_url)
    finally:
        if client is None:
            owns.close()


def discover_available_release_dates(
    start_date: date,
    *,
    max_months: int = 6,
    client: LocgHttpClient | None = None,
    through_farthest_available: bool = False,
) -> list[date]:
    """Walk weekly (Wednesday) release pages; include dates that return parseable content."""
    owns = client or LocgHttpClient()
    dates: list[date] = []
    cursor = start_date
    # Align to Wednesday (US new comics day).
    while cursor.weekday() != 2:
        cursor += timedelta(days=1)
    end_cap = start_date + timedelta(days=max_months * 31)
    empty_streak = 0
    try:
        while cursor <= end_cap:
            html = owns.get_text(calendar_url_for_date(cursor))
            stubs = parse_release_date_page(html, page_date=cursor)
            if stubs:
                dates.append(cursor)
                empty_streak = 0
            else:
                empty_streak += 1
                if not through_farthest_available and empty_streak >= 4:
                    break
                if through_farthest_available and empty_streak >= 8:
                    break
            cursor += timedelta(days=7)
    finally:
        if client is None:
            owns.close()
    return dates


def stub_to_detail_seed(stub: LocgListIssueStub) -> dict[str, Any]:
    return {
        "title": stub.title,
        "publisher": stub.publisher,
        "release_date": stub.release_date,
        "foc_date": stub.foc_date,
        "price": stub.price,
        "cover_image_url": stub.cover_image_url,
        "variant_count": stub.variant_count,
        "source_url": stub.source_url,
        "source_issue_id": _issue_id_from_url(stub.source_url),
    }


def merge_detail_into_seed(seed: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    merged = dict(seed)
    for key, value in detail.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        merged[key] = value
    if not merged.get("source_url") and detail.get("source_url"):
        merged["source_url"] = detail["source_url"]
    if not merged.get("source_issue_id") and merged.get("source_url"):
        merged["source_issue_id"] = _issue_id_from_url(str(merged["source_url"]))
    return merged
