"""Normalize retailer-sourced draft imports so confirm can create inventory without catalog enrichment."""

from __future__ import annotations

import re
from decimal import Decimal

from sqlmodel import Session

from app.models import DraftImport
from app.schemas.ai import ParseOrderResponse
from app.services.import_catalog_resolution_service import derive_catalog_search_title

RETAILER_FALLBACK_PUBLISHER = "Unknown Publisher"
_ISSUE_FROM_TITLE_RE = re.compile(r"#\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)


def _issue_number_from_title(title: str | None) -> str | None:
    if not title:
        return None
    match = _ISSUE_FROM_TITLE_RE.search(title)
    if match is None:
        return None
    return match.group(1)


def _normalize_issue_number(value: str | None, *, title: str | None) -> str:
    candidate = (value or "").strip().lstrip("#")
    if candidate:
        return candidate
    from_title = _issue_number_from_title(title)
    if from_title:
        return from_title
    return "1"


def prepare_draft_import_for_retailer_confirm(session: Session, draft_import: DraftImport) -> None:
    """Fill required order-create fields without requiring catalog or release metadata."""
    payload = ParseOrderResponse.model_validate(draft_import.parsed_payload_json or {})
    if payload.retailer is None:
        payload = payload.model_copy(update={"retailer": "Midtown Comics"})
    if payload.source_type is None:
        payload = payload.model_copy(update={"source_type": "retailer_account"})
    if payload.order_date is None:
        payload = payload.model_copy(update={"order_date": draft_import.created_at.date()})

    normalized_items = []
    for item in payload.items:
        publisher = (item.publisher or "").strip() or RETAILER_FALLBACK_PUBLISHER
        raw_title = (item.title or "").strip() or "Unknown Title"
        # Derive the issue number from the raw retailer title before cleaning it,
        # since cleaning strips the "#N" marker.
        issue_number = _normalize_issue_number(item.issue_number, title=raw_title)
        # Store the cleaned series name as the book title. Retailer titles carry
        # cover/variant/promo noise (e.g. "#1 Cover A Regular <Artist> Cover
        # (DC All In)(Limit 1 Per Customer)"); the display title should be the same
        # cleaned series name we use for catalog search, with the issue number and
        # variant rendered from their own fields.
        title = derive_catalog_search_title(raw_title) or raw_title
        quantity = int(item.quantity or 1)
        raw_price = item.raw_item_price if item.raw_item_price is not None else Decimal("0")
        normalized_items.append(
            item.model_copy(
                update={
                    "publisher": publisher,
                    "title": title,
                    # Metadata enrichment derives the canonical series (ComicTitle)
                    # from raw_title when present, so clean it too; the original
                    # retailer string is preserved on the order snapshot.
                    "raw_title": title,
                    "issue_number": issue_number,
                    "quantity": quantity,
                    "raw_item_price": raw_price,
                }
            )
        )

    payload = payload.model_copy(update={"items": normalized_items})
    draft_import.parsed_payload_json = payload.model_dump(mode="json")
    session.add(draft_import)
    session.flush()
