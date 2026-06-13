from __future__ import annotations

import html
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_MIDTOWN_BASE_URL = "https://www.midtowncomics.com"
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_PRICE_RE = re.compile(r"\$?\s*([0-9]+(?:\.[0-9]{2})?)")
_DATE_PATTERNS = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y")
_KNOWN_LABELS = (
    "Date|Status|Total|Subtotal|Order Total|Publisher|Qty|QTY|Price|Each|Line Total|"
    "Item Status|Shipped|Backordered|Unavailable|Returned|SKU|Variant|Cover Artist|Item #|Condition"
)
_ORDER_NUMBER_RE = re.compile(r"\border\s*#\s*([0-9]{4,})\b", flags=re.IGNORECASE)

logger = logging.getLogger(__name__)

_ITEM_LABEL_PREFIXES = (
    "publisher:",
    "each:",
    "total:",
    "qty:",
    "condition:",
    "status:",
    "item #:",
    "sku:",
    "line total:",
    "price:",
    "shipped:",
    "backordered:",
    "unavailable:",
    "returned:",
    "variant:",
    "cover artist:",
    "release date:",
)
_TITLE_CLASS_TOKENS = ("title", "product-name", "product_name", "item-name", "item_name", "comic", "name")
_SKIP_HREF_PARTS = ("/account/", "/cart", "javascript:", "mailto:", "#pull-list", "pull-list")
_PRODUCT_PATH_MARKERS = ("/product/", "/store/", "/comics/", "/Product/", "/Store/", "/p/")
_ORDER_ITEM_CLASS_RE = re.compile(r'\border-item\b', flags=re.IGNORECASE)
_SAVED_IMAGE_FILE_RE = re.compile(r"(\d+)_ful\.jpg", flags=re.IGNORECASE)
_PUBLISHER_ALIASES = {
    "dc": "DC",
    "dc comics": "DC",
    "marvel": "Marvel",
    "marvel comics": "Marvel",
    "image": "Image",
    "image comics": "Image",
    "idw publishing": "IDW Publishing",
    "idw": "IDW Publishing",
    "independents": "Independents",
    "dark horse": "Dark Horse",
    "dark horse comics": "Dark Horse",
}


class MidtownOrderNumberError(RuntimeError):
    """Raised when a Midtown order number cannot be found or validated."""


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
    release_date: date | None = None
    shipped_qty: int | None = None
    backordered_qty: int | None = None
    unavailable_qty: int | None = None
    returned_qty: int | None = None
    condition: str | None = None
    image_title: str | None = None
    remote_midtown_image_url: str | None = None
    parse_diagnostics: dict = field(default_factory=dict)
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
    parse_diagnostics: dict = field(default_factory=dict)
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
                "parse_diagnostics": _json_safe(self.parse_diagnostics),
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


