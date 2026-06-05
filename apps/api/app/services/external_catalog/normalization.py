from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class NormalizedLocgIssue:
    source_name: str
    source_issue_id: str | None
    source_url: str | None
    title: str
    publisher: str
    series_name: str
    issue_number: str | None
    issue_title: str | None
    release_date: date | None
    foc_date: date | None
    cover_date: date | None
    price: float | None
    description: str | None
    pull_count: int | None
    want_count: int | None
    variant_count: int | None
    cover_image_url: str | None
    thumbnail_url: str | None
    high_resolution_image_url: str | None
    product_url: str | None
    story_summary: str | None
    imprint: str | None
    universe: str | None
    is_first_issue: bool
    is_milestone_issue: bool
    milestone_issue_number: int | None
    importance_signals_json: dict[str, Any] | None
    decision_signals_json: dict[str, Any] | None
    normalized_title_key: str
    variants: list[dict[str, Any]]
    creators: list[dict[str, Any]]


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip())


def _title_case_publisher(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    return cleaned.upper() if len(cleaned) <= 4 else cleaned.title()


def parse_issue_number_from_title(title: str) -> str | None:
    match = re.search(r"#\s*([0-9]+(?:\.[0-9]+)?)", title, re.IGNORECASE)
    if match:
        return match.group(1).lstrip("0") or "0"
    return None


def split_series_and_issue_title(title: str, *, publisher: str) -> tuple[str, str | None, str | None]:
    cleaned = _clean_text(title)
    if not cleaned:
        return "", None, None
    issue_num = parse_issue_number_from_title(cleaned)
    if issue_num is not None:
        series = re.sub(r"\s*#\s*[0-9]+(?:\.[0-9]+)?.*$", "", cleaned, flags=re.IGNORECASE).strip()
        return series or cleaned, issue_num, cleaned
    if cleaned.lower().endswith(" #1") or re.search(r"\b#1\b", cleaned):
        return re.sub(r"\s*#1\b.*", "", cleaned, flags=re.IGNORECASE).strip() or cleaned, "1", cleaned
    return cleaned, None, cleaned


def build_normalized_title_key(*, publisher: str, series_name: str, issue_number: str | None) -> str:
    pub = _clean_text(publisher).lower()
    series = _clean_text(series_name).lower()
    num = (issue_number or "").strip().lower() or "oneshot"
    return f"{pub}|{series}|{num}"[:320]


def parse_price(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    try:
        parsed = float(cleaned)
        return parsed if parsed > 0 else None
    except ValueError:
        return None


def _parse_date_field(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned[:10])
    except ValueError:
        return None


def _url_field(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return None


def coalesce_issue_image_urls(raw: dict[str, Any]) -> dict[str, Any]:
    """Resolve cover (required when any art exists), thumbnail, and high-res URL references."""
    merged = dict(raw)
    thumbnail = _url_field(
        merged,
        "thumbnail_url",
        "thumb_url",
        "thumbnail",
        "image_thumbnail_url",
    )
    high_res = _url_field(
        merged,
        "high_resolution_image_url",
        "high_res_image_url",
        "high_resolution_url",
        "image_large_url",
        "large_image_url",
        "full_image_url",
    )
    cover = _url_field(
        merged,
        "cover_image_url",
        "cover_url",
        "image_url",
        "primary_image_url",
    )
    if not high_res:
        high_res = _url_field(merged, "og_image", "og:image")
    if not cover:
        cover = _url_field(merged, "og_image", "og:image") or thumbnail or high_res
    if not thumbnail:
        thumbnail = cover
    if not high_res and cover:
        high_res = cover
    if cover:
        merged["cover_image_url"] = cover
    if thumbnail:
        merged["thumbnail_url"] = thumbnail
    if high_res:
        merged["high_resolution_image_url"] = high_res
    return merged


def parse_count(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    digits = re.sub(r"[^0-9]", "", str(value))
    if not digits:
        return None
    return int(digits)


def normalize_locg_issue(raw: dict[str, Any], *, source_name: str) -> NormalizedLocgIssue:
    from app.services.external_catalog.creator_roles import expand_creators_from_raw
    from app.services.external_catalog.importance_signals import detect_importance_signals
    from app.services.external_catalog.variant_normalize import normalize_variants_from_raw

    raw = coalesce_issue_image_urls(raw)
    title = _clean_text(raw.get("title"))
    publisher = _title_case_publisher(str(raw.get("publisher") or ""))
    series_name, issue_number, issue_title = split_series_and_issue_title(title, publisher=publisher)
    if raw.get("series_name"):
        series_name = _clean_text(str(raw.get("series_name")))
    if raw.get("issue_number"):
        issue_number = _clean_text(str(raw.get("issue_number"))).lstrip("#") or issue_number

    release_date = _parse_date_field(raw.get("release_date"))
    foc_date = _parse_date_field(raw.get("foc_date"))
    cover_date = _parse_date_field(raw.get("cover_date"))

    solicitation = _clean_text(raw.get("description") or raw.get("solicitation") or raw.get("solicitation_text"))
    story_summary = _clean_text(raw.get("story_summary") or raw.get("story") or raw.get("synopsis"))
    imprint = _clean_text(raw.get("imprint") or raw.get("publisher_imprint"))
    universe = _clean_text(raw.get("universe") or raw.get("publisher_universe"))

    variants = normalize_variants_from_raw(raw)
    creators = expand_creators_from_raw(raw)

    importance = detect_importance_signals(
        title=title,
        series_name=series_name,
        issue_number=issue_number,
        description=solicitation or None,
        story_summary=story_summary or None,
        imprint=imprint or None,
        universe=universe or None,
    )
    upc = _clean_text(str(raw.get("upc") or "")) or None
    distributor_sku = _clean_text(
        str(raw.get("distributor_sku") or raw.get("sku_lunar") or raw.get("sku") or "")
    ) or None
    if upc or distributor_sku:
        importance = dict(importance)
        if upc:
            importance["upc"] = upc
        if distributor_sku:
            importance["distributor_sku"] = distributor_sku

    from app.services.external_catalog.decision_signals import build_decision_signals_from_normalized

    class _NormProbe:
        pass

    probe = _NormProbe()
    probe.title = title
    probe.series_name = series_name
    probe.issue_number = issue_number
    probe.publisher = publisher
    probe.description = solicitation or None
    probe.story_summary = story_summary or None
    probe.imprint = imprint or importance.get("imprint")
    probe.universe = universe or importance.get("universe")
    probe.pull_count = parse_count(raw.get("pull_count"))
    probe.want_count = parse_count(raw.get("want_count"))
    probe.foc_date = foc_date
    probe.release_date = release_date
    probe.price = parse_price(raw.get("price"))
    probe.cover_image_url = _url_field(raw, "cover_image_url")
    probe.thumbnail_url = _url_field(raw, "thumbnail_url")
    probe.high_resolution_image_url = _url_field(raw, "high_resolution_image_url")
    probe.importance_signals_json = importance

    decision_signals = build_decision_signals_from_normalized(
        norm_like=probe,
        creators=creators,
        variants=variants,
    )

    product_url = _url_field(raw, "product_url", "product_link") or (
        str(raw["source_url"]).strip() if raw.get("source_url") else None
    )

    key = build_normalized_title_key(
        publisher=publisher,
        series_name=series_name,
        issue_number=issue_number,
    )

    return NormalizedLocgIssue(
        source_name=source_name,
        source_issue_id=(str(raw["source_issue_id"]).strip() if raw.get("source_issue_id") else None),
        source_url=(str(raw["source_url"]).strip() if raw.get("source_url") else None),
        title=title,
        publisher=publisher,
        series_name=series_name,
        issue_number=issue_number,
        issue_title=issue_title,
        release_date=release_date,
        foc_date=foc_date,
        cover_date=cover_date,
        price=parse_price(raw.get("price")),
        description=solicitation or None,
        story_summary=story_summary or None,
        pull_count=parse_count(raw.get("pull_count")),
        want_count=parse_count(raw.get("want_count")),
        variant_count=parse_count(raw.get("variant_count")) or (len(variants) if variants else None),
        cover_image_url=_url_field(raw, "cover_image_url"),
        thumbnail_url=_url_field(raw, "thumbnail_url"),
        high_resolution_image_url=_url_field(raw, "high_resolution_image_url"),
        product_url=product_url,
        imprint=imprint or importance.get("imprint"),
        universe=universe or importance.get("universe"),
        is_first_issue=bool(importance.get("first_issue")),
        is_milestone_issue=bool(importance.get("is_milestone_issue")),
        milestone_issue_number=importance.get("milestone_issue_number"),
        importance_signals_json=importance,
        decision_signals_json=decision_signals,
        normalized_title_key=key,
        variants=variants,
        creators=creators,
    )
