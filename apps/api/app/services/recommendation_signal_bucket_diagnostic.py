"""Per-signal bucket diagnostics (A missing source, B match failed, C strict scoring)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.creator_intelligence import CreatorProfile
from app.models.pull_list import PullList
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.services.popularity_engine import creator_score
from app.services.recommendation_intelligence_enrichment import (
    _ANNIVERSARY_PATTERNS,
    _HOMAGE_PATTERNS,
    _LEGACY_NUMBERING_PATTERNS,
    _homage_signals,
    _milestone_signals,
    _text_blob,
    build_collector_significance_with_breakdown,
    parse_issue_number_milestone,
)
from app.services.recommendation_priority_enrichment import (
    build_owned_series_inventory_stats,
    build_recommendation_priority_enrichment,
)
from app.services.recommendation_catalog_quality import classify_catalog_text
from app.services.recommendation_title_index import resolve_release_pair
from app.services.recommendation_title_normalize import (
    display_title_key,
    normalize_recommendation_title_key,
    parse_normalized_display_title,
)

PRODUCT_FORMAT_SINGLE_ISSUE = "single_issue"
PRODUCT_FORMAT_VARIANT = "variant"
PRODUCT_FORMAT_TRADE_PAPERBACK = "trade_paperback"
PRODUCT_FORMAT_HARDCOVER = "hardcover"
PRODUCT_FORMAT_MAGAZINE = "magazine"
PRODUCT_FORMAT_MERCHANDISE = "merchandise"
PRODUCT_FORMAT_UNKNOWN = "unknown"

_USABLE_DEFAULT_FORMATS = frozenset({PRODUCT_FORMAT_SINGLE_ISSUE, PRODUCT_FORMAT_VARIANT})
_USABLE_WITH_BOOKS = _USABLE_DEFAULT_FORMATS | frozenset(
    {PRODUCT_FORMAT_TRADE_PAPERBACK, PRODUCT_FORMAT_HARDCOVER}
)

_NO_USABLE_CATALOG_FIX = (
    "Release feed does not currently contain a usable single-issue match for this title."
)

BUCKET_OK = "OK"
BUCKET_A = "A_SOURCE_DATA_MISSING"
BUCKET_B = "B_MATCH_FAILED"
BUCKET_C = "C_SCORING_RULE_TOO_STRICT"

_CREATOR_POP_THRESHOLD = 68.0


def _closest_index_keys(title_query: str, index: dict[str, tuple[ReleaseIssue, ReleaseSeries]], *, limit: int = 15) -> list[str]:
    needle = normalize_recommendation_title_key(title_query)
    if not needle:
        return []
    tokens = [t for t in re.split(r"\s+", needle) if len(t) >= 3]
    scored: list[tuple[int, str]] = []
    for key in index:
        score = sum(1 for t in tokens if t in key)
        if needle in key or key in needle:
            score += 5
        if score > 0:
            scored.append((score, key))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [k for _, k in scored[:limit]]


def classify_catalog_product_format(
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> str:
    quality = classify_catalog_text(
        series_name=series.series_name,
        issue_number=issue.issue_number,
        title=issue.title,
        publisher=series.publisher,
    )
    blob = f"{series.series_name} {issue.title} {issue.issue_number}".lower()
    if quality.is_single_issue:
        if "(variants)" in (issue.title or "").lower():
            return PRODUCT_FORMAT_VARIANT
        return PRODUCT_FORMAT_SINGLE_ISSUE
    reason = (quality.recommendation_exclusion_reason or "").lower()
    if reason == "non_comic_merchandise":
        return PRODUCT_FORMAT_MERCHANDISE
    if reason in {"hardcover_book"} or re.search(r"\bhc\b", blob):
        return PRODUCT_FORMAT_HARDCOVER
    if reason in {"trade_paperback", "paperback_book", "prose_or_art_book", "sticker_book", "tour_book"}:
        return PRODUCT_FORMAT_TRADE_PAPERBACK
    if "magazine" in blob:
        return PRODUCT_FORMAT_MAGAZINE
    if re.search(r"\btp\b|\btpb\b|trade\s+paperback", blob):
        return PRODUCT_FORMAT_TRADE_PAPERBACK
    return PRODUCT_FORMAT_UNKNOWN


def _format_usable(product_format: str, *, include_books: bool) -> bool:
    allowed = _USABLE_WITH_BOOKS if include_books else _USABLE_DEFAULT_FORMATS
    return product_format in allowed


def _catalog_candidate_row(
    issue: ReleaseIssue,
    series: ReleaseSeries,
    *,
    include_books: bool,
) -> dict[str, Any]:
    fmt = classify_catalog_product_format(issue, series)
    usable = _format_usable(fmt, include_books=include_books)
    return {
        "display_title": display_title_key(series_name=series.series_name, issue_number=issue.issue_number),
        "series_name": series.series_name,
        "issue_number": issue.issue_number,
        "issue_title": issue.title,
        "product_format": fmt,
        "usable_for_spec_diagnostic": usable,
        "excluded_by_format_filter": not usable,
    }


def _search_release_catalog(
    session: Session,
    *,
    owner_user_id: int,
    title_query: str,
    strict_title: str | None = None,
    limit: int = 30,
) -> list[tuple[ReleaseIssue, ReleaseSeries]]:
    query = (strict_title or title_query).strip()
    q = query.lower()
    if not q:
        return []
    series_part, issue_part = parse_normalized_display_title(query)
    stmt = (
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    )
    if strict_title and series_part and issue_part:
        stmt = stmt.where(
            func.lower(ReleaseSeries.series_name) == series_part.lower(),
            ReleaseIssue.issue_number == issue_part,
        )
    elif series_part and issue_part:
        stmt = stmt.where(
            func.lower(ReleaseSeries.series_name) == series_part,
            ReleaseIssue.issue_number == issue_part,
        )
    else:
        stmt = stmt.where(
            or_(
                func.lower(ReleaseSeries.series_name).contains(q),
                func.lower(ReleaseIssue.title).contains(q),
            )
        )
    return list(session.exec(stmt.limit(limit)).all())


def _select_catalog_pair(
    catalog_rows: list[tuple[ReleaseIssue, ReleaseSeries]],
    *,
    include_books: bool,
    strict_title: str | None,
    index_pair: tuple[ReleaseIssue, ReleaseSeries] | None,
) -> tuple[
    tuple[ReleaseIssue, ReleaseSeries] | None,
    list[dict[str, Any]],
    str | None,
    str | None,
    bool,
]:
    """Returns (pair, candidates, selected_reason, product_format, excluded_by_format_filter)."""
    candidates = [_catalog_candidate_row(issue, series, include_books=include_books) for issue, series in catalog_rows]
    usable = [
        (issue, series)
        for issue, series in catalog_rows
        if _format_usable(classify_catalog_product_format(issue, series), include_books=include_books)
    ]

    if strict_title:
        series_part, issue_part = parse_normalized_display_title(strict_title)
        strict_usable = []
        for issue, series in usable:
            if series_part and issue_part:
                if (
                    (series.series_name or "").strip().lower() == series_part.lower()
                    and (issue.issue_number or "").strip() == issue_part.strip()
                ):
                    strict_usable.append((issue, series))
            else:
                key = display_title_key(series_name=series.series_name, issue_number=issue.issue_number)
                if normalize_recommendation_title_key(key) == normalize_recommendation_title_key(strict_title):
                    strict_usable.append((issue, series))
        usable = strict_usable

    def _rank(row: tuple[ReleaseIssue, ReleaseSeries]) -> tuple[int, str]:
        fmt = classify_catalog_product_format(row[0], row[1])
        order = {
            PRODUCT_FORMAT_SINGLE_ISSUE: 0,
            PRODUCT_FORMAT_VARIANT: 1,
            PRODUCT_FORMAT_TRADE_PAPERBACK: 9,
            PRODUCT_FORMAT_HARDCOVER: 10,
        }
        return (order.get(fmt, 5), row[1].series_name)

    if index_pair is not None:
        fmt = classify_catalog_product_format(index_pair[0], index_pair[1])
        if _format_usable(fmt, include_books=include_books) and (
            not strict_title or index_pair in usable
        ):
            return index_pair, candidates, "release_index_resolve_pair", fmt, False

    if usable:
        usable.sort(key=_rank)
        issue, series = usable[0]
        fmt = classify_catalog_product_format(issue, series)
        return (issue, series), candidates, "preferred_single_issue_catalog_row", fmt, False

    if index_pair is not None and include_books:
        fmt = classify_catalog_product_format(index_pair[0], index_pair[1])
        return index_pair, candidates, "release_index_include_books", fmt, not _format_usable(fmt, include_books=False)

    excluded = bool(catalog_rows) and not usable
    return None, candidates, "no_usable_single_issue_in_catalog", None, excluded


def _creator_names_in_text(session: Session, blob: str) -> list[dict[str, Any]]:
    lower = blob.lower()
    hits: list[dict[str, Any]] = []
    for profile in session.exec(select(CreatorProfile).where(CreatorProfile.status == "ACTIVE").limit(400)).all():
        name = (profile.creator_name or "").strip()
        if len(name) < 3:
            continue
        if re.search(rf"\b{re.escape(name.lower())}\b", lower):
            cid = int(profile.id or 0)
            pop = creator_score(session, creator_id=cid) if cid > 0 else 0.0
            hits.append(
                {
                    "creator_name": name,
                    "creator_id": cid,
                    "popularity_score": round(pop, 2),
                    "meets_threshold": pop >= _CREATOR_POP_THRESHOLD,
                }
            )
    return hits[:8]


def _homage_labels_in_blob(blob: str) -> list[str]:
    labels: list[str] = []
    for pattern, label in _HOMAGE_PATTERNS:
        if pattern.search(blob):
            labels.append(label)
    return labels


def _classify_creator_bucket(
    *,
    release_matched: bool,
    enrichment_attempted: bool,
    creator_score_value: float,
    names_in_catalog: bool,
    names_in_variants: bool,
    matched_profiles: list[dict[str, Any]],
) -> str:
    if creator_score_value > 0:
        return BUCKET_OK
    if not release_matched:
        return BUCKET_B
    if not enrichment_attempted:
        return BUCKET_B
    if not names_in_catalog and not names_in_variants and not matched_profiles:
        return BUCKET_A
    if matched_profiles and all(not p["meets_threshold"] for p in matched_profiles):
        return BUCKET_C
    if names_in_catalog or names_in_variants:
        return BUCKET_C
    return BUCKET_A


def _classify_milestone_bucket(
    *,
    release_matched: bool,
    enrichment_attempted: bool,
    milestone_score: float,
    parsed_milestone_num: int | None,
    anniversary_wording: bool,
    legacy_wording: bool,
    key_signal_milestone: bool,
) -> str:
    if milestone_score > 0:
        return BUCKET_OK
    if not release_matched or not enrichment_attempted:
        return BUCKET_B
    if key_signal_milestone and parsed_milestone_num is None and not anniversary_wording:
        return BUCKET_C
    if anniversary_wording or legacy_wording:
        return BUCKET_C
    if parsed_milestone_num is not None:
        return BUCKET_C
    return BUCKET_A


def _classify_homage_bucket(
    *,
    release_matched: bool,
    enrichment_attempted: bool,
    homage_score: float,
    homage_in_catalog: bool,
    homage_in_variants: bool,
) -> str:
    if homage_score > 0:
        return BUCKET_OK
    if not release_matched or not enrichment_attempted:
        return BUCKET_B
    if homage_in_catalog or homage_in_variants:
        return BUCKET_C
    return BUCKET_A


def _classify_market_bucket(
    *,
    release_matched: bool,
    enrichment_attempted: bool,
    market_demand_score: float,
    market_profiles_matched: bool,
    owner_continuity: bool,
    pull_list_match: bool,
    fmv_present: bool,
    market_user_available: bool,
) -> str:
    if market_demand_score > 0:
        return BUCKET_OK
    if not release_matched or not enrichment_attempted:
        return BUCKET_B
    if market_user_available and market_profiles_matched:
        return BUCKET_C
    if owner_continuity or pull_list_match or fmv_present:
        return BUCKET_C
    if market_profiles_matched:
        return BUCKET_C
    return BUCKET_A


def _recommended_next_fix(buckets: dict[str, str]) -> str:
    fixes: list[str] = []
    if buckets.get("creator") == BUCKET_B or buckets.get("milestone") == BUCKET_B:
        fixes.append("Fix title index normalization or align recommendation title with catalog display_title key.")
    if buckets.get("creator") == BUCKET_A:
        fixes.append("Enrich release catalog text with creator credits or refresh CreatorProfile registry.")
    if buckets.get("creator") == BUCKET_C:
        fixes.append("Creator present but below popularity threshold (68) or not linked in catalog blob.")
    if buckets.get("milestone") == BUCKET_A:
        fixes.append("Issue is not a numeric milestone (25/50/100/…) and catalog lacks anniversary/legacy wording.")
    if buckets.get("milestone") == BUCKET_C:
        fixes.append("MILESTONE_NUMBERING key signal or anniversary text present but milestone_score path did not award points.")
    if buckets.get("homage") == BUCKET_A:
        fixes.append("Add homage/tribute/retro language to variant names or solicitation description.")
    if buckets.get("market_demand") == BUCKET_A:
        fixes.append("Seed MarketDemandProfile, owner inventory FMV, or run unified scoring with market_user_fit.")
    if buckets.get("market_demand") == BUCKET_C:
        fixes.append("Market/continuity signals exist but historical_demand_score is zero (collector path uses scoring_ctx=None).")
    if not fixes:
        return "Signals scoring as expected; investigate composite priority if rank still seems low."
    return " ".join(fixes[:3])


def diagnose_title_signal_buckets(
    session: Session,
    *,
    owner_user_id: int,
    title_query: str,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
    recommendation_row: dict[str, Any] | None = None,
    rationale: str = "",
    include_books: bool = False,
    strict_catalog_title: str | None = None,
) -> dict[str, Any]:
    normalized_key = normalize_recommendation_title_key(title_query)
    index_pair = resolve_release_pair(title_query, release_index)
    if strict_catalog_title:
        index_pair = resolve_release_pair(strict_catalog_title, release_index) or index_pair
    catalog_rows = _search_release_catalog(
        session,
        owner_user_id=owner_user_id,
        title_query=title_query,
        strict_title=strict_catalog_title,
    )
    pair, candidate_catalog_matches, selected_reason, product_format, excluded_by_format = _select_catalog_pair(
        catalog_rows,
        include_books=include_books,
        strict_title=strict_catalog_title,
        index_pair=index_pair,
    )

    issue, series = pair if pair else (None, None)
    issue_id = int(issue.id) if issue and issue.id else None
    index_fmt = (
        classify_catalog_product_format(index_pair[0], index_pair[1]) if index_pair else None
    )
    release_index_matched = (
        index_pair is not None
        and index_fmt is not None
        and _format_usable(index_fmt, include_books=include_books)
    )
    catalog_matched = pair is not None
    release_matched = (
        pair is not None
        and issue_id is not None
        and product_format is not None
        and _format_usable(product_format, include_books=include_books)
    )

    variants: list[ReleaseVariant] = []
    if issue_id:
        variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)).all())

    key_signals: list[str] = []
    if issue_id:
        key_signals = [
            str(r.signal_type)
            for r in session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == issue_id)).all()
        ]

    rec_rationale = rationale or (recommendation_row or {}).get("rationale", "")
    blob_full = _text_blob(series=series, issue=issue, variants=variants, rationale=rec_rationale)
    blob_issue = _text_blob(series=series, issue=issue, variants=None, rationale="")
    blob_variants_only = " ".join(
        (v.variant_name or "") + " " + (v.variant_type or "") + " " + (v.cover_artist or "")
        for v in variants
    ).lower()

    owned_stats = build_owned_series_inventory_stats(session, owner_user_id=owner_user_id)
    priority_enrichment = None
    market_user_available = False
    if release_matched and issue is not None and series is not None and issue_id:
        priority_enrichment = build_recommendation_priority_enrichment(
            session,
            owner_user_id=owner_user_id,
            series_name=series.series_name,
            issue_title=issue.title,
            publisher=series.publisher,
            key_signals=key_signals,
            v2_confidence=float((recommendation_row or {}).get("confidence_score") or 0.58),
            spec_type=None,
            owns_series_run=False,
            owned_stats=owned_stats,
            scoring_ctx=None,
            issue_id=issue_id,
            issue=issue,
            series=series,
        )

    breakdown = None
    if release_matched and issue is not None and series is not None:
        _, breakdown = build_collector_significance_with_breakdown(
            session,
            series=series,
            issue=issue,
            variants=variants,
            rationale=rec_rationale,
            key_signals=key_signals,
            priority_enrichment=priority_enrichment,
            owned_stats=owned_stats,
            base_score=float((recommendation_row or {}).get("priority_score") or 0.0),
        )

    creator_sc = float(breakdown.creator_score if breakdown else 0.0)
    milestone_sc = float(breakdown.milestone_score if breakdown else 0.0)
    homage_sc = float(breakdown.homage_score if breakdown else 0.0)
    market_sc = float(breakdown.historical_demand_score if breakdown else 0.0)

    creator_matches = _creator_names_in_text(session, blob_full) if release_matched else []
    parsed_ms = parse_issue_number_milestone(issue.issue_number) if issue else None
    ms_num, _ms_bonus, _ = _milestone_signals(issue.issue_number or "", blob_full) if issue else (None, 0.0, [])
    anniversary = any(p.search(blob_full) for p in _ANNIVERSARY_PATTERNS)
    legacy = any(p.search(blob_full) for p in _LEGACY_NUMBERING_PATTERNS)
    homage_labels = _homage_labels_in_blob(blob_full)
    homage_variant_labels = _homage_labels_in_blob(blob_variants_only)

    series_key = (
        (series.publisher or "").strip().lower(),
        (series.series_name or "").strip().lower(),
    ) if series else ("", "")
    owned_count = owned_stats.copies_by_series.get(series_key, 0) if series else 0
    fmv = owned_stats.avg_fmv_by_series.get(series_key) if series else None

    pull_match = False
    if series:
        pl = session.exec(
            select(PullList)
            .where(PullList.owner_user_id == owner_user_id)
            .where(func.lower(PullList.series_name) == series_key[1])
            .limit(1)
        ).first()
        pull_match = pl is not None

    market_profiles: list[dict[str, Any]] = []
    for profile in session.exec(select(MarketDemandProfile)).all():
        name = (getattr(profile, "entity_name", None) or "").strip().lower()
        if name and len(name) >= 3 and name in blob_full:
            market_profiles.append(
                {
                    "entity_name": profile.entity_name,
                    "demand_score": float(profile.demand_score),
                }
            )

    enrichment_attempted = release_matched and issue_id is not None

    creator_bucket = _classify_creator_bucket(
        release_matched=release_matched,
        enrichment_attempted=enrichment_attempted,
        creator_score_value=creator_sc,
        names_in_catalog=bool(_creator_names_in_text(session, blob_issue)),
        names_in_variants=bool(_creator_names_in_text(session, blob_variants_only)),
        matched_profiles=creator_matches,
    )
    milestone_bucket = _classify_milestone_bucket(
        release_matched=release_matched,
        enrichment_attempted=enrichment_attempted,
        milestone_score=milestone_sc,
        parsed_milestone_num=parsed_ms,
        anniversary_wording=anniversary,
        legacy_wording=legacy,
        key_signal_milestone="MILESTONE_NUMBERING" in {s.upper() for s in key_signals},
    )
    homage_bucket = _classify_homage_bucket(
        release_matched=release_matched,
        enrichment_attempted=enrichment_attempted,
        homage_score=homage_sc,
        homage_in_catalog=bool(_homage_labels_in_blob(blob_issue)),
        homage_in_variants=bool(homage_variant_labels),
    )
    market_bucket = _classify_market_bucket(
        release_matched=release_matched,
        enrichment_attempted=enrichment_attempted,
        market_demand_score=market_sc,
        market_profiles_matched=bool(market_profiles),
        owner_continuity=owned_count > 0,
        pull_list_match=pull_match,
        fmv_present=fmv is not None and float(fmv) > 0,
        market_user_available=False,
    )

    buckets = {
        "creator": creator_bucket,
        "milestone": milestone_bucket,
        "homage": homage_bucket,
        "market_demand": market_bucket,
    }

    usable_single_count = sum(
        1 for c in candidate_catalog_matches if c.get("usable_for_spec_diagnostic")
    )
    next_fix = _recommended_next_fix(buckets)
    if excluded_by_format and usable_single_count == 0 and catalog_rows:
        next_fix = _NO_USABLE_CATALOG_FIX

    release_catalog: dict[str, Any] = {
        "catalog_rows_found": len(catalog_rows),
        "usable_single_issue_rows_found": usable_single_count,
        "catalog_matched": catalog_matched,
        "index_matched": release_index_matched,
        "product_format": product_format,
        "excluded_by_format_filter": excluded_by_format,
        "candidate_catalog_matches": candidate_catalog_matches,
        "selected_catalog_match_reason": selected_reason,
        "publisher": series.publisher if series else None,
        "series_name": series.series_name if series else None,
        "issue_number": issue.issue_number if issue else None,
        "issue_title": issue.title if issue else None,
        "foc_date": issue.foc_date.isoformat() if issue and issue.foc_date else None,
        "release_date": issue.release_date.isoformat() if issue and issue.release_date else None,
        "variant_count": len(variants),
        "variants": [
            {
                "variant_name": v.variant_name,
                "variant_type": v.variant_type,
                "cover_artist": v.cover_artist,
                "ratio_value": v.ratio_value,
            }
            for v in variants[:12]
        ],
        "solicitation_text_sample": (issue.title or "")[:500] if issue else None,
    }

    index_key_from_release = None
    if issue and series:
        index_key_from_release = display_title_key(
            series_name=series.series_name,
            issue_number=issue.issue_number,
        )

    return {
        "title_query": title_query,
        "bucket_summary": buckets,
        "release_catalog": release_catalog,
        "recommendation": recommendation_row or {"found": False},
        "title_index": {
            "normalized_title_key": normalized_key,
            "release_index_key": index_key_from_release,
            "resolve_release_pair_matched": release_index_matched,
            "catalog_fallback_available": catalog_matched and not release_index_matched,
            "closest_index_keys": _closest_index_keys(title_query, release_index),
        },
        "creator_diagnostic": {
            "creator_score": creator_sc,
            "creator_names_in_catalog_text": bool(_creator_names_in_text(session, blob_issue)) if release_matched else False,
            "creator_names_in_variant_text": bool(_creator_names_in_text(session, blob_variants_only)) if release_matched else False,
            "matched_creator_profiles": creator_matches,
            "why_zero_bucket": creator_bucket if creator_sc <= 0 else BUCKET_OK,
        },
        "milestone_diagnostic": {
            "milestone_score": milestone_sc,
            "parsed_issue_number": issue.issue_number if issue else None,
            "numeric_milestone_issue": parsed_ms,
            "milestone_signals_parsed_num": ms_num,
            "anniversary_wording": anniversary,
            "legacy_wording": legacy,
            "release_key_signal_milestone": "MILESTONE_NUMBERING" in {s.upper() for s in key_signals},
            "why_zero_bucket": milestone_bucket if milestone_sc <= 0 else BUCKET_OK,
        },
        "homage_diagnostic": {
            "homage_score": homage_sc,
            "homage_wording_in_description": bool(_homage_labels_in_blob(blob_issue)),
            "homage_wording_in_variants": bool(homage_variant_labels),
            "homage_labels_detected": homage_labels + homage_variant_labels,
            "why_zero_bucket": homage_bucket if homage_sc <= 0 else BUCKET_OK,
        },
        "market_demand_diagnostic": {
            "market_demand_score": market_sc,
            "market_demand_profiles_matched": market_profiles,
            "owner_inventory_copies_in_series": owned_count,
            "pull_list_series_match": pull_match,
            "avg_fmv_in_series": fmv,
            "historical_demand_bonus": priority_enrichment.historical_demand_bonus if priority_enrichment else 0.0,
            "continuity_bonus": priority_enrichment.continuity_bonus if priority_enrichment else 0.0,
            "why_zero_bucket": market_bucket if market_sc <= 0 else BUCKET_OK,
        },
        "recommended_next_fix": next_fix,
    }


def aggregate_bucket_counts(reports: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    signals = ("creator", "milestone", "homage", "market_demand")
    out: dict[str, Counter[str]] = {s: Counter() for s in signals}
    for report in reports:
        summary = report.get("bucket_summary") or {}
        for signal in signals:
            out[signal][str(summary.get(signal, BUCKET_A))] += 1
    return {signal: dict(counter) for signal, counter in out.items()}
