from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services.external_catalog.importance_signals import parse_ratio_from_text
from app.services.external_catalog.league_of_comic_geeks import (
    LOCG_BASE_URL,
    LocgListIssueStub,
    LocgListVariantRowStub,
    _abs_url,
    _issue_id_from_url,
    _parse_date_value,
    _parse_price_stub,
)
from app.services.external_catalog.variant_normalize import normalize_variant_row


def _parse_details_blocks(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in re.finditer(
        r'<div class="name">\s*([^<]+?)\s*</div>\s*<div class="value">\s*([\s\S]*?)\s*</div>',
        html,
        re.IGNORECASE,
    ):
        name = re.sub(r"\s+", " ", match.group(1)).strip()
        value = re.sub(r"<[^>]+>", " ", match.group(2))
        value = re.sub(r"\s+", " ", value).strip()
        if name and value:
            out[name.lower()] = value
    return out


def _parse_metric_after_icon(html: str, icon_class: str) -> int | None:
    pattern = (
        rf'<i class="[^"]*{re.escape(icon_class)}[^"]*"[^>]*>\s*</i>\s*'
        r'<span class="ml-1">([0-9,]+)</span>'
    )
    match = re.search(pattern, html, re.IGNORECASE)
    if not match:
        return None
    digits = match.group(1).replace(",", "")
    return int(digits) if digits.isdigit() else None


def _parse_variants_from_live(html: str, *, base_url: str) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r'<a href="(/comic/\d+[^"]*\?variant=\d+)"[^>]*data-original-title="([^"]*)"'
        r'[^>]*>[\s\S]*?data-src="([^"]+)"',
        html,
        re.IGNORECASE,
    ):
        rel = match.group(1)
        if rel in seen:
            continue
        seen.add(rel)
        title = match.group(2).strip()
        image_url = match.group(3).strip()
        cover_label = None
        variant_name = title
        label_m = re.match(r"^\s*Cover\s+([A-Z0-9]+)\s+(.*)$", title, re.IGNORECASE)
        if label_m:
            letter = label_m.group(1).strip()
            cover_label = f"Cover {letter}"
            variant_name = label_m.group(2).strip()
        row = normalize_variant_row(
            {
                "cover_label": cover_label,
                "variant_name": variant_name or title,
                "ratio_value": parse_ratio_from_text(variant_name or title),
                "image_url": image_url,
                "variant_detail_url": _abs_url(rel),
            }
        )
        variants.append(row)
    if not variants:
        for match in re.finditer(
            r'<a href="(/comic/\d+[^"]*\?variant=\d+)"[^>]*data-original-title="([^"]*)"',
            html,
            re.IGNORECASE,
        ):
            rel = match.group(1)
            if rel in seen:
                continue
            seen.add(rel)
            title = match.group(2).strip()
            variants.append(
                normalize_variant_row(
                    {
                        "variant_name": title,
                        "ratio_value": parse_ratio_from_text(title),
                        "variant_detail_url": _abs_url(rel),
                    }
                )
            )
    return variants


def _parse_creators_live(html: str) -> list[dict[str, Any]]:
    creators: list[dict[str, Any]] = []
    from app.services.external_catalog.creator_roles import bucket_role

    for section_id in ("creators", "top-level-credits", "cover-artists"):
        section = re.search(
            rf'<section id="{section_id}[^"]*">([\s\S]*?)</section>',
            html,
            re.IGNORECASE,
        )
        if not section:
            continue
        block = section.group(1)
        for row in re.finditer(
            r'<div class="role[^"]*">\s*([^<]+?)\s*</div>[\s\S]*?'
            r'<div class="name[^"]*">\s*<a href="/people/\d+/[^"]+">([^<]+)</a>',
            block,
            re.IGNORECASE,
        ):
            role_display = row.group(1).strip()
            name = row.group(2).strip()
            if name:
                creators.append(
                    {
                        "creator_name": name,
                        "role": bucket_role(role_display),
                        "role_display": role_display,
                        "source_url": None,
                    }
                )
    return creators


def _parse_characters_live(html: str) -> list[dict[str, Any]]:
    characters: list[dict[str, Any]] = []
    section = re.search(r'<section id="characters[^"]*">([\s\S]*?)</section>', html, re.IGNORECASE)
    if not section:
        return characters
    block = section.group(1)
    for row in re.finditer(
        r'<a href="/character/\d+/[^"]+">([^<]+)</a>',
        block,
        re.IGNORECASE,
    ):
        name = row.group(1).strip()
        if name:
            characters.append({"character_name": name, "role": None, "universe": None})
    return characters


