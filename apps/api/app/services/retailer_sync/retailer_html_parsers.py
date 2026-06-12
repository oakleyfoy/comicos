"""Retailer saved-order HTML parser registry.

Each retailer exposes a parser that turns saved order HTML into the shared
:class:`RetailerOrderDetail` normalized form. The shared upload/review/confirm
pipeline (see ``retailer_html_import``) is identical across retailers; only the
``parse`` step is retailer-specific.

Implementation status:
  * ``midtown``      -> fully supported (delegates to the proven Midtown parser)
  * ``dcbs``         -> beta (generic heuristics until a sample HTML is supplied)
  * ``third_eye``    -> beta (generic heuristics until a sample HTML is supplied)
  * ``mycomicshop``  -> beta (generic heuristics until a sample HTML is supplied)
  * ``unknown``      -> generic heuristic parser for any saved order page
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.services.retailer_sync.midtown_parser import (
    MidtownOrderNumberError,
    parse_midtown_order_detail,
)
from app.services.retailer_sync.retailer_html_common import (
    RetailerHtmlImportError,
    RetailerHtmlPageDiagnostics,
    RetailerOrderDetail,
    RetailerOrderItem,
)

_VISIBLE_TEXT_EXCERPT_LIMIT = 5000
_PRICE_RE = re.compile(r"\$\s*([0-9]{1,5}(?:\.[0-9]{2}))")
_ORDER_NUMBER_RE = re.compile(
    r"\b(?:order|invoice|confirmation|order\s*number|order\s*#)\s*[#:]?\s*([A-Za-z0-9][A-Za-z0-9_-]{2,40})",
    flags=re.IGNORECASE,
)
_ORDER_HASH_LINK_RE = re.compile(r"order\s*#", flags=re.IGNORECASE)
_QTY_LABEL_RE = re.compile(r"\b(?:qty|quantity)\b\s*[:x]?\s*(\d{1,3})", flags=re.IGNORECASE)
_DATE_PATTERNS = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%m/%d/%y")
_PUBLISHER_HINTS = (
    "marvel",
    "dc comics",
    "dc",
    "image",
    "image comics",
    "idw",
    "idw publishing",
    "dark horse",
    "boom",
    "boom! studios",
    "dynamite",
    "valiant",
    "oni press",
    "vault",
    "titan",
    "archie",
)


def _parse_price(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = _PRICE_RE.search(value)
    if match is None:
        return None
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    from datetime import datetime

    cleaned = value.strip()
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    return None


def _detect_publisher(text: str) -> str | None:
    lowered = text.lower()
    for hint in _PUBLISHER_HINTS:
        if re.search(rf"\b{re.escape(hint)}\b", lowered):
            return hint.title() if hint.islower() else hint
    return None


def _parse_issue_and_cover(title: str) -> tuple[str | None, str | None]:
    issue_match = re.search(r"#\s*([0-9A-Za-z.\-]+)", title)
    cover_match = re.search(r"\b(Cover\s+[A-Z0-9]+)\b", title, flags=re.IGNORECASE)
    issue_number = issue_match.group(1) if issue_match else None
    cover_name = cover_match.group(1).title() if cover_match else None
    return issue_number, cover_name


class RetailerHtmlParser:
    """Base class for retailer saved-order HTML parsers."""

    retailer_key: str = "unknown"
    display_name: str = "Unknown Retailer"
    #: ``supported`` | ``beta`` | ``generic``
    status: str = "generic"
    accepts_upload: bool = True

    def analyze(self, html_text: str) -> RetailerHtmlPageDiagnostics:
        soup = BeautifulSoup(html_text, "html.parser")
        title_tag = soup.title.get_text(strip=True) if soup.title else None
        visible = soup.get_text("\n", strip=True)
        order_number_link_count = 0
        for anchor in soup.find_all("a"):
            link_text = anchor.get_text(" ", strip=True)
            href = anchor.get("href") or ""
            if _ORDER_HASH_LINK_RE.search(link_text) or _ORDER_HASH_LINK_RE.search(href):
                order_number_link_count += 1
        return RetailerHtmlPageDiagnostics(
            retailer=self.retailer_key,
            title=title_tag,
            page_length=len(html_text),
            order_item_count=len(soup.select(".order-item")) or len(soup.find_all("tr")),
            order_number_link_count=order_number_link_count,
            visible_text_excerpt=visible[:_VISIBLE_TEXT_EXCERPT_LIMIT],
            has_right_contents=soup.select_one("#right-contents") is not None,
            has_info_container=soup.select_one(".info-container") is not None,
        )

    def parse(self, html_text: str) -> RetailerOrderDetail:  # pragma: no cover - abstract
        raise NotImplementedError


class MidtownSavedHtmlParser(RetailerHtmlParser):
    retailer_key = "midtown"
    display_name = "Midtown Comics"
    status = "supported"

    def parse(self, html_text: str) -> RetailerOrderDetail:
        # The Midtown parser is duck-compatible with RetailerOrderDetail.
        return parse_midtown_order_detail(html_text)  # type: ignore[return-value]


class GenericRetailerHtmlParser(RetailerHtmlParser):
    """Best-effort parser for arbitrary saved order pages.

    Heuristics only: find an order number near order/invoice labels, then scan
    table rows (and a visible-text fallback) for lines that contain a price.
    Missing release date / product URL / catalog match never block the import.
    """

    retailer_key = "unknown"
    display_name = "Unknown / Other Retailer"
    status = "generic"

    def _extract_order_number(self, soup: BeautifulSoup) -> str | None:
        header_text_sources: list[str] = []
        if soup.title:
            header_text_sources.append(soup.title.get_text(" ", strip=True))
        for tag in soup.find_all(["h1", "h2", "h3"]):
            header_text_sources.append(tag.get_text(" ", strip=True))
        header_text_sources.append(soup.get_text(" ", strip=True)[:4000])
        for text in header_text_sources:
            for match in _ORDER_NUMBER_RE.finditer(text or ""):
                candidate = (match.group(1) or "").strip()
                if not candidate:
                    continue
                # Real order numbers contain at least one digit; this rejects words
                # like "Confirmation", "Details", or "Summary" that follow "Order".
                if not re.search(r"\d", candidate):
                    continue
                return candidate
        return None

    def _build_item_from_cells(self, cell_texts: list[str], raw_fragment: str) -> RetailerOrderItem | None:
        prices = [
            _parse_price(text)
            for text in cell_texts
            if _PRICE_RE.search(text)
        ]
        prices = [price for price in prices if price is not None]
        if not prices:
            return None

        title = ""
        for text in cell_texts:
            cleaned = text.strip()
            if not cleaned:
                continue
            if _PRICE_RE.fullmatch(cleaned) or _PRICE_RE.search(cleaned) and len(cleaned) <= 12:
                continue
            if re.fullmatch(r"\d{1,3}", cleaned):
                continue
            if len(cleaned) > len(title):
                title = cleaned
        if not title or len(title) < 3:
            return None

        quantity = 1
        joined = " ".join(cell_texts)
        qty_label = _QTY_LABEL_RE.search(joined)
        if qty_label:
            quantity = max(1, int(qty_label.group(1)))
        else:
            for text in cell_texts:
                cleaned = text.strip()
                if re.fullmatch(r"\d{1,3}", cleaned):
                    quantity = max(1, int(cleaned))
                    break

        unit_price = prices[0]
        total_price = prices[-1] if len(prices) > 1 else None
        issue_number, cover_name = _parse_issue_and_cover(title)
        item = RetailerOrderItem(
            title=title,
            publisher=_detect_publisher(joined),
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            issue_number=issue_number,
            cover_name=cover_name,
            raw_fragment=raw_fragment[:4000],
        )
        item.parse_diagnostics = {"parse_source": "generic_row_scan"}
        return item

    def _extract_items_from_tables(self, soup: BeautifulSoup) -> list[RetailerOrderItem]:
        items: list[RetailerOrderItem] = []
        seen_keys: set[str] = set()
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            cell_texts = [cell.get_text(" ", strip=True) for cell in cells]
            item = self._build_item_from_cells(cell_texts, str(row))
            if item is None:
                continue
            # Attach product url / image if present in the row.
            anchor = row.find("a", href=True)
            if anchor is not None:
                item.product_url = anchor["href"].strip() or None
            img = row.find("img")
            if img is not None and img.get("src"):
                item.image_url = img["src"].strip() or None
                item.thumbnail_url = item.image_url
            key = item.product_url or f"{item.title}|{item.quantity}|{item.unit_price}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            items.append(item)
        return items

    def _extract_items_from_visible_text(self, soup: BeautifulSoup) -> list[RetailerOrderItem]:
        items: list[RetailerOrderItem] = []
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
        for line in lines:
            if not _PRICE_RE.search(line):
                continue
            # Strip trailing price(s) to recover the title.
            title = _PRICE_RE.sub("", line).strip(" -\u2013\t")
            title = re.sub(r"\b(?:qty|quantity)\b\s*[:x]?\s*\d{1,3}", "", title, flags=re.IGNORECASE).strip()
            if len(title) < 3:
                continue
            prices = [_parse_price(p) for p in _PRICE_RE.findall(line)]
            prices = [p for p in prices if p is not None]
            qty_label = _QTY_LABEL_RE.search(line)
            quantity = max(1, int(qty_label.group(1))) if qty_label else 1
            issue_number, cover_name = _parse_issue_and_cover(title)
            item = RetailerOrderItem(
                title=title,
                publisher=_detect_publisher(line),
                quantity=quantity,
                unit_price=prices[0] if prices else None,
                total_price=prices[-1] if len(prices) > 1 else None,
                issue_number=issue_number,
                cover_name=cover_name,
                raw_fragment=line[:1000],
            )
            item.parse_diagnostics = {"parse_source": "generic_visible_text"}
            items.append(item)
        return items

    def parse(self, html_text: str) -> RetailerOrderDetail:
        soup = BeautifulSoup(html_text, "html.parser")
        order_number = self._extract_order_number(soup)
        items = self._extract_items_from_tables(soup)
        parse_source = "generic_row_scan"
        if not items:
            items = self._extract_items_from_visible_text(soup)
            parse_source = "generic_visible_text"

        order_total = None
        for label in ("Order Total", "Grand Total", "Total", "Subtotal"):
            match = re.search(rf"{label}\s*[:]?\s*\$?\s*([0-9]+(?:\.[0-9]{{2}}))", soup.get_text(" ", strip=True), flags=re.IGNORECASE)
            if match:
                order_total = _parse_price(match.group(0))
                if order_total is not None:
                    break

        detail = RetailerOrderDetail(
            retailer_order_number=order_number or "",
            order_total=order_total,
            items=items,
            raw_html=html_text,
        )
        detail.parse_diagnostics = {
            "parse_scope": "generic",
            "parse_source": parse_source,
            "retailer": self.retailer_key,
            "item_blocks_found": len(items),
            "items_parsed": len(items),
            "order_number_found": bool(order_number),
        }
        return detail


class DCBSSavedHtmlParser(GenericRetailerHtmlParser):
    retailer_key = "dcbs"
    display_name = "DCBS / Discount Comic Book Service"
    status = "beta"


class ThirdEyeSavedHtmlParser(GenericRetailerHtmlParser):
    retailer_key = "third_eye"
    display_name = "Third Eye Comics"
    status = "beta"


class MyComicShopSavedHtmlParser(GenericRetailerHtmlParser):
    retailer_key = "mycomicshop"
    display_name = "MyComicShop"
    status = "beta"


# Public registry. The keys here are the canonical retailer identifiers used by
# the API, persistence layer, and frontend selector.
retailer_html_parsers: dict[str, RetailerHtmlParser] = {
    "midtown": MidtownSavedHtmlParser(),
    "dcbs": DCBSSavedHtmlParser(),
    "third_eye": ThirdEyeSavedHtmlParser(),
    "mycomicshop": MyComicShopSavedHtmlParser(),
    "unknown": GenericRetailerHtmlParser(),
}


def get_retailer_html_parser(retailer: str | None) -> RetailerHtmlParser:
    key = (retailer or "").strip().lower()
    parser = retailer_html_parsers.get(key)
    if parser is None:
        raise RetailerHtmlImportError(
            f"Unsupported retailer '{retailer}'. Choose a supported retailer or use "
            "'Unknown / Request Support' to upload a saved order page."
        )
    return parser


def list_supported_retailers() -> list[dict]:
    """Return retailer cards for the import selector UI (registry-driven)."""
    cards: list[dict] = []
    for key, parser in retailer_html_parsers.items():
        cards.append(
            {
                "key": key,
                "display_name": parser.display_name,
                "status": parser.status,
                "supported": parser.status == "supported",
                "accepts_upload": parser.accepts_upload,
                "is_fallback": key == "unknown",
            }
        )
    return cards


def __getattr__(name: str):
    # The Midtown order-number error is part of the parser contract; re-export it
    # so callers can catch parser-specific failures from this module.
    if name == "MidtownOrderNumberError":
        return MidtownOrderNumberError
    raise AttributeError(name)
