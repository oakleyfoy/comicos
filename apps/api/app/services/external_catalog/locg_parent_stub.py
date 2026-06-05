"""Parent issue stubs for variant-only LoCG list rows (no data-parent=0 line)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

_PARENT_TITLE_FROM_VARIANT = re.compile(
    r"^(.+?\s+#\d+)\b",
    re.IGNORECASE,
)


def comic_id_from_locg_url(url: str) -> str:
    m = re.search(r"/comic/(\d+)", url or "")
    return m.group(1) if m else ""


def derive_parent_title_from_variant_title(title: str) -> str:
    """Best-effort series/issue title from a variant list title."""
    cleaned = re.sub(r"\s+", " ", (title or "").strip())
    if not cleaned:
        return ""
    m = _PARENT_TITLE_FROM_VARIANT.match(cleaned)
    if m:
        return m.group(1).strip()
    for sep in (
        " Facsimile",
        " Cover ",
        " Printing",
        " AMC ",
        " Metal ",
        " Virgin ",
        " Wraparound",
        " Black &",
    ):
        idx = cleaned.find(sep)
        if idx > 0:
            return cleaned[:idx].strip()
    return cleaned


def parent_stub_dict_from_variant_row(
    row: Any,
    *,
    page_date: date | None,
    source_name: str,
) -> dict[str, Any] | None:
    parent_url = (getattr(row, "parent_source_url", None) or "").strip()
    if not parent_url:
        return None
    title = derive_parent_title_from_variant_title(
        getattr(row, "title", None) or getattr(row, "variant_name", None) or ""
    )
    if not title:
        comic_id = comic_id_from_locg_url(parent_url)
        title = f"Comic {comic_id}" if comic_id else "Unknown parent"
    return {
        "source_name": source_name,
        "source_url": parent_url,
        "title": title,
        "publisher": getattr(row, "publisher", None) or "",
        "release_date": getattr(row, "release_date", None) or page_date,
        "price": getattr(row, "price", None),
        "cover_image_url": None,
    }
