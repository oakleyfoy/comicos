from __future__ import annotations

"""Deterministic known-UPC catalog for replay-safe mobile scan lookups (P44-03)."""

from typing import Any

KNOWN_UPC_ENTRIES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "012345678905",
        {
            "catalog_key": "sample-trade-paperback",
            "title": "Sample Trade Paperback",
            "format": "tpb",
        },
    ),
    (
        "9780316383129",
        {
            "catalog_key": "sample-isbn13",
            "title": "Sample ISBN-13 Title",
            "format": "book",
        },
    ),
)


def lookup_known_upc(normalized_value: str) -> dict[str, Any] | None:
    for upc, payload in KNOWN_UPC_ENTRIES:
        if upc == normalized_value:
            return {"upc": upc, **payload}
    return None
