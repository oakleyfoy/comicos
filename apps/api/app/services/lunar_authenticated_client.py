from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin

import httpx

from app.services.lunar_credentials import require_lunar_credentials

LUNAR_BASE_URL = "https://www.lunardistribution.com"
LUNAR_RESOURCES_PATH = "/home/resources"
LUNAR_LOGIN_PAGE_PATH = "/home/login"
LUNAR_LOGIN_POST_PATH = "/account/login"

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

PERIOD_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
    re.IGNORECASE,
)
HREF_PERIOD_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)-(\d{4})",
    re.IGNORECASE,
)
LUNAR_PRODUCT_DOWNLOAD_RE = re.compile(
    r'href="(/home/productdatadownload\?prefix=(\d{4})([^"]*))"',
    re.IGNORECASE,
)
LUNAR_PREFIX_RE = re.compile(r"^\d{4}$")


class LunarAuthenticationError(Exception):
    pass


class LunarResourceNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class LunarCsvLink:
    period_label: str
    period_key: str
    link_text: str
    href: str
    file_type: str


@dataclass(frozen=True)
class LunarDownloadedCsv:
    file_name: str
    file_period: str
    file_type: str
    content_bytes: bytes
    downloaded_at: datetime
    source_url: str


def period_key_from_label(label: str) -> str | None:
    match = PERIOD_RE.search(label)
    if not match:
        return None
    month = MONTHS.get(match.group(1).lower())
    if month is None:
        return None
    return f"{match.group(2)}-{month:02d}"


def period_from_lunar_prefix(prefix: str) -> tuple[str, str]:
    if not LUNAR_PREFIX_RE.match(prefix):
        return "", ""
    month = int(prefix[:2])
    year = 2000 + int(prefix[2:])
    if month < 1 or month > 12:
        return "", ""
    month_name = next(name.title() for name, idx in MONTHS.items() if idx == month)
    period_label = f"{month_name} {year}"
    return period_label, f"{year}-{month:02d}"


def _parse_product_download_links(html: str, *, base_url: str) -> list[LunarCsvLink]:
    discovered: list[LunarCsvLink] = []
    seen: set[tuple[str, str]] = set()
    for match in LUNAR_PRODUCT_DOWNLOAD_RE.finditer(html):
        href_path = match.group(1).replace("&amp;", "&")
        prefix = match.group(2)
        extras = match.group(3).lower()
        if "format=" in extras:
            continue
        is_related = "includerelated=true" in extras.replace(" ", "")
        file_type = "LUNAR_FORMAT_WITH_RELATED" if is_related else "LUNAR_FORMAT"
        dedupe_key = (prefix, file_type)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        period_label, period_key = period_from_lunar_prefix(prefix)
        if not period_key:
            continue
        link_text = (
            "Lunar Format Product File With Related Products"
            if is_related
            else "Lunar Format Product File"
        )
        discovered.append(
            LunarCsvLink(
                period_label=period_label,
                period_key=period_key,
                link_text=link_text,
                href=urljoin(base_url, href_path),
                file_type=file_type,
            )
        )
    return discovered


class _ResourcesPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str, str]] = []
        self._current_period_label = ""
        self._current_period_key = ""
        self._in_heading = False
        self._heading_parts: list[str] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"h2", "h3", "h4"}:
            self._in_heading = True
            self._heading_parts = []
            return
        if lowered != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_parts.append(data)
            return
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"h2", "h3", "h4"}:
            heading_text = " ".join(part.strip() for part in self._heading_parts if part.strip())
            period_match = PERIOD_RE.search(heading_text)
            if period_match:
                self._current_period_label = period_match.group(0)
                self._current_period_key = period_key_from_label(self._current_period_label) or ""
            self._in_heading = False
            self._heading_parts = []
            return
        if lowered != "a" or self._current_href is None:
            return
        text = " ".join(part.strip() for part in self._text_parts if part.strip())
        self.links.append((self._current_href, text, self._current_period_label, self._current_period_key))
        self._current_href = None
        self._text_parts = []


def _period_from_href(href: str) -> tuple[str, str]:
    match = HREF_PERIOD_RE.search(href.replace("_", "-"))
    if not match:
        return "", ""
    month_name = match.group(1).title()
    year = match.group(2)
    period_label = f"{month_name} {year}"
    period_key = period_key_from_label(period_label) or ""
    return period_label, period_key


