from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

_MIDTOWN_BASE_URL = "https://www.midtowncomics.com"
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_PRICE_RE = re.compile(r"\$?\s*([0-9]+(?:\.[0-9]{2})?)")
_DATE_PATTERNS = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y")
_KNOWN_LABELS = (
    "Date|Status|Total|Publisher|Qty|Price|Line Total|Item Status|Shipped|Backordered|"
    "Unavailable|Returned|SKU|Variant|Cover Artist|Item #"
)


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [_json_safe(child) for child in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@dataclass(slots=True)
class MidtownOrderHistoryEntry:
    retailer_order_number: str
    order_date: date | None = None
    order_status: str | None = None
    order_total: Decimal | None = None
    detail_url: str | None = None
    raw_fragment: str = ""

    def to_dict(self) -> dict:
        return _json_safe(asdict(self))


@dataclass(slots=True)
class MidtownOrderItem:
    retailer_item_id: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    title: str = ""
    publisher: str | None = None
    issue_number: str | None = None
    cover_name: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    quantity: int = 1
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    item_status: str | None = None
    shipped_qty: int | None = None
    backordered_qty: int | None = None
    unavailable_qty: int | None = None
    returned_qty: int | None = None
    raw_fragment: str = ""

    def to_dict(self) -> dict:
        return _json_safe(asdict(self))


@dataclass(slots=True)
class MidtownOrderDetail:
    retailer_order_number: str
    order_date: date | None = None
    order_status: str | None = None
    order_total: Decimal | None = None
    detail_url: str | None = None
    items: list[MidtownOrderItem] = field(default_factory=list)
    raw_html: str = ""

    def to_dict(self) -> dict:
        return _json_safe(
            {
                "retailer_order_number": self.retailer_order_number,
                "order_date": self.order_date,
                "order_status": self.order_status,
                "order_total": self.order_total,
                "detail_url": self.detail_url,
                "items": [item.to_dict() for item in self.items],
            }
        )


def _clean_html_text(value: str) -> str:
    text = html.unescape(_TAG_RE.sub(" ", value or ""))
    return _SPACE_RE.sub(" ", text).strip()


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

    cleaned = _clean_html_text(value)
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(-?\d+)", value)
    return int(match.group(1)) if match else None


def _parse_issue_and_cover(title: str) -> tuple[str | None, str | None]:
    issue_match = re.search(r"#\s*([0-9A-Za-z.\-]+)", title)
    cover_match = re.search(r"\b(Cover\s+[A-Z0-9]+)\b", title, flags=re.IGNORECASE)
    issue_number = issue_match.group(1) if issue_match else None
    cover_name = cover_match.group(1).title() if cover_match else None
    return issue_number, cover_name


def _absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    return urljoin(_MIDTOWN_BASE_URL, html.unescape(url))


def _match_after_label(fragment: str, label: str) -> str | None:
    text = _clean_html_text(fragment)
    match = re.search(
        rf"{label}\s*:?\s*(.+?)(?=\s+(?:{_KNOWN_LABELS})\s*:|$)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def parse_midtown_order_history(html_text: str) -> list[MidtownOrderHistoryEntry]:
    results: list[MidtownOrderHistoryEntry] = []
    seen_numbers: set[str] = set()
    for match in re.finditer(
        r'href=["\']([^"\']*(?:order|Order)[^"\']+)["\']', html_text, flags=re.IGNORECASE
    ):
        href = match.group(1)
        start = max(match.start() - 600, 0)
        end = min(match.end() + 1500, len(html_text))
        fragment = html_text[start:end]
        text = _clean_html_text(fragment)
        number_match = re.search(r"Order\s*#?\s*([A-Z0-9\-]+)", text, flags=re.IGNORECASE)
        if number_match is None:
            number_match = re.search(r"([A-Z0-9]{5,})", text)
        if number_match is None:
            continue
        order_number = number_match.group(1).strip()
        if order_number in seen_numbers:
            continue
        seen_numbers.add(order_number)
        results.append(
            MidtownOrderHistoryEntry(
                retailer_order_number=order_number,
                order_date=_parse_date(_match_after_label(fragment, "Date")),
                order_status=_match_after_label(fragment, "Status"),
                order_total=_parse_price(_match_after_label(fragment, "Total")),
                detail_url=_absolute_url(href),
                raw_fragment=fragment,
            )
        )
    return results


def _extract_item_fragments(html_text: str) -> list[str]:
    fragments: list[str] = []
    for anchor in re.finditer(
        r'href=["\']([^"\']*/product/[^"\']+)["\']', html_text, flags=re.IGNORECASE
    ):
        row_start = html_text.rfind("<tr", 0, anchor.start())
        row_end = html_text.find("</tr>", anchor.end())
        if row_start != -1 and row_end != -1:
            fragments.append(html_text[row_start : row_end + len("</tr>")])
            continue
        div_start = html_text.rfind("<div", 0, anchor.start())
        div_end = html_text.find("</div>", anchor.end())
        if div_start != -1 and div_end != -1:
            fragments.append(html_text[div_start : div_end + len("</div>")])
    deduped: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        key = fragment[:300]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fragment)
    return deduped


def _extract_title(fragment: str, product_url: str | None) -> str:
    title_match = re.search(
        r'(?:class=["\'][^"\']*(?:product|title)[^"\']*["\'][^>]*>|<a[^>]*href=["\'][^"\']*/product/[^"\']+["\'][^>]*>)(.*?)</a>',
        fragment,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        text = _clean_html_text(title_match.group(1))
        if text:
            return text
    if not product_url:
        return ""
    slug = product_url.rstrip("/").split("/")[-1]
    slug = re.sub(r"^\d+-?", "", slug)
    slug = slug.replace("-", " ")
    return _SPACE_RE.sub(" ", slug).strip().title()


def parse_midtown_order_detail(
    html_text: str, *, fallback_order_number: str | None = None, detail_url: str | None = None
) -> MidtownOrderDetail:
    page_text = _clean_html_text(html_text)
    number_match = re.search(r"Order\s*#?\s*([A-Z0-9\-]+)", page_text, flags=re.IGNORECASE)
    retailer_order_number = (
        number_match.group(1).strip()
        if number_match is not None
        else (fallback_order_number or "").strip()
    )
    detail = MidtownOrderDetail(
        retailer_order_number=retailer_order_number,
        order_date=_parse_date(_match_after_label(html_text, "Date")),
        order_status=_match_after_label(html_text, "Status"),
        order_total=_parse_price(_match_after_label(html_text, "Total")),
        detail_url=detail_url,
        raw_html=html_text,
    )
    for fragment in _extract_item_fragments(html_text):
        product_match = re.search(
            r'href=["\']([^"\']*/product/[^"\']+)["\']', fragment, flags=re.IGNORECASE
        )
        image_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', fragment, flags=re.IGNORECASE)
        title = _extract_title(
            fragment, _absolute_url(product_match.group(1)) if product_match else None
        )
        if not title:
            continue
        issue_number, cover_name = _parse_issue_and_cover(title)
        detail.items.append(
            MidtownOrderItem(
                retailer_item_id=_match_after_label(fragment, "Item #")
                or _match_after_label(fragment, "SKU"),
                product_url=_absolute_url(product_match.group(1)) if product_match else None,
                image_url=_absolute_url(image_match.group(1)) if image_match else None,
                thumbnail_url=_absolute_url(image_match.group(1)) if image_match else None,
                title=title,
                publisher=_match_after_label(fragment, "Publisher"),
                issue_number=issue_number,
                cover_name=cover_name,
                variant_type=_match_after_label(fragment, "Variant"),
                cover_artist=_match_after_label(fragment, "Cover Artist"),
                quantity=_parse_int(_match_after_label(fragment, "Qty")) or 1,
                unit_price=_parse_price(_match_after_label(fragment, "Price")),
                total_price=_parse_price(_match_after_label(fragment, "Line Total"))
                or _parse_price(_match_after_label(fragment, "Total")),
                item_status=_match_after_label(fragment, "Item Status")
                or _match_after_label(fragment, "Status"),
                shipped_qty=_parse_int(_match_after_label(fragment, "Shipped")),
                backordered_qty=_parse_int(_match_after_label(fragment, "Backordered")),
                unavailable_qty=_parse_int(_match_after_label(fragment, "Unavailable")),
                returned_qty=_parse_int(_match_after_label(fragment, "Returned")),
                raw_fragment=fragment,
            )
        )
    return detail