def _extract_order_status(html_text: str) -> str | None:
    text = _clean_html_text(html_text)
    match = re.search(
        r"\bStatus\s*:?\s*([A-Za-z][A-Za-z -]{0,80}?)(?=\s+\d+\b|\s+(?:Date|Total|Publisher|Qty|Price|Line Total|Item Status|Shipped|Backordered|Unavailable|Returned|SKU|Variant|Cover Artist|Item #)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_release_date(fragment: str) -> date | None:
    return _parse_date(
        _match_after_label(fragment, "Release Date")
        or _match_after_label(fragment, "Ship Date")
        or _match_after_label(fragment, "Pub Date")
    )


def _extract_item_quality_snapshot(item: MidtownOrderItem, *, saved_html_upload: bool = False) -> dict:
    fields = {
        "retailer_item_id": item.retailer_item_id,
        "product_url": item.product_url,
        "image_url": item.image_url,
        "title": item.title,
        "publisher": item.publisher,
        "issue_number": item.issue_number,
        "cover_name": item.cover_name,
        "variant_type": item.variant_type,
        "cover_artist": item.cover_artist,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "total_price": item.total_price,
        "item_status": item.item_status,
        "release_date": item.release_date,
    }
    optional_fields = {"product_url", "release_date", "retailer_item_id", "cover_artist", "variant_type"}
    if not saved_html_upload:
        optional_fields = set()
    extracted = [name for name, value in fields.items() if value not in (None, "", [])]
    missing = [
        name
        for name, value in fields.items()
        if value in (None, "", []) and name not in optional_fields
    ]
    enrichment_missing = [
        name for name in optional_fields if fields.get(name) in (None, "", [])
    ]
    return {
        "fields_extracted": extracted,
        "fields_missing": missing,
        "enrichment_fields_missing": enrichment_missing,
        "fields_extracted_count": len(extracted),
        "fields_total": len(fields),
    }


def _extract_order_number_from_text(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        cleaned = _clean_html_text(value)
        match = _ORDER_NUMBER_RE.search(cleaned)
        if match and match.group(1):
            return match.group(1).strip()
    return None


def _extract_order_number_from_url(detail_url: str | None) -> str | None:
    if not detail_url:
        return None
    parsed = urlparse(detail_url)
    for segment in reversed([segment for segment in parsed.path.split("/") if segment]):
        if re.fullmatch(r"[0-9]{4,}", segment):
            return segment
    return None


def _extract_order_number_from_header(html_text: str) -> str | None:
    for match in re.finditer(
        r"<(?:title|h1|h2|h3)[^>]*>(.*?)</(?:title|h1|h2|h3)>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = _clean_html_text(match.group(1))
        order_number = _extract_order_number_from_text(text)
        if order_number:
            return order_number
    return None


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
        order_number = _extract_order_number_from_text(text)
        if order_number is None:
            continue
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
    """Legacy scan: product links anywhere in the document (pre-scoped pages)."""
    return _extract_item_fragments_legacy(html_text)


def _extract_item_fragments_legacy(html_text: str) -> list[str]:
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
    return fragments


def _info_container_header_html(scoped_html: str) -> str:
    """Return markup before the first ``.order-item`` inside ``.info-container``."""
    soup = BeautifulSoup(scoped_html, "html.parser")
    info = soup.select_one(".info-container")
    if info is None:
        return scoped_html
    chunks: list[str] = []
    for child in info.children:
        name = getattr(child, "name", None)
        classes = child.get("class") if name else None
        if name and classes and "order-item" in classes:
            break
        if name:
            chunks.append(str(child))
        else:
            text = str(child).strip()
            if text:
                chunks.append(text)
    return "".join(chunks) if chunks else scoped_html


def _scope_saved_order_container(html_text: str) -> tuple[str | None, list[str]]:
    """Isolate ``#right-contents .info-container`` and its ``.order-item`` rows."""
    soup = BeautifulSoup(html_text, "html.parser")
    right = soup.select_one("#right-contents")
    if right is None:
        return None, []
    info = right.select_one(".info-container")
    if info is None:
        return None, []
    fragments = [str(element) for element in info.select(".order-item")]
    return str(info), fragments


def _visible_text_from_html(html_fragment: str) -> str:
    soup = BeautifulSoup(html_fragment, "html.parser")
    return soup.get_text("\n", strip=True)


def _extract_order_total_from_scope(scoped_html: str) -> Decimal | None:
    for label in ("Order Total", "Grand Total", "Subtotal", "Total"):
        parsed = _parse_price(_match_after_label(scoped_html, label))
        if parsed is not None:
            return parsed
    return None


def _line_value(lines: list[str], prefix: str) -> str | None:
    prefix_lower = prefix.lower()
    for line in lines:
        if line.lower().startswith(prefix_lower):
            return line.split(":", 1)[-1].strip() if ":" in line else line[len(prefix) :].strip()
    return None


def _parse_order_items_from_visible_text(text: str) -> list[MidtownOrderItem]:
    """Parse Midtown order line items from plain visible text blocks."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    label_prefixes = (
        "publisher:",
        "each:",
        "total:",
        "qty:",
        "condition:",
        "status:",
        "date:",
        "subtotal:",
        "order total:",
        "line total:",
        "price:",
        "item #:",
        "sku:",
    )
    items: list[MidtownOrderItem] = []
    index = 0
    while index < len(lines):
        title = lines[index]
        lower = title.lower()
        if lower.startswith(label_prefixes) or _ORDER_NUMBER_RE.search(title):
            index += 1
            continue
        lookahead = lines[index + 1 : index + 12]
        if not any(
            segment.lower().startswith(("publisher:", "each:", "price:")) for segment in lookahead
        ):
            index += 1
            continue
        block_lines = [title]
        cursor = index + 1
        while cursor < len(lines):
            segment = lines[cursor]
            segment_lower = segment.lower()
            if segment_lower.startswith(label_prefixes):
                block_lines.append(segment)
                cursor += 1
                continue
            if _ORDER_NUMBER_RE.search(segment):
                break
            next_lookahead = lines[cursor + 1 : cursor + 12]
            if any(
                part.lower().startswith(("publisher:", "each:", "price:"))
                for part in next_lookahead
            ):
                break
            block_lines.append(segment)
            cursor += 1
        block = "\n".join(block_lines)
        publisher = _line_value(block_lines, "Publisher")
        unit_price = _parse_price(_line_value(block_lines, "Each")) or _parse_price(
            _line_value(block_lines, "Price")
        )
        total_price = _parse_price(_line_value(block_lines, "Total")) or _parse_price(
            _line_value(block_lines, "Line Total")
        )
        quantity = (
            _parse_int(_line_value(block_lines, "QTY"))
            or _parse_int(_line_value(block_lines, "Qty"))
            or 1
        )
        item_status = _line_value(block_lines, "Status")
        if unit_price is None and total_price is None:
            index = cursor
            continue
        issue_number, cover_name = _parse_issue_and_cover(title)
        item = MidtownOrderItem(
            title=title,
            publisher=publisher,
            issue_number=issue_number,
            cover_name=cover_name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price or unit_price,
            item_status=item_status,
            raw_fragment=block,
        )
        item.parse_diagnostics = _extract_item_quality_snapshot(item)
        item.parse_diagnostics["missing_fields"] = item.parse_diagnostics["fields_missing"]
        item.parse_diagnostics["parse_source"] = "visible_text_fallback"
        items.append(item)
        index = cursor
    return items


def _normalize_midtown_publisher(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _clean_html_text(value)
    if not cleaned:
        return None
    return _PUBLISHER_ALIASES.get(cleaned.casefold(), cleaned)


def _derive_remote_midtown_image_url(src: str | None) -> str | None:
    if not src:
        return None
    filename = src.replace("\\", "/").split("/")[-1]
    match = _SAVED_IMAGE_FILE_RE.search(filename)
    if not match:
        return None
    product_id = match.group(1)
    return f"https://www.midtowncomics.com/images/PRODUCT/FUL/{product_id}_ful.jpg"


def _normalize_midtown_saved_image_src(src: str | None) -> tuple[str | None, str | None]:
    if not src:
        return None, None
    cleaned = src.strip()
    if cleaned.startswith(("http://", "https://")):
        return cleaned, cleaned
    remote = _derive_remote_midtown_image_url(cleaned)
    return cleaned, remote


def _label_value_in_nodes(nodes, label: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(label)}\s*:?\s*(.*)$", flags=re.IGNORECASE)
    for node in nodes:
        text = _clean_html_text(node.get_text(" ", strip=True))
        if not text:
            continue
        match = pattern.match(text)
        if match:
            return match.group(1).strip()
    return None


def _parse_saved_html_col10_order_item(fragment: str) -> MidtownOrderItem | None:
    soup = BeautifulSoup(fragment, "html.parser")
    col10 = soup.select_one(".col-10")
    if col10 is None:
        return None

    col2_img = soup.select_one(".col-2 img")
    img_src = col2_img.get("src") if col2_img else None
    image_title = _clean_html_text(col2_img.get("title") or "") if col2_img else None
    image_url, remote_midtown_image_url = _normalize_midtown_saved_image_src(img_src)

    h3_texts = [_clean_html_text(h3.get_text(" ", strip=True)) for h3 in col10.find_all("h3")]
    h3_texts = [text for text in h3_texts if text]
    aria_label = _clean_html_text(col10.get("aria-label") or "")

    title = h3_texts[0] if h3_texts else ""
    if not title and aria_label:
        title = aria_label
    if not title and image_title:
        title = image_title
    if not title:
        return None

    publisher: str | None = None
    item_status: str | None = None
    for h3_text in h3_texts[1:]:
        if h3_text.lower().startswith("status:"):
            item_status = h3_text.split(":", 1)[-1].strip()
        elif publisher is None:
            publisher = _normalize_midtown_publisher(h3_text)

    field_nodes = col10.find_all(["p", "div"])
    unit_price = _parse_price(_label_value_in_nodes(field_nodes, "Each"))
    total_price = _parse_price(_label_value_in_nodes(field_nodes, "Total"))
    quantity = _parse_int(_label_value_in_nodes(field_nodes, "QTY")) or 1
    condition_raw = _label_value_in_nodes(field_nodes, "Condition")
    condition = condition_raw if condition_raw else None

    status_root = col10.select_one(".item-status") or col10
    status_nodes = status_root.find_all(["p", "div"])
    shipped_qty = _parse_int(_label_value_in_nodes(status_nodes, "Shipped"))
    backordered_qty = _parse_int(_label_value_in_nodes(status_nodes, "Backordered"))
    unavailable_qty = _parse_int(_label_value_in_nodes(status_nodes, "Not Available"))
    returned_qty = _parse_int(_label_value_in_nodes(status_nodes, "Returned"))

    issue_number, cover_name = _parse_issue_and_cover(title)
    item = MidtownOrderItem(
        title=title,
        publisher=publisher,
        issue_number=issue_number,
        cover_name=cover_name,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        item_status=item_status,
        condition=condition,
        image_title=image_title or None,
        image_url=image_url,
        thumbnail_url=image_url,
        remote_midtown_image_url=remote_midtown_image_url,
        shipped_qty=shipped_qty,
        backordered_qty=backordered_qty,
        unavailable_qty=unavailable_qty,
        returned_qty=returned_qty,
        raw_fragment=fragment,
    )
    item.parse_diagnostics = _extract_item_quality_snapshot(item, saved_html_upload=True)
    item.parse_diagnostics["missing_fields"] = item.parse_diagnostics["fields_missing"]
    item.parse_diagnostics["parse_source"] = "saved_html_col10"
    return item


def _col10_order_item_debug_fields(fragment: str) -> dict:
    soup = BeautifulSoup(fragment, "html.parser")
    col10 = soup.select_one(".col-10")
    col2_img = soup.select_one(".col-2 img")
    pretty = soup.prettify()
    field_nodes = col10.find_all(["p", "div"]) if col10 else []
    status_root = col10.select_one(".item-status") if col10 else None
    status_nodes = status_root.find_all(["p", "div"]) if status_root else []
    parsed_item = _parse_saved_html_col10_order_item(fragment)
    resolved_fields = None
    if parsed_item is not None:
        resolved_fields = {
            "title": parsed_item.title,
            "publisher": parsed_item.publisher,
            "image_url": parsed_item.image_url,
            "remote_midtown_image_url": parsed_item.remote_midtown_image_url,
            "image_title": parsed_item.image_title,
            "unit_price": str(parsed_item.unit_price) if parsed_item.unit_price is not None else None,
            "total_price": str(parsed_item.total_price) if parsed_item.total_price is not None else None,
            "quantity": parsed_item.quantity,
            "condition": parsed_item.condition,
            "item_status": parsed_item.item_status,
            "shipped_qty": parsed_item.shipped_qty,
            "backordered_qty": parsed_item.backordered_qty,
            "unavailable_qty": parsed_item.unavailable_qty,
            "returned_qty": parsed_item.returned_qty,
        }
    return {
        "item_html_excerpt": pretty[:3000],
        "prettified_html": pretty[:8000],
        "item_text": soup.get_text("\n", strip=True),
        "h3_texts": [_clean_html_text(h3.get_text(" ", strip=True)) for h3 in (col10.find_all("h3") if col10 else [])],
        "img_src": col2_img.get("src") if col2_img else None,
        "img_title": _clean_html_text(col2_img.get("title") or "") if col2_img else None,
        "col10_aria_label": _clean_html_text(col10.get("aria-label") or "") if col10 else None,
        "p_texts": [_clean_html_text(node.get_text(" ", strip=True)) for node in field_nodes if node.get_text(strip=True)],
        "item_status_texts": [
            _clean_html_text(node.get_text(" ", strip=True)) for node in status_nodes if node.get_text(strip=True)
        ],
        "classes_in_node": sorted(
            {cls for element in soup.find_all(True) for cls in (element.get("class") or [])}
        ),
        "anchor_texts": [
            _clean_html_text(anchor.get_text(" ", strip=True))
            for anchor in soup.find_all("a")
            if _clean_html_text(anchor.get_text(" ", strip=True))
        ],
        "resolved_fields": resolved_fields,
        "resolved_title": parsed_item.title if parsed_item else None,
    }


def _is_order_item_label_line(line: str) -> bool:
    lower = line.lower()
    return any(lower.startswith(prefix) for prefix in _ITEM_LABEL_PREFIXES)


def _href_looks_like_product(href: str) -> bool:
    lower = href.lower()
    if any(part in lower for part in _SKIP_HREF_PARTS):
        return False
    return any(marker.lower() in lower for marker in _PRODUCT_PATH_MARKERS)


def _extract_title_from_order_item(fragment: str) -> tuple[str, str | None, list[dict]]:
    """Extract a line title from a scoped Midtown ``.order-item`` HTML fragment."""
    soup = BeautifulSoup(fragment, "html.parser")
    candidates: list[dict] = []

    for anchor in soup.find_all("a", href=True):
        text = _clean_html_text(anchor.get("title") or "") or _clean_html_text(
            anchor.get("aria-label") or ""
        )
        href = anchor["href"].strip()
        if not text:
            text = _clean_html_text(anchor.get_text(" ", strip=True))
        if text:
            candidates.append({"kind": "anchor_text", "href": href, "text": text})
        if text and _href_looks_like_product(href):
            return text, _absolute_url(href), candidates

    for tag in ("h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"):
        for element in soup.find_all(tag):
            text = _clean_html_text(element.get_text(" ", strip=True))
            if text and len(text) > 5 and not _is_order_item_label_line(text):
                candidates.append({"kind": f"{tag}_text", "text": text})
                return text, None, candidates

    for anchor in soup.find_all("a", href=True):
        text = _clean_html_text(anchor.get_text(" ", strip=True))
        href = anchor["href"].strip()
        if text and len(text) > 5 and not _is_order_item_label_line(text):
            candidates.append({"kind": "anchor_text_fallback", "href": href, "text": text})
            return text, _absolute_url(href), candidates

    for img in soup.find_all("img"):
        alt = _clean_html_text(img.get("alt") or "")
        if alt and len(alt) > 3 and "logo" not in alt.lower():
            candidates.append({"kind": "img_alt", "text": alt})
            return alt, None, candidates

    for element in soup.find_all(True):
        class_tokens = [token.lower() for token in (element.get("class") or [])]
        if not any(
            any(hint in token for hint in _TITLE_CLASS_TOKENS) for token in class_tokens
        ):
            continue
        text = _clean_html_text(element.get_text(" ", strip=True))
        if text and len(text) > 5 and not _is_order_item_label_line(text):
            candidates.append({"kind": "class_hint", "classes": class_tokens, "text": text})
            return text, None, candidates

    for line in soup.get_text("\n", strip=True).splitlines():
        cleaned = line.strip()
        if not cleaned or _is_order_item_label_line(cleaned) or _ORDER_NUMBER_RE.search(cleaned):
            continue
        if len(cleaned) > 5:
            candidates.append({"kind": "visible_text_line", "text": cleaned})
            return cleaned, None, candidates

    return "", None, candidates


def _order_item_debug_fields(fragment: str) -> dict:
    soup = BeautifulSoup(fragment, "html.parser")
    if soup.select_one(".col-10") is not None:
        debug = _col10_order_item_debug_fields(fragment)
        debug["candidate_title_selectors"] = debug.get("h3_texts") or []
        return debug
    pretty = soup.prettify()
    title, _, selectors = _extract_title_from_order_item(fragment)
    return {
        "item_html_excerpt": pretty[:3000],
        "prettified_html": pretty[:8000],
        "item_text": soup.get_text("\n", strip=True),
        "classes_in_node": sorted(
            {cls for element in soup.find_all(True) for cls in (element.get("class") or [])}
        ),
        "anchor_texts": [
            _clean_html_text(anchor.get_text(" ", strip=True))
            for anchor in soup.find_all("a")
            if _clean_html_text(anchor.get_text(" ", strip=True))
        ],
        "candidate_title_selectors": selectors,
        "resolved_title": title or None,
    }


def _parse_item_from_fragment(fragment: str) -> tuple[MidtownOrderItem | None, str | None]:
    """Return ``(item, skip_reason)`` from a single order line HTML fragment."""
    scoped_order_item = bool(_ORDER_ITEM_CLASS_RE.search(fragment))
    if scoped_order_item:
        col10_item = _parse_saved_html_col10_order_item(fragment)
        if col10_item is not None:
            return col10_item, None

    product_url: str | None = None
    saved_html_upload = False
    if scoped_order_item:
        saved_html_upload = True
        title, product_url, _ = _extract_title_from_order_item(fragment)
    else:
        product_match = re.search(
            r'href=["\']([^"\']*/product/[^"\']+)["\']', fragment, flags=re.IGNORECASE
        )
        product_url = _absolute_url(product_match.group(1)) if product_match else None
        title = _extract_title(fragment, product_url)
    if not title:
        return None, "missing_title"
    if product_url is None:
        product_match = re.search(
            r'href=["\']([^"\']*(?:/product/|/store/|/Store/|/comics/)[^"\']+)["\']',
            fragment,
            flags=re.IGNORECASE,
        )
        if product_match:
            product_url = _absolute_url(product_match.group(1))
    issue_number, cover_name = _parse_issue_and_cover(title)
    variant_type = _match_after_label(fragment, "Variant")
    cover_artist = _match_after_label(fragment, "Cover Artist")
    release_date = _extract_release_date(fragment)
    quantity = (
        _parse_int(_match_after_label(fragment, "QTY"))
        or _parse_int(_match_after_label(fragment, "Qty"))
        or 1
    )
    unit_price = _parse_price(_match_after_label(fragment, "Each")) or _parse_price(
        _match_after_label(fragment, "Price")
    )
    total_price = (
        _parse_price(_match_after_label(fragment, "Line Total"))
        or _parse_price(_match_after_label(fragment, "Total"))
    )
    image_tag_match = re.search(r"<img[^>]*>", fragment, flags=re.IGNORECASE)
    image_src: str | None = None
    image_title: str | None = None
    if image_tag_match:
        image_tag = image_tag_match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', image_tag, flags=re.IGNORECASE)
        image_src = src_match.group(1) if src_match else None
        title_match = re.search(r'title=["\']([^"\']*)["\']', image_tag, flags=re.IGNORECASE)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', image_tag, flags=re.IGNORECASE)
        image_title = (
            _clean_html_text((title_match.group(1) if title_match else "") or (alt_match.group(1) if alt_match else ""))
            or None
        )
    image_url, remote_midtown_image_url = _normalize_midtown_saved_image_src(image_src)
    if image_url and image_url.startswith(("http://", "https://")):
        image_url = _absolute_url(image_url)
    item = MidtownOrderItem(
        retailer_item_id=_match_after_label(fragment, "Item #") or _match_after_label(fragment, "SKU"),
        product_url=product_url,
        image_url=image_url,
        thumbnail_url=image_url,
        remote_midtown_image_url=remote_midtown_image_url,
        image_title=image_title,
        title=title,
        publisher=_normalize_midtown_publisher(_match_after_label(fragment, "Publisher")),
        issue_number=issue_number,
        cover_name=cover_name,
        variant_type=variant_type,
        cover_artist=cover_artist,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        item_status=_match_after_label(fragment, "Item Status") or _match_after_label(fragment, "Status"),
        release_date=release_date,
        shipped_qty=_parse_int(_match_after_label(fragment, "Shipped")),
        backordered_qty=_parse_int(_match_after_label(fragment, "Backordered")),
        unavailable_qty=_parse_int(_match_after_label(fragment, "Unavailable")),
        returned_qty=_parse_int(_match_after_label(fragment, "Returned")),
        raw_fragment=fragment,
    )
    item.parse_diagnostics = _extract_item_quality_snapshot(item, saved_html_upload=saved_html_upload)
    item.parse_diagnostics["missing_fields"] = item.parse_diagnostics["fields_missing"]
    return item, None


def _append_parsed_items(
    detail: MidtownOrderDetail,
    item_fragments: list[str],
    *,
    parse_source: str,
) -> dict[str, int]:
    skipped_reasons: dict[str, int] = {}
    seen_item_keys: set[str] = set()
    for fragment in item_fragments:
        item, skip_reason = _parse_item_from_fragment(fragment)
        if item is None:
            if skip_reason:
                skipped_reasons[skip_reason] = skipped_reasons.get(skip_reason, 0) + 1
            continue
        item_key = item.product_url or item.title
        if item_key in seen_item_keys:
            skipped_reasons["duplicate_item_block"] = skipped_reasons.get("duplicate_item_block", 0) + 1
            continue
        seen_item_keys.add(item_key)
        item.parse_diagnostics["parse_source"] = parse_source
        detail.items.append(item)
    return skipped_reasons


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
    retailer_order_number = (
        _extract_order_number_from_header(html_text)
        or _extract_order_number_from_url(detail_url)
        or fallback_order_number
    )
    if not retailer_order_number:
        raise MidtownOrderNumberError(
            "parser_no_order_number: Midtown order number was not found in the page header or URL."
        )

    scoped_html, scoped_fragments = _scope_saved_order_container(html_text)
    parse_context = scoped_html if scoped_html is not None else html_text
    parse_scope = "info_container" if scoped_html is not None else "legacy"
    item_fragments: list[str] = []
    parse_source = "legacy_product_scan"
    visible_text_items: list[MidtownOrderItem] = []

    if scoped_html is not None:
        item_fragments = scoped_fragments
        parse_source = "info_container_order_item"
        if not item_fragments:
            visible_text_items = _parse_order_items_from_visible_text(
                _visible_text_from_html(scoped_html)
            )
            if visible_text_items:
                parse_source = "visible_text_fallback"
    else:
        item_fragments = _extract_item_fragments_legacy(html_text)

    order_total = _extract_order_total_from_scope(parse_context) or _parse_price(
        _match_after_label(parse_context, "Total")
    )
    order_header_context = (
        _info_container_header_html(scoped_html) if scoped_html is not None else parse_context
    )
    detail = MidtownOrderDetail(
        retailer_order_number=retailer_order_number,
        order_date=_parse_date(_match_after_label(order_header_context, "Date")),
        order_status=_match_after_label(order_header_context, "Status")
        or _extract_order_status(order_header_context),
        order_total=order_total,
        detail_url=detail_url,
        raw_html=html_text,
    )

    skipped_reasons: dict[str, int] = {}
    if visible_text_items:
        detail.items = visible_text_items
    else:
        skipped_reasons = _append_parsed_items(
            detail, item_fragments, parse_source=parse_source
        )

    blocks_found = len(item_fragments) if not visible_text_items else len(visible_text_items)
    detail.parse_diagnostics = {
        "parse_scope": parse_scope,
        "parse_source": parse_source,
        "item_blocks_found": blocks_found,
        "items_parsed": len(detail.items),
        "items_skipped": max(blocks_found - len(detail.items), 0),
        "skipped_reasons": skipped_reasons,
    }
    if item_fragments:
        first_item_debug = _order_item_debug_fields(item_fragments[0])
        detail.parse_diagnostics["first_order_item"] = first_item_debug
        logger.info(
            "midtown_parser first_order_item_html=%s",
            first_item_debug["item_html_excerpt"][:1500],
        )
        logger.info(
            "midtown_parser first_order_item_text=%s",
            first_item_debug["item_text"][:1500],
        )
        logger.info(
            "midtown_parser candidate_title_selectors=%s",
            first_item_debug["candidate_title_selectors"],
        )
    return detail