def enrich_issue_detail_from_live_html(html: str, base: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    if not merged.get("title"):
        og = re.search(r'<meta property="og:title" content="([^"]*)"', html, re.IGNORECASE)
        if og:
            merged["title"] = og.group(1).strip()
        else:
            h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
            if h1:
                merged["title"] = h1.group(1).strip()

    blocks = _parse_details_blocks(html)
    if blocks.get("upc") and not merged.get("upc"):
        merged["upc"] = blocks["upc"].split()[0]
    if blocks.get("distributor sku") and not merged.get("distributor_sku"):
        merged["distributor_sku"] = blocks["distributor sku"].split(",")[0].strip()
    if blocks.get("final order cutoff") and not merged.get("foc_date"):
        foc_raw = blocks["final order cutoff"]
        release_hint = merged.get("release_date")
        if release_hint and isinstance(release_hint, date):
            foc_raw = f"{foc_raw} {release_hint.year}"
        merged["foc_date"] = _parse_date_value(foc_raw)
    if blocks.get("cover date") and not merged.get("cover_date"):
        merged["cover_date"] = _parse_date_value(blocks["cover date"])

    if not merged.get("description"):
        desc = re.search(
            r'<section id="summary">[\s\S]*?<div class="listing-description">([\s\S]*?)</div>',
            html,
            re.IGNORECASE,
        )
        if desc:
            text = re.sub(r"<[^>]+>", "\n", desc.group(1))
            text = re.sub(r"\n+", "\n", text).strip()
            merged["description"] = text

    fmt = re.search(
        r"Comic\s*&nbsp;&nbsp;·&nbsp;&nbsp;\s*([0-9]+)\s*pages\s*&nbsp;&nbsp;·&nbsp;&nbsp;\s*\$([0-9.]+)",
        html,
        re.IGNORECASE,
    )
    if fmt:
        merged.setdefault("format", "Comic")
        merged.setdefault("page_count", int(fmt.group(1)))
        if not merged.get("price"):
            merged["price"] = float(fmt.group(2))

    og_desc = re.search(r'<meta property="og:description" content="([^"]*)"', html, re.IGNORECASE)
    if og_desc and not merged.get("publisher"):
        pub = re.search(r"published by\s+([^.<\"]+)", og_desc.group(1), re.IGNORECASE)
        if pub:
            merged["publisher"] = pub.group(1).strip()

    release_m = re.search(
        r'Releases\s*<a href="/comics/new-comics/[^"]+">([^<]+)</a>',
        html,
        re.IGNORECASE,
    )
    if release_m and not merged.get("release_date"):
        merged["release_date"] = _parse_date_value(release_m.group(1).strip())

    if merged.get("pull_count") is None:
        merged["pull_count"] = _parse_metric_after_icon(html, "cg-icon-pull")
    if merged.get("want_count") is None:
        merged["want_count"] = _parse_metric_after_icon(html, "cg-icon-wishlist")

    if not merged.get("cover_image_url"):
        cover = re.search(
            r'<div class="cover-art">[\s\S]*?<img src="([^"]+)"',
            html,
            re.IGNORECASE,
        )
        if cover:
            merged["cover_image_url"] = cover.group(1).strip()
            merged.setdefault("high_resolution_image_url", cover.group(1).strip())

    og_image = re.search(r'<meta property="og:image" content="([^"]*)"', html, re.IGNORECASE)
    if og_image:
        merged.setdefault("thumbnail_url", og_image.group(1).strip())

    variants = merged.get("variants") or []
    if not variants:
        variants = _parse_variants_from_live(html, base_url=merged.get("source_url") or "")
    merged["variants"] = variants
    if variants and not merged.get("variant_count"):
        merged["variant_count"] = len(variants)

    if not merged.get("creators"):
        merged["creators"] = _parse_creators_live(html)
    if not merged.get("characters"):
        merged["characters"] = _parse_characters_live(html)

    return merged


def parse_release_date_live_page(html: str, *, page_date: date | None = None) -> list[LocgListIssueStub]:
    stubs: list[LocgListIssueStub] = []
    seen_ids: set[str] = set()
    for block_match in re.finditer(
        r"<li[^>]*\bissue\b[^>]*>.*?</li>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        block = block_match.group(0)
        attrs = _parse_issue_li_block(block)
        if attrs.get("data-parent", "0") != "0":
            continue
        comic_id = attrs.get("data-comic", "")
        if not comic_id or comic_id in seen_ids:
            continue
        seen_ids.add(comic_id)
        href_m = re.search(r'href="(/comic/\d+/[^"?]+)"', block, re.IGNORECASE)
        if not href_m:
            continue
        sort_m = re.search(r'data-sorting="([^"]*)"', block, re.IGNORECASE)
        title_m = re.search(
            r'<div class="title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
            block,
            re.IGNORECASE,
        )
        title = (
            sort_m.group(1).strip()
            if sort_m and sort_m.group(1).strip()
            else (title_m.group(1).strip() if title_m else f"Comic {comic_id}")
        )
        publisher_m = re.search(r'<div class="publisher[^"]*">\s*([^<]+)\s*</div>', block, re.IGNORECASE)
        price_m = re.search(r'<span class="price">\s*(?:&nbsp;·&nbsp;)?\s*\$([0-9.]+)', block, re.IGNORECASE)
        date_m = re.search(r'<span class="date"[^>]*>\s*([^<]+)\s*</span>', block, re.IGNORECASE)
        cover_m = re.search(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)
        variant_m = re.search(r'<a class="variant-toggle"[^>]*>\s*\+([0-9]+)', block, re.IGNORECASE)
        stubs.append(
            LocgListIssueStub(
                title=title,
                publisher=(publisher_m.group(1).strip() if publisher_m else ""),
                release_date=_parse_date_value(date_m.group(1) if date_m else None) or page_date,
                price=_parse_price_stub(price_m.group(1) if price_m else None),
                source_url=_abs_url(href_m.group(1)),
                cover_image_url=cover_m.group(1).strip() if cover_m else None,
                variant_count=int(variant_m.group(1)) if variant_m else None,
                foc_date=None,
            )
        )
    return stubs


def _parse_issue_li_block(block: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key in ("data-comic", "data-parent", "data-pulls"):
        m = re.search(rf'{key}="([^"]*)"', block, re.IGNORECASE)
        if m:
            attrs[key] = m.group(1)
    return attrs


def parse_release_date_variant_rows(
    html: str, *, page_date: date | None = None
) -> list[LocgListVariantRowStub]:
    rows: list[LocgListVariantRowStub] = []
    seen_variant_ids: set[str] = set()
    for block_match in re.finditer(
        r"<li[^>]*\bissue\b[^>]*>.*?</li>", html, re.IGNORECASE | re.DOTALL
    ):
        block = block_match.group(0)
        attrs = _parse_issue_li_block(block)
        parent_id = attrs.get("data-parent", "0")
        if parent_id == "0":
            continue
        sort_m = re.search(r'data-sorting="([^"]*)"', block, re.IGNORECASE)
        variant_comic_id = attrs.get("data-comic", "")
        if not variant_comic_id or variant_comic_id in seen_variant_ids:
            continue
        seen_variant_ids.add(variant_comic_id)
        href_m = re.search(r'href="(/comic/\d+/[^"]+)"', block, re.IGNORECASE)
        if not href_m:
            continue
        rel_href = href_m.group(1)
        parent_href_m = re.match(r"(/comic/\d+/[^?]+)", rel_href, re.IGNORECASE)
        parent_rel = parent_href_m.group(1) if parent_href_m else rel_href.split("?", 1)[0]
        title_m = re.search(
            r'<div class="title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)(?:<span class="variant-name">\s*([^<]*)</span>)?',
            block,
            re.IGNORECASE,
        )
        if sort_m and sort_m.group(1).strip():
            full_title = sort_m.group(1).strip()
            title = full_title
            variant_name = full_title
        else:
            title = title_m.group(1).strip() if title_m else f"Variant {variant_comic_id}"
            variant_name = (title_m.group(2).strip() if title_m and title_m.group(2) else title)
        if variant_name == title and "variant-name" in block:
            vn = re.search(r'<span class="variant-name">\s*([^<]+)</span>', block, re.IGNORECASE)
            if vn:
                variant_name = vn.group(1).strip()
        publisher_m = re.search(r'<div class="publisher[^"]*">\s*([^<]+)\s*</div>', block, re.IGNORECASE)
        price_m = re.search(r'<span class="price">\s*(?:&nbsp;·&nbsp;)?\s*\$([0-9.]+)', block, re.IGNORECASE)
        date_m = re.search(r'<span class="date"[^>]*>\s*([^<]+)\s*</span>', block, re.IGNORECASE)
        cover_m = re.search(r'data-src="([^"]+)"', block, re.IGNORECASE) or re.search(
            r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE
        )
        image = cover_m.group(1).strip() if cover_m else None
        if image and image.startswith("data:"):
            image = None
        rows.append(
            LocgListVariantRowStub(
                variant_comic_id=variant_comic_id,
                parent_comic_id=parent_id,
                title=title,
                variant_name=variant_name or title,
                publisher=(publisher_m.group(1).strip() if publisher_m else ""),
                source_url=_abs_url(rel_href),
                parent_source_url=_abs_url(parent_rel),
                cover_image_url=image,
                price=_parse_price_stub(price_m.group(1) if price_m else None),
                release_date=_parse_date_value(date_m.group(1) if date_m else None) or page_date,
            )
        )
    return rows


def list_variant_row_to_upsert_dict(row: LocgListVariantRowStub) -> dict[str, Any]:
    from app.services.external_catalog.importance_signals import parse_ratio_from_text
    from app.services.external_catalog.variant_normalize import normalize_variant_row

    cover_label = (row.variant_comic_id or "")[:64]
    label_m = re.match(r"^\s*Cover\s+([A-Z0-9]+)\s+", row.variant_name, re.IGNORECASE)
    if label_m:
        cover_label = label_m.group(1).strip()[:64]
    variant_name = (row.variant_name or row.title or "").strip()
    if len(variant_name) > 200:
        variant_name = variant_name[:200]
    return normalize_variant_row(
        {
            "cover_label": cover_label,
            "variant_name": variant_name,
            "ratio_value": parse_ratio_from_text(row.variant_name),
            "price": row.price,
            "image_url": row.cover_image_url,
            "source_url": row.source_url,
            "variant_detail_url": row.source_url,
        }
    )
