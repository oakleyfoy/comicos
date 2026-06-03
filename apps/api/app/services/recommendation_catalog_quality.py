"""Classify release catalog rows for Top Recommendations (single-issue vs books/trades)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_forward_window import KEY_SIGNAL_TYPES, NEW_ONE_SIGNALS, days_until_foc

RECOMMENDATION_PRICE_CAP = 12.0
recommendation_price_cap = RECOMMENDATION_PRICE_CAP

# Normalized publisher tokens that indicate core periodical comics publishers.
CORE_COMIC_PUBLISHER_TOKENS = frozenset(
    {
        "marvel",
        "dc",
        "dc comics",
        "image",
        "image comics",
        "idw",
        "idw publishing",
        "boom",
        "boom studios",
        "boom! studios",
        "dark horse",
        "dark horse comics",
        "dynamite",
        "dynamite entertainment",
        "mad cave",
        "mad cave studios",
        "oni",
        "oni press",
        "titan",
        "titan comics",
        "dstlry",
    }
)

_BOOK_TRADE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\btp\b",
        r"\btpb\b",
        r"trade\s+paperback",
        r"trading\s+card",
        r"\bhc\b",
        r"hardcover",
        r"hard\s+cover",
        r"\bpb\b",
        r"paperback",
        r"graphic\s+novel",
        r"art\s+book",
        r"artbook",
        r"\bprose\b",
        r"\bnovel\b",
        r"pictorial\s+history",
        r"\bhistory\s+of\b",
        r"encyclopedia",
        r"reference\s+book",
        r"sketchbook",
        r"poster\s+book",
        r"coloring\s+book",
        r"children'?s\s+book",
        r"sticker\s+book",
        r"\bstickerbook\b",
        r"tour\s+book",
        r"\btour\b",
        r"\bhorrors\b",
    )
)

_COLLECTED_EDITION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bomnibus\b",
        r"\bcompendium\b",
        r"\bdigest\b",
        r"collected\s+edition",
        r"complete\s+collection",
        r"box\s+set",
        r"volume\s+\d",
        r"\bvol\.?\s*\d",
    )
)

_MERCH_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bmerchandise\b",
        r"\bt-?shirt\b",
        r"\bfigure\b",
        r"\bstatue\b",
        r"\bfunko\b",
        r"board\s+game",
        r"\bmug\b",
        r"\btoy\b",
    )
)

_FOIL_SPECIAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfoil\b",
        r"\bvirgin\b",
        r"cardstock",
        r"chromium",
        r"metal\s+variant",
        r"embossed",
        r"holofoil",
    )
)

_REPRINT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfacsimile\b",
        r"\breprint\b",
        r"new\s+printing",
        r"second\s+printing",
        r"third\s+printing",
    )
)

_NON_ISSUE_NUMBERS = frozenset(
    {
        "",
        "tp",
        "tbp",
        "tpb",
        "hc",
        "gn",
        "ogns",
        "one-shot",
        "oneshot",
        "nn",
        "var",
        "bundle",
        "set",
        "book",
        "vol",
        "volume",
        "compendium",
        "omnibus",
        "digest",
    }
)


def _hard_excludes_from_top(quality: ReleaseCatalogQuality) -> bool:
    """Books, collected editions, and non-periodical formats never qualify for top recs."""
    if quality.is_book_or_trade or quality.is_collected_edition:
        return True
    reason = quality.recommendation_exclusion_reason
    if reason in {
        "non_comic_merchandise",
        "prose_or_art_book",
        "paperback_book",
        "trade_paperback",
        "hardcover_book",
        "collected_edition",
        "not_single_issue",
        "over_price_cap_book_or_trade",
    }:
        return True
    return False


def _spec_override_allowed(
    *,
    exclusion: str | None,
    is_single_issue: bool,
    is_book: bool,
    is_collected: bool,
    is_merch: bool,
) -> bool:
    if is_book or is_collected or is_merch:
        return False
    if exclusion == "reprint_non_key" and is_single_issue:
        return True
    return False


@dataclass(frozen=True)
class ReleaseCatalogQuality:
    is_single_issue: bool
    is_collected_edition: bool
    is_book_or_trade: bool
    spec_eligible: bool
    recommendation_exclusion_reason: str | None
    priority_multiplier: float = 1.0
    publisher_boost: float = 0.0
    recommendation_price_cap: float = RECOMMENDATION_PRICE_CAP
    is_over_price_cap: bool = False
    price_exception_reason: str | None = None
    price_discipline_score: float = 1.0


def _blob(*parts: str | None) -> str:
    return " ".join(p.strip() for p in parts if p and str(p).strip()).lower()


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


def _normalize_publisher(value: str | None) -> str:
    return (value or "").strip().lower()


def publisher_boost_for(publisher: str | None) -> float:
    pub = _normalize_publisher(publisher)
    if not pub:
        return 0.0
    if pub in CORE_COMIC_PUBLISHER_TOKENS:
        return 4.0
    for token in CORE_COMIC_PUBLISHER_TOKENS:
        if token in pub or pub in token:
            return 3.0
    return 0.0


def _looks_like_comic_issue_number(issue_number: str | None) -> bool:
    raw = (issue_number or "").strip().lstrip("#").lower()
    if raw in _NON_ISSUE_NUMBERS:
        return False
    if _matches_any(raw, _BOOK_TRADE_PATTERNS):
        return False
    return bool(re.fullmatch(r"\d+[a-z]{0,4}(?:\.\d+)?", raw))


def _is_number_one(issue_number: str | None) -> bool:
    raw = (issue_number or "").strip().lstrip("#").lower()
    return raw in {"1", "1.0"} or raw.startswith("1/")


def _effective_cover_price(cover_price: float | None) -> float | None:
    if cover_price is None:
        return None
    if cover_price <= 0:
        return None
    return float(cover_price)


def _has_foil_or_special_format(*parts: str | None) -> bool:
    blob = _blob(*parts)
    return _matches_any(blob, _FOIL_SPECIAL_PATTERNS)


def _strong_spec_signal(*, spec_type: str | None, v2_total_score: float | None) -> bool:
    if spec_type in {"STRONG_BUY", "BUY"}:
        return True
    return v2_total_score is not None and float(v2_total_score) >= 72.0


def _resolve_price_exception(
    *,
    quality: ReleaseCatalogQuality,
    issue_number: str | None,
    title: str | None,
    key_signals: list[str] | None,
    spec_type: str | None,
    v2_total_score: float | None,
    has_ratio_variant: bool,
    has_incentive_variant: bool,
    user_owns_series_run: bool,
    foc_urgency_high: bool,
) -> str | None:
    signal_set = {s.upper() for s in (key_signals or [])}
    if has_ratio_variant or has_incentive_variant or signal_set.intersection({"RATIO_VARIANT", "INCENTIVE_VARIANT", "VARIANT_HOT"}):
        return "ratio_incentive_variant"
    if _has_foil_or_special_format(title) and _strong_spec_signal(spec_type=spec_type, v2_total_score=v2_total_score):
        return "special_format_spec"
    if _is_number_one(issue_number) and (
        quality.publisher_boost >= 3.0 or signal_set.intersection(NEW_ONE_SIGNALS) or "NEW_NUMBER_ONE" in signal_set
    ):
        return "number_one_franchise"
    if signal_set.intersection(KEY_SIGNAL_TYPES):
        return "major_key_issue"
    if user_owns_series_run and quality.is_single_issue:
        return "active_run_continuation"
    if foc_urgency_high:
        return "foc_preorder_urgency"
    if quality.spec_eligible and _strong_spec_signal(spec_type=spec_type, v2_total_score=v2_total_score):
        return "spec_profile_match"
    return None


def apply_price_discipline(
    quality: ReleaseCatalogQuality,
    *,
    cover_price: float | None,
    issue_number: str | None = None,
    title: str | None = None,
    key_signals: list[str] | None = None,
    spec_type: str | None = None,
    v2_total_score: float | None = None,
    has_ratio_variant: bool = False,
    has_incentive_variant: bool = False,
    user_owns_series_run: bool = False,
    foc_days: int | None = None,
    confidence_score: float | None = None,
) -> ReleaseCatalogQuality:
    """Apply $12 default cap; allow over-cap only with explicit exception reasons."""
    price = _effective_cover_price(cover_price)
    cap = RECOMMENDATION_PRICE_CAP
    if price is None or price <= cap:
        discipline = 1.0 if price is not None and price <= cap else 0.98
        return replace(
            quality,
            recommendation_price_cap=cap,
            is_over_price_cap=False,
            price_exception_reason=None,
            price_discipline_score=discipline,
        )

    if quality.is_book_or_trade or quality.is_collected_edition or quality.recommendation_exclusion_reason in {
        "non_comic_merchandise",
        "prose_or_art_book",
        "paperback_book",
        "trade_paperback",
        "hardcover_book",
        "collected_edition",
    }:
        return replace(
            quality,
            recommendation_price_cap=cap,
            is_over_price_cap=True,
            price_exception_reason=None,
            price_discipline_score=0.0,
            recommendation_exclusion_reason=quality.recommendation_exclusion_reason or "over_price_cap_book_or_trade",
            priority_multiplier=0.0,
            spec_eligible=False,
        )

    foc_urgency_high = foc_days is not None and 0 <= foc_days <= 7 and (
        (confidence_score or 0.0) >= 0.65 or _strong_spec_signal(spec_type=spec_type, v2_total_score=v2_total_score)
    )
    exception = _resolve_price_exception(
        quality=quality,
        issue_number=issue_number,
        title=title,
        key_signals=key_signals,
        spec_type=spec_type,
        v2_total_score=v2_total_score,
        has_ratio_variant=has_ratio_variant,
        has_incentive_variant=has_incentive_variant,
        user_owns_series_run=user_owns_series_run,
        foc_urgency_high=foc_urgency_high,
    )
    if exception is None:
        return replace(
            quality,
            recommendation_price_cap=cap,
            is_over_price_cap=True,
            price_exception_reason=None,
            price_discipline_score=0.0,
            recommendation_exclusion_reason="over_price_cap_no_signal",
            priority_multiplier=0.0,
            spec_eligible=False,
        )

    discipline_by_reason = {
        "ratio_incentive_variant": 0.92,
        "special_format_spec": 0.88,
        "number_one_franchise": 0.9,
        "major_key_issue": 0.87,
        "active_run_continuation": 0.86,
        "foc_preorder_urgency": 0.89,
        "spec_profile_match": 0.85,
    }
    discipline = discipline_by_reason.get(exception, 0.85)
    multiplier = quality.priority_multiplier * 0.92 if quality.priority_multiplier > 0 else 0.85
    return replace(
        quality,
        recommendation_price_cap=cap,
        is_over_price_cap=True,
        price_exception_reason=exception,
        price_discipline_score=discipline,
        priority_multiplier=multiplier,
        spec_eligible=True,
    )


def build_forward_release_title_index(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[str, tuple[ReleaseIssue, ReleaseSeries]]:
    from app.services.unified_collector_intelligence import _display_title

    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] = {}
    for issue, series in rows:
        key = _display_title(series_name=series.series_name, issue_number=issue.issue_number).strip().lower()
        index[key] = (issue, series)
    return index


def _hot_key_override(key_signals: list[str] | None, *, spec_type: str | None = None) -> bool:
    if spec_type in {"STRONG_BUY", "BUY"}:
        return True
    if not key_signals:
        return False
    signal_set = {s.upper() for s in key_signals}
    return bool(signal_set.intersection(KEY_SIGNAL_TYPES) or signal_set.intersection(NEW_ONE_SIGNALS))


def classify_catalog_text(
    *,
    series_name: str | None,
    issue_number: str | None = None,
    title: str | None = None,
    publisher: str | None = None,
    key_signals: list[str] | None = None,
    spec_type: str | None = None,
) -> ReleaseCatalogQuality:
    """Heuristic classification from display/catalog text (cross-system titles)."""
    blob = _blob(series_name, title, issue_number)
    is_book = _matches_any(blob, _BOOK_TRADE_PATTERNS)
    is_collected = _matches_any(blob, _COLLECTED_EDITION_PATTERNS)
    is_merch = _matches_any(blob, _MERCH_PATTERNS)
    is_reprint = _matches_any(blob, _REPRINT_PATTERNS)
    hot = _hot_key_override(key_signals, spec_type=spec_type)

    is_single = _looks_like_comic_issue_number(issue_number) and not is_book and not is_collected and not is_merch
    if is_single and not is_reprint and not _matches_any(blob, _COLLECTED_EDITION_PATTERNS):
        return ReleaseCatalogQuality(
            is_single_issue=True,
            is_collected_edition=False,
            is_book_or_trade=False,
            spec_eligible=True,
            recommendation_exclusion_reason=None,
            priority_multiplier=1.0,
            publisher_boost=publisher_boost_for(publisher),
        )

    exclusion: str | None = None
    multiplier = 1.0
    if is_merch:
        exclusion = "non_comic_merchandise"
        multiplier = 0.0
    elif is_book:
        exclusion = "paperback_book" if "paperback" in blob or " pb" in blob else "trade_paperback"
        if "hardcover" in blob or re.search(r"\bhc\b", blob):
            exclusion = "hardcover_book"
        if "prose" in blob or "novel" in blob or "pictorial history" in blob or "history of" in blob:
            exclusion = "prose_or_art_book"
        if "sticker" in blob:
            exclusion = "sticker_book"
        if "tour" in blob or "horrors" in blob:
            exclusion = "tour_book"
        multiplier = 0.0
    elif is_collected:
        exclusion = "collected_edition"
        multiplier = 0.0
    elif is_reprint:
        exclusion = "reprint_non_key"
        multiplier = 0.12 if not hot else 0.85
    elif not _looks_like_comic_issue_number(issue_number):
        exclusion = "not_single_issue"
        multiplier = 0.0

    spec_eligible = _spec_override_allowed(
        exclusion=exclusion,
        is_single_issue=is_single,
        is_book=is_book,
        is_collected=is_collected,
        is_merch=is_merch,
    ) and hot
    if exclusion and not spec_eligible:
        multiplier = 0.0

    return ReleaseCatalogQuality(
        is_single_issue=is_single,
        is_collected_edition=is_collected,
        is_book_or_trade=is_book or is_collected,
        spec_eligible=spec_eligible,
        recommendation_exclusion_reason=exclusion,
        priority_multiplier=multiplier,
        publisher_boost=publisher_boost_for(publisher),
    )


def classify_forward_release(
    issue: ReleaseIssue,
    series: ReleaseSeries,
    *,
    key_signals: list[str] | None = None,
    spec_type: str | None = None,
    v2_total_score: float | None = None,
    has_ratio_variant: bool = False,
    has_incentive_variant: bool = False,
    user_owns_series_run: bool = False,
    confidence_score: float | None = None,
    today: date | None = None,
) -> ReleaseCatalogQuality:
    quality = classify_catalog_text(
        series_name=series.series_name,
        issue_number=issue.issue_number,
        title=issue.title,
        publisher=series.publisher,
        key_signals=key_signals,
        spec_type=spec_type,
    )
    foc_days = days_until_foc(issue.foc_date, today=today) if issue.foc_date is not None else None
    return apply_price_discipline(
        quality,
        cover_price=issue.cover_price,
        issue_number=issue.issue_number,
        title=issue.title,
        key_signals=key_signals,
        spec_type=spec_type,
        v2_total_score=v2_total_score,
        has_ratio_variant=has_ratio_variant,
        has_incentive_variant=has_incentive_variant,
        user_owns_series_run=user_owns_series_run,
        foc_days=foc_days,
        confidence_score=confidence_score,
    )


def parse_recommendation_display_title(title: str) -> tuple[str, str | None]:
    raw = (title or "").strip()
    if " #" in raw:
        series, issue = raw.split(" #", 1)
        return series.strip(), issue.strip() or None
    if "#" in raw:
        series, issue = raw.split("#", 1)
        return series.strip(), issue.strip() or None
    return raw, None


def quality_for_recommendation_title(
    title: str,
    *,
    session: Session | None = None,
    owner_user_id: int | None = None,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] | None = None,
    key_signals: list[str] | None = None,
    spec_type: str | None = None,
    confidence_score: float | None = None,
    today: date | None = None,
) -> ReleaseCatalogQuality:
    """Resolve catalog quality for a unified/cross-system/daily action title."""
    title_key = title.strip().lower()
    if title_key.endswith(" (variants)"):
        title_key = title_key[: -len(" (variants)")]
    index = release_index
    if index is None and session is not None and owner_user_id is not None:
        index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    series_name, issue_number = parse_recommendation_display_title(title)
    display_quality = apply_price_discipline(
        classify_catalog_text(
            series_name=series_name,
            issue_number=issue_number,
            title=title,
            key_signals=key_signals,
            spec_type=spec_type,
        ),
        cover_price=None,
        issue_number=issue_number,
        title=title,
        key_signals=key_signals,
        spec_type=spec_type,
    )
    pair = index.get(title_key) if index else None
    if pair is not None:
        issue, series = pair
        issue_id = int(issue.id or 0)
        signals = key_signals
        if signals is None and session is not None and issue_id:
            from app.services.recommendation_forward_window import _key_signals_by_issue

            signals = _key_signals_by_issue(session, issue_ids=[issue_id]).get(issue_id, [])
        release_quality = classify_forward_release(
            issue,
            series,
            key_signals=signals,
            spec_type=spec_type,
            confidence_score=confidence_score,
            today=today,
        )
        if _hard_excludes_from_top(display_quality) or not should_include_in_top_recommendations(display_quality):
            return display_quality
        if _hard_excludes_from_top(release_quality) or not should_include_in_top_recommendations(release_quality):
            return release_quality
        return release_quality
    return display_quality


def title_passes_top_recommendation_quality(
    title: str,
    *,
    session: Session | None = None,
    owner_user_id: int | None = None,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] | None = None,
) -> bool:
    quality = quality_for_recommendation_title(
        title,
        session=session,
        owner_user_id=owner_user_id,
        release_index=release_index,
    )
    return should_include_in_top_recommendations(quality)


def should_include_in_top_recommendations(quality: ReleaseCatalogQuality) -> bool:
    if _hard_excludes_from_top(quality):
        return False
    if quality.price_discipline_score <= 0.0:
        return False
    if quality.is_over_price_cap and not quality.price_exception_reason:
        return False
    if quality.recommendation_exclusion_reason and not quality.spec_eligible:
        return False
    return quality.priority_multiplier > 0.0


def apply_quality_to_priority(base_priority: float, quality: ReleaseCatalogQuality) -> float:
    adjusted = base_priority * quality.priority_multiplier * quality.price_discipline_score + quality.publisher_boost
    if quality.is_single_issue and quality.spec_eligible and not quality.is_over_price_cap:
        adjusted += 2.0
    elif quality.is_single_issue and quality.is_over_price_cap and quality.price_exception_reason:
        adjusted += 0.75
    return round(max(0.0, min(100.0, adjusted)), 1)
