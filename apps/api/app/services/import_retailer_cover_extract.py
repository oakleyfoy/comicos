"""P92-07 Phase 3 — extract retailer cover URLs from receipt HTML."""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass
from typing import Any

from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse

_IMG_SRC_PATTERN = re.compile(
    r"""<img[^>]+src\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_HREF_PATTERN = re.compile(
    r"""<a[^>]+href\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_TR_BLOCK_PATTERN = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
_SKU_PATTERN = re.compile(r"\b(?:sku|item\s*#|product\s*#)\s*[:#]?\s*([A-Za-z0-9-]{4,})\b", re.I)
_COVER_URL_HINTS = ("cover", "comic", "product", "thumbnail", "catalog", "issue", "midtown", "cdn")
_SKIP_URL_HINTS = (
    "logo",
    "pixel",
    "spacer",
    "facebook",
    "instagram",
    "twitter",
    "unsubscribe",
    "tracking",
    "open.gif",
    "beacon",
    "emoji",
)


@dataclass(frozen=True)
class RetailerCoverRow:
    image_url: str
    product_url: str | None = None
    sku: str | None = None
    alt_text: str | None = None


def _normalize_url(url: str) -> str:
    cleaned = html_module.unescape(url.strip())
    if cleaned.startswith("//"):
        return f"https:{cleaned}"
    return cleaned


def _looks_like_cover_image(url: str) -> bool:
    lower = url.lower()
    if not lower.startswith(("http://", "https://", "//")):
        return False
    if any(skip in lower for skip in _SKIP_URL_HINTS):
        return False
    if any(hint in lower for hint in _COVER_URL_HINTS):
        return True
    return lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def _extract_alt_from_tag(fragment: str) -> str | None:
    match = re.search(r"""alt\s*=\s*["']([^"']*)["']""", fragment, re.I)
    if not match:
        return None
    alt = html_module.unescape(match.group(1)).strip()
    return alt or None


def _sku_from_fragment(fragment: str) -> str | None:
    match = _SKU_PATTERN.search(html_module.unescape(fragment))
    if not match:
        return None
    return match.group(1).strip()


def extract_retailer_cover_rows(html: str) -> list[RetailerCoverRow]:
    if not html or "<img" not in html.lower():
        return []

    rows: list[RetailerCoverRow] = []
    tr_blocks = _TR_BLOCK_PATTERN.findall(html)
    fragments = tr_blocks if tr_blocks else [html]

    for fragment in fragments:
        img_match = _IMG_SRC_PATTERN.search(fragment)
        if not img_match:
            continue
        image_url = _normalize_url(img_match.group(1))
        if not _looks_like_cover_image(image_url):
            continue
        href_match = _HREF_PATTERN.search(fragment)
        product_url = _normalize_url(href_match.group(1)) if href_match else None
        if product_url and not product_url.startswith(("http://", "https://")):
            product_url = None
        rows.append(
            RetailerCoverRow(
                image_url=image_url,
                product_url=product_url,
                sku=_sku_from_fragment(fragment),
                alt_text=_extract_alt_from_tag(fragment),
            )
        )

    if rows:
        return rows

    seen: set[str] = set()
    for url in _IMG_SRC_PATTERN.findall(html):
        normalized = _normalize_url(url)
        if normalized in seen or not _looks_like_cover_image(normalized):
            continue
        seen.add(normalized)
        rows.append(RetailerCoverRow(image_url=normalized))
    return rows


def _title_tokens(title: str | None) -> set[str]:
    if not title:
        return set()
    return {token for token in re.split(r"[^a-z0-9]+", title.lower()) if len(token) >= 3}


def _row_matches_item(row: RetailerCoverRow, item: AiDraftOrderItem) -> bool:
    haystack = " ".join(filter(None, [row.alt_text, row.product_url or ""])).lower()
    if not haystack:
        return False
    title = item.title or item.canonical_title
    tokens = _title_tokens(title)
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in haystack)
    return hits >= min(2, len(tokens))


def _apply_row_to_item(item: AiDraftOrderItem, row: RetailerCoverRow) -> AiDraftOrderItem:
    updates: dict[str, Any] = {
        "retailer_cover_url": row.image_url,
    }
    if row.product_url:
        updates["retailer_product_url"] = row.product_url
        updates["cover_source_url"] = row.product_url
    if row.sku:
        updates["retailer_sku"] = row.sku
        updates["cover_source_sku"] = row.sku
    return item.model_copy(update=updates)


def enrich_parse_order_retailer_covers(
    parsed: ParseOrderResponse,
    *,
    html: str | None,
    retailer: str | None = None,
) -> ParseOrderResponse:
    source_html = html
    if not source_html or not parsed.items:
        return parsed

    rows = extract_retailer_cover_rows(source_html)
    if not rows:
        return parsed

    retailer_name = (retailer or parsed.retailer or "").strip() or None
    enriched_items: list[AiDraftOrderItem] = []
    used_rows: set[int] = set()

    for index, item in enumerate(parsed.items):
        if (item.retailer_cover_url or "").strip():
            enriched_items.append(item)
            continue

        row: RetailerCoverRow | None = None
        if len(rows) == len(parsed.items) and index < len(rows):
            row = rows[index]
            used_rows.add(index)
        else:
            for row_index, candidate in enumerate(rows):
                if row_index in used_rows:
                    continue
                if _row_matches_item(candidate, item):
                    row = candidate
                    used_rows.add(row_index)
                    break

        if row is None:
            enriched_items.append(item)
            continue
        enriched_items.append(_apply_row_to_item(item, row))

    update: dict[str, Any] = {"items": enriched_items}
    if retailer_name and not parsed.retailer:
        update["retailer"] = retailer_name
    return parsed.model_copy(update=update)


def enrich_parse_order_retailer_covers_from_raw_text(parsed: ParseOrderResponse, raw_text: str) -> ParseOrderResponse:
    if "<img" not in raw_text.lower():
        return parsed
    return enrich_parse_order_retailer_covers(
        parsed,
        html=raw_text,
        retailer=parsed.retailer,
    )
