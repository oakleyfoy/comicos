"""Shared, retailer-agnostic types for saved-order HTML imports.

Every retailer HTML parser normalizes into :class:`RetailerOrderDetail` /
:class:`RetailerOrderItem`. These dataclasses are intentionally duck-compatible
with the Midtown parser output so the shared persistence layer
(``upsert_retailer_order_snapshots``) can store any retailer's parse result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@dataclass(slots=True)
class RetailerOrderItem:
    """Common normalized order line, shared across all retailer HTML parsers."""

    title: str = ""
    publisher: str | None = None
    quantity: int = 1
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    item_status: str | None = None
    condition: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    product_url: str | None = None
    retailer_item_id: str | None = None
    issue_number: str | None = None
    cover_name: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    release_date: date | None = None
    shipped_qty: int | None = None
    backordered_qty: int | None = None
    unavailable_qty: int | None = None
    returned_qty: int | None = None
    parse_diagnostics: dict = field(default_factory=dict)
    raw_fragment: str = ""

    def to_dict(self) -> dict:
        return _json_safe(asdict(self))


@dataclass(slots=True)
class RetailerOrderDetail:
    """Common normalized order, shared across all retailer HTML parsers."""

    retailer_order_number: str
    order_date: date | None = None
    order_status: str | None = None
    order_total: Decimal | None = None
    detail_url: str | None = None
    items: list[RetailerOrderItem] = field(default_factory=list)
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


@dataclass
class RetailerHtmlPageDiagnostics:
    """Lightweight structural diagnostics for a saved retailer order page."""

    retailer: str
    title: str | None
    page_length: int
    order_item_count: int
    order_number_link_count: int
    visible_text_excerpt: str
    has_right_contents: bool = False
    has_info_container: bool = False
    saved_html_path: str | None = None
    parsed: dict | None = None

    def to_dict(self) -> dict:
        return _json_safe(asdict(self))

    def debug_response(self) -> dict:
        return {
            "title": self.title,
            "page_length": self.page_length,
            "order_item_count": self.order_item_count,
            "has_right_contents": self.has_right_contents,
            "has_info_container": self.has_info_container,
            "visible_text_excerpt": self.visible_text_excerpt,
        }


class RetailerHtmlImportError(RuntimeError):
    """Raised when a saved retailer order HTML file cannot be imported."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: RetailerHtmlPageDiagnostics | dict | None = None,
    ):
        super().__init__(message)
        if isinstance(diagnostics, RetailerHtmlPageDiagnostics):
            self.diagnostics = diagnostics.to_dict()
        else:
            self.diagnostics = diagnostics
