"""Controlled Midtown Comics product lookup."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib import error, parse, request

from .base import (
    RETAILER_LOOKUP_FAILURE_TTL,
    RETAILER_LOOKUP_SUCCESS_TTL,
    RetailerLookupResult,
    RetailerProductCandidate,
    cover_letter_from_text,
    normalize_retailer_name,
    retailer_lookup_is_fresh,
)
from .scoring import accept_retailer_candidate, possible_retailer_candidate, score_retailer_candidate

MIDTOWN_RETAILER = "Midtown Comics"
MIDTOWN_HOST = "www.midtowncomics.com"

_USER_AGENT = "ComicOS/1.0 (import-retailer-lookup)"
_FETCH_TIMEOUT_SECONDS = float(os.environ.get("MIDTOWN_LOOKUP_TIMEOUT_SECONDS", "10"))
_RATE_LIMIT_SECONDS = float(os.environ.get("MIDTOWN_LOOKUP_DELAY_SECONDS", "0.35"))
_SEARCH_URL_TEMPLATE = os.environ.get(
    "MIDTOWN_SEARCH_URL_TEMPLATE",
    "https://www.midtowncomics.com/search?q={query}",
)
_MAX_HTML_BYTES = int(os.environ.get("MIDTOWN_LOOKUP_MAX_HTML_BYTES", "1000000"))

_META_PATTERN = re.compile(
    r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_A_BLOCK_PATTERN = re.compile(r"<a\b[^>]*href\s*=\s*['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", re.I | re.S)
_IMG_PATTERN = re.compile(r"<img\b[^>]*src\s*=\s*['\"]([^'\"]+)['\"][^>]*>", re.I)
_PRICE_PATTERN = re.compile(r"[$](\d+(?:\.\d{2})?)")
_SKU_PATTERN = re.compile(r"\b(?:sku|item\s*#|product\s*#)\s*[:#]?\s*([A-Za-z0-9-]{4,})\b", re.I)
_ISSUE_PATTERN = re.compile(r"\b#?\s*(\d+[A-Za-z]?)\b")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_url(url: str) -> str:
    url = unescape(url.strip())
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _canonicalize_text(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split()).strip()


def _normalize_query(item: dict[str, Any]) -> str:
    cover_letter = cover_letter_from_text(
        " ".join(
            filter(
                None,
                [
                    item.get("cover_name"),
                    item.get("raw_variant_text"),
                    item.get("canonical_variant_text"),
                    item.get("variant_type"),
                ],
            )
        )
    )
    bits = [
        item.get("title") or item.get("canonical_title"),
        item.get("issue_number") or item.get("canonical_issue_number"),
        f"Cover {cover_letter.upper()}" if cover_letter else None,
        item.get("cover_artist"),
        item.get("publisher") or item.get("canonical_publisher"),
    ]
    cleaned: list[str] = []
    for bit in bits:
        if bit is None:
            continue
        text = _canonicalize_text(str(bit))
        if text and text.casefold() != "none":
            cleaned.append(text)
    return " ".join(cleaned)


def _should_reuse_cached_result(item: dict[str, Any], *, force: bool) -> bool:
    if force:
        return False
    enrichment = item.get("retailer_lookup_enrichment")
    return retailer_lookup_is_fresh(enrichment if isinstance(enrichment, dict) else None, force=False)


def _cached_result(item: dict[str, Any]) -> RetailerLookupResult | None:
    enrichment = item.get("retailer_lookup_enrichment")
    if not isinstance(enrichment, dict):
        return None
    if not enrichment.get("checked_at"):
        return None
    candidates: tuple[RetailerProductCandidate, ...] = ()
    selected = enrichment.get("selected_candidate")
    if isinstance(selected, dict):
        candidates = (
            RetailerProductCandidate(
                retailer=str(selected.get("retailer") or MIDTOWN_RETAILER),
                product_title=str(selected.get("product_title") or ""),
                product_url=selected.get("product_url"),
                image_url=selected.get("image_url"),
                thumbnail_url=selected.get("thumbnail_url"),
                publisher=selected.get("publisher"),
                series_title=selected.get("series_title"),
                issue_number=selected.get("issue_number"),
                cover_name=selected.get("cover_name"),
                variant_type=selected.get("variant_type"),
                cover_artist=selected.get("cover_artist"),
                release_date=selected.get("release_date"),
                price=selected.get("price"),
                sku=selected.get("sku"),
                source_confidence=selected.get("source_confidence"),
                raw_score_reasons=tuple(selected.get("raw_score_reasons") or ()),
            ),
        )
    return RetailerLookupResult(
        matched=bool(enrichment.get("matched")),
        possible_match=bool(enrichment.get("possible_match")),
        retailer=str(enrichment.get("retailer") or MIDTOWN_RETAILER),
        selected_candidate=candidates[0] if candidates else None,
        candidates=candidates,
        rejected_reason=enrichment.get("rejected_reason"),
        query=enrichment.get("query"),
        diagnostics=dict(enrichment.get("diagnostics") or {}),
    )


def _fetch_html(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with request.urlopen(req, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
        data = resp.read(_MAX_HTML_BYTES)
        # If the response is larger than our safety budget, keep the first chunk only.
        # The parser is designed to work from product/listing snippets.
        if resp.read(1):
            return data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def _extract_meta(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in _META_PATTERN.findall(html):
        out[key.strip().lower()] = _canonicalize_text(value)
    return out


def _extract_title(html: str, meta: dict[str, str]) -> str | None:
    for key in ("og:title", "twitter:title", "title"):
        if meta.get(key):
            return meta[key]
    match = _TITLE_PATTERN.search(html)
    if match:
        return _canonicalize_text(unescape(match.group(1)))
    return None


def _extract_product_url(base_url: str | None, href: str | None) -> str | None:
    if not href:
        return None
    href = _normalize_url(href)
    if href.startswith("http"):
        return href
    if base_url and href.startswith("/"):
        parsed = parse.urlparse(base_url)
        return parse.urlunparse((parsed.scheme or "https", parsed.netloc, href, "", "", ""))
    return None


def _title_from_product_url(product_url: str | None) -> str | None:
    if not product_url:
        return None
    parsed = parse.urlparse(product_url)
    slug = (parsed.fragment or parsed.path.rsplit("/", 1)[-1]).strip()
    slug = slug.split("#", 1)[-1] if "#" in slug else slug
    slug = slug.replace("-", " ").replace("_", " ").strip()
    slug = re.sub(r"\s+", " ", slug)
    if not slug:
        return None
    return _canonicalize_text(unescape(slug))


def _is_midtown_product_href(href: str | None) -> bool:
    if not href:
        return False
    parsed = parse.urlparse(href)
    path = parsed.path or href
    return path.casefold().startswith("/product/")


def _candidate_from_html_fragment(
    fragment: str,
    *,
    href: str | None = None,
    base_url: str | None = None,
) -> RetailerProductCandidate | None:
    meta = _extract_meta(fragment)
    image_url = meta.get("og:image") or meta.get("twitter:image")
    title = _extract_title(fragment, meta) or meta.get("og:description") or ""
    product_url = _extract_product_url(base_url, href)
    if not title:
        title = _title_from_product_url(product_url) or ""
    if not title:
        return None
    img_match = _IMG_PATTERN.search(fragment)
    if not image_url and img_match:
        image_url = _normalize_url(img_match.group(1))
    if not title or title.casefold() in {"midtown comics - search", "midtown comics"}:
        title = _title_from_product_url(product_url) or title
    price_match = _PRICE_PATTERN.search(fragment)
    sku_match = _SKU_PATTERN.search(fragment)
    issue_match = _ISSUE_PATTERN.search(title)
    cover_letter = cover_letter_from_text(" ".join([title, meta.get("og:description", ""), fragment]))
    return RetailerProductCandidate(
        retailer=MIDTOWN_RETAILER,
        product_title=title,
        product_url=product_url,
        image_url=image_url,
        thumbnail_url=image_url,
        publisher=meta.get("product:brand") or meta.get("brand"),
        series_title=meta.get("product:series") or meta.get("series"),
        issue_number=issue_match.group(1) if issue_match else None,
        cover_name=cover_letter and f"Cover {cover_letter.upper()}",
        variant_type=meta.get("product:variant"),
        cover_artist=meta.get("product:artist") or meta.get("artist"),
        release_date=meta.get("product:release_date") or meta.get("og:release_date"),
        price=price_match.group(1) if price_match else meta.get("product:price"),
        sku=sku_match.group(1) if sku_match else meta.get("product:sku"),
        source_confidence=0.5,
        raw_score_reasons=(),
    )


def _extract_candidates(html: str, *, base_url: str | None = None) -> list[RetailerProductCandidate]:
    candidates: list[RetailerProductCandidate] = []
    seen: set[str] = set()
    product_href_pattern = re.compile(r'href=["\']([^"\']*?/product/\d+[^"\']*)["\']', re.IGNORECASE)
    matches = list(product_href_pattern.finditer(html))
    for match in matches:
        href = match.group(1)
        snippet_start = max(0, match.start() - 600)
        snippet_end = min(len(html), match.end() + 1800)
        fragment = html[snippet_start:snippet_end]
        candidate = _candidate_from_html_fragment(fragment, href=href, base_url=base_url)
        if candidate is None:
            continue
        candidate = RetailerProductCandidate(
            **{**candidate.__dict__, "product_url": _extract_product_url(base_url, href) or candidate.product_url}
        )
        if not candidate.product_title or candidate.product_title.casefold() in {"midtown comics - search", "midtown comics"}:
            title_from_url = _title_from_product_url(candidate.product_url)
            if title_from_url:
                candidate = RetailerProductCandidate(
                    **{**candidate.__dict__, "product_title": title_from_url}
                )
        key = candidate.product_url or candidate.product_title
        if key in seen:
            continue
        seen.add(key or candidate.product_title)
        candidates.append(candidate)
    if candidates:
        return candidates

    for href, fragment in _A_BLOCK_PATTERN.findall(html):
        if not _is_midtown_product_href(href):
            continue
        candidate = _candidate_from_html_fragment(fragment, href=href, base_url=base_url)
        if candidate is None:
            continue
        candidate = RetailerProductCandidate(
            **{**candidate.__dict__, "product_url": _extract_product_url(base_url, href) or candidate.product_url}
        )
        if not candidate.product_title or candidate.product_title.casefold() in {"midtown comics - search", "midtown comics"}:
            title_from_url = _title_from_product_url(candidate.product_url)
            if title_from_url:
                candidate = RetailerProductCandidate(
                    **{**candidate.__dict__, "product_title": title_from_url}
                )
        key = candidate.product_url or candidate.product_title
        if key in seen:
            continue
        seen.add(key or candidate.product_title)
        candidates.append(candidate)
    if candidates:
        return candidates
    candidate = _candidate_from_html_fragment(html, base_url=base_url)
    return [candidate] if candidate is not None else []


def _search_url(query: str) -> str:
    return _SEARCH_URL_TEMPLATE.format(query=parse.quote_plus(query))


def _retailer_lookup_enrichment(
    *,
    query: str,
    result: RetailerLookupResult,
) -> dict[str, Any]:
    selected = result.selected_candidate
    top_score = result.diagnostics.get("top_score")
    return {
        "retailer": result.retailer,
        "product_url": selected.product_url if selected else None,
        "image_url": selected.image_url if selected else None,
        "thumbnail_url": selected.thumbnail_url if selected else None,
        "product_title": selected.product_title if selected else None,
        "release_date": selected.release_date if selected else None,
        "publisher": selected.publisher if selected else None,
        "sku": selected.sku if selected else None,
        "score": top_score if top_score is not None else None,
        "score_reasons": list(selected.raw_score_reasons if selected else ()),
        "matched": result.matched,
        "possible_match": result.possible_match,
        "checked_at": _utc_now().isoformat(),
        "query": query,
        "rejected_reason": result.rejected_reason,
        "diagnostics": result.diagnostics,
        "selected_candidate": {
            "retailer": selected.retailer if selected else None,
            "product_title": selected.product_title if selected else None,
            "product_url": selected.product_url if selected else None,
            "image_url": selected.image_url if selected else None,
            "thumbnail_url": selected.thumbnail_url if selected else None,
            "publisher": selected.publisher if selected else None,
            "series_title": selected.series_title if selected else None,
            "issue_number": selected.issue_number if selected else None,
            "cover_name": selected.cover_name if selected else None,
            "variant_type": selected.variant_type if selected else None,
            "cover_artist": selected.cover_artist if selected else None,
            "release_date": selected.release_date if selected else None,
            "price": selected.price if selected else None,
            "sku": selected.sku if selected else None,
            "source_confidence": selected.source_confidence if selected else None,
            "raw_score_reasons": list(selected.raw_score_reasons if selected else ()),
        }
        if selected
        else None,
    }


def lookup_midtown_product(
    item: dict[str, Any],
    *,
    limit: int = 10,
    force: bool = False,
) -> RetailerLookupResult:
    retailer_name = normalize_retailer_name(item.get("retailer"))
    retailer_product_url = str(item.get("retailer_product_url") or "")
    has_midtown_url = "midtowncomics.com" in retailer_product_url.casefold()
    if retailer_name and "midtown" not in retailer_name and not has_midtown_url:
        return RetailerLookupResult(
            matched=False,
            possible_match=False,
            retailer=item.get("retailer") or MIDTOWN_RETAILER,
            selected_candidate=None,
            rejected_reason="retailer_not_midtown",
            query=None,
            diagnostics={"retailer": item.get("retailer")},
        )
    if not retailer_name and not has_midtown_url:
        return RetailerLookupResult(
            matched=False,
            possible_match=False,
            retailer=item.get("retailer") or MIDTOWN_RETAILER,
            selected_candidate=None,
            rejected_reason="retailer_not_midtown",
            query=None,
            diagnostics={"retailer": item.get("retailer"), "retailer_product_url": retailer_product_url or None},
        )

    if _should_reuse_cached_result(item, force=force):
        cached = _cached_result(item)
        if cached is not None:
            return cached

    query = _normalize_query(item)
    enrichment = item.get("retailer_lookup_enrichment")
    if isinstance(enrichment, dict) and enrichment.get("query") and not force:
        # If the draft already tried this exact lookup recently, avoid another fetch.
        if retailer_lookup_is_fresh(enrichment, force=False):
            cached = _cached_result(item)
            if cached is not None:
                return cached

    if not query:
        return RetailerLookupResult(
            matched=False,
            possible_match=False,
            retailer=item.get("retailer") or MIDTOWN_RETAILER,
            selected_candidate=None,
            rejected_reason="missing_query",
            query=None,
            diagnostics={"reason": "missing title/issue/publisher"},
        )

    try:
        time.sleep(_RATE_LIMIT_SECONDS)
        product_url = item.get("retailer_product_url")
        html = _fetch_html(product_url) if product_url else _fetch_html(_search_url(query))
    except Exception as exc:  # noqa: BLE001
        return RetailerLookupResult(
            matched=False,
            possible_match=False,
            retailer=item.get("retailer") or MIDTOWN_RETAILER,
            selected_candidate=None,
            rejected_reason="lookup_failed",
            query=query,
            diagnostics={"error": type(exc).__name__, "message": str(exc)},
        )

    candidates = _extract_candidates(html, base_url=item.get("retailer_product_url") or None)
    scored: list[tuple[int, RetailerProductCandidate, list[str], str | None]] = []
    for candidate in candidates[: max(1, limit)]:
        score, reasons, reject = score_retailer_candidate(item, candidate)
        scored.append((score, candidate, reasons, reject))
    if not scored:
        return RetailerLookupResult(
            matched=False,
            possible_match=False,
            retailer=item.get("retailer") or MIDTOWN_RETAILER,
            selected_candidate=None,
            rejected_reason="no_candidates",
            query=query,
            diagnostics={"candidate_count": 0},
        )
    scored.sort(key=lambda row: (row[0], row[1].product_title.lower()), reverse=True)
    top_score, top_candidate, reasons, reject = scored[0]
    top_candidate = RetailerProductCandidate(
        **{
            **top_candidate.__dict__,
            "source_confidence": float(top_score) / 100.0,
            "raw_score_reasons": tuple(reasons),
        }
    )
    if accept_retailer_candidate(top_score):
        return RetailerLookupResult(
            matched=True,
            possible_match=False,
            retailer=top_candidate.retailer,
            selected_candidate=top_candidate,
            candidates=tuple(row[1] for row in scored[:limit]),
            rejected_reason=None,
            query=query,
            diagnostics={"candidate_count": len(scored), "top_score": top_score},
        )
    if possible_retailer_candidate(top_score):
        return RetailerLookupResult(
            matched=False,
            possible_match=True,
            retailer=top_candidate.retailer,
            selected_candidate=top_candidate,
            candidates=tuple(row[1] for row in scored[:limit]),
            rejected_reason=reject or "possible_match",
            query=query,
            diagnostics={"candidate_count": len(scored), "top_score": top_score},
        )
    return RetailerLookupResult(
        matched=False,
        possible_match=False,
        retailer=top_candidate.retailer,
        selected_candidate=top_candidate,
        candidates=tuple(row[1] for row in scored[:limit]),
        rejected_reason=reject or "score_below_threshold",
        query=query,
        diagnostics={"candidate_count": len(scored), "top_score": top_score},
    )


def enrich_item_with_midtown_lookup(item: dict[str, Any], *, limit: int = 10, force: bool = False) -> dict[str, Any]:
    if (
        not force
        and item.get("retailer_cover_url")
        and (item.get("retailer_item_id") or item.get("retailer_order_number"))
    ):
        return {}
    result = lookup_midtown_product(item, limit=limit, force=force)
    selected = result.selected_candidate
    enrichment = _retailer_lookup_enrichment(query=result.query or "", result=result)
    updates = {
        "retailer_lookup_enrichment": enrichment,
        "retailer_lookup_status": "matched" if result.matched else "possible_match" if result.possible_match else "rejected",
        "retailer_lookup_score": int(result.diagnostics.get("top_score") or 0) if selected else None,
        "retailer_lookup_rejected_reason": result.rejected_reason,
    }
    if selected is not None:
        updates.update(
            {
                "retailer_product_url": selected.product_url,
                "retailer_sku": selected.sku,
            }
        )
        if result.matched and selected.product_url:
            updates["retailer_cover_url"] = selected.image_url
            updates["cover_image_url"] = selected.image_url or selected.product_url
            updates["cover_thumbnail_url"] = selected.thumbnail_url or selected.image_url or selected.product_url
            updates["cover_url"] = selected.image_url or selected.thumbnail_url or selected.product_url
            updates["has_cover_image"] = True
    return {k: v for k, v in updates.items() if v is not None}