def parse_monthly_csv_links(html: str, *, base_url: str = LUNAR_BASE_URL) -> list[LunarCsvLink]:
    discovered = _parse_product_download_links(html, base_url=base_url)
    if discovered:
        return discovered

    parser = _ResourcesPageParser()
    parser.feed(html)
    discovered: list[LunarCsvLink] = []

    for href, text, section_period_label, section_period_key in parser.links:
        if not href.lower().endswith(".csv"):
            continue
        normalized_text = text.lower()
        if "lunar format" not in normalized_text or "product file" not in normalized_text:
            continue
        file_type = "LUNAR_FORMAT_WITH_RELATED" if "related" in normalized_text else "LUNAR_FORMAT"
        period_label = section_period_label
        period_key = section_period_key
        if not period_key:
            period_match = PERIOD_RE.search(text)
            if period_match:
                period_label = period_match.group(0)
                period_key = period_key_from_label(period_label) or ""
        if not period_key:
            href_label, href_key = _period_from_href(href)
            period_label = href_label or period_label
            period_key = href_key
        if not period_key:
            continue
        discovered.append(
            LunarCsvLink(
                period_label=period_label,
                period_key=period_key,
                link_text=text.strip(),
                href=urljoin(base_url, href),
                file_type=file_type,
            )
        )
    return discovered


def select_latest_period_link(
    links: list[LunarCsvLink],
    *,
    file_type: str = "LUNAR_FORMAT",
    period: str | None = None,
) -> LunarCsvLink:
    filtered = [link for link in links if link.file_type == file_type]
    if period is not None:
        matches = [link for link in filtered if link.period_key == period]
        if not matches:
            raise LunarResourceNotFoundError(f"No Lunar CSV link found for period {period}")
        return matches[0]
    if not filtered:
        raise LunarResourceNotFoundError("No Lunar Format Product File CSV links found")
    return sorted(filtered, key=lambda row: row.period_key, reverse=True)[0]


class LunarAuthenticatedClient:
    def __init__(
        self,
        *,
        base_url: str = LUNAR_BASE_URL,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(base_url=self.base_url, follow_redirects=True, transport=transport, timeout=60.0)
            self._owns_client = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> LunarAuthenticatedClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def login(self, *, username: str | None = None, password: str | None = None) -> None:
        if username is None or password is None:
            username, password = require_lunar_credentials()
        login_page = self._client.get(LUNAR_LOGIN_PAGE_PATH)
        login_page.raise_for_status()
        token_match = re.search(
            r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"',
            login_page.text,
        )
        if not token_match:
            raise LunarAuthenticationError("Lunar login anti-forgery token not found")
        response = self._client.post(
            LUNAR_LOGIN_POST_PATH,
            data={
                "__RequestVerificationToken": token_match.group(1),
                "Username": username,
                "Password": password,
            },
        )
        response.raise_for_status()
        response_text_lower = response.text.lower()
        if "invalid login" in response_text_lower:
            raise LunarAuthenticationError("Lunar login failed")
        if "/home/login" in str(response.url).lower() and "invalid" in response_text_lower:
            raise LunarAuthenticationError("Lunar login failed")

    def fetch_resources_html(self, *, resources_path: str = LUNAR_RESOURCES_PATH) -> str:
        response = self._client.get(resources_path)
        response.raise_for_status()
        if "/home/login" in str(response.url).lower():
            raise LunarAuthenticationError("Lunar session is not authenticated")
        return response.text

    def download_csv(self, link: LunarCsvLink) -> LunarDownloadedCsv:
        href = link.href
        if href.startswith(self.base_url):
            request_path = href[len(self.base_url) :]
        else:
            request_path = href
        response = self._client.get(request_path)
        response.raise_for_status()
        file_name = href.rsplit("/", 1)[-1] or f"lunar-{link.period_key}.csv"
        if "productdatadownload" in href.lower():
            file_name = f"lunar-{link.period_key}-{link.file_type.lower()}.csv"
        return LunarDownloadedCsv(
            file_name=file_name,
            file_period=link.period_key,
            file_type=link.file_type,
            content_bytes=response.content,
            downloaded_at=datetime.now(timezone.utc),
            source_url=link.href,
        )

    def download_product_csv(
        self,
        *,
        period: str | None = None,
        with_related_products: bool = False,
        resources_path: str = LUNAR_RESOURCES_PATH,
    ) -> LunarDownloadedCsv:
        html = self.fetch_resources_html(resources_path=resources_path)
        links = parse_monthly_csv_links(html, base_url=self.base_url)
        file_type = "LUNAR_FORMAT_WITH_RELATED" if with_related_products else "LUNAR_FORMAT"
        link = select_latest_period_link(links, file_type=file_type, period=period)
        return self.download_csv(link)


def authenticated_client_factory() -> Callable[[], LunarAuthenticatedClient]:
    return LunarAuthenticatedClient
