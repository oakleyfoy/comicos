"""Resolve blank publisher fields using catalog, registry, inventory, aliases, and heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import CanonicalSeries, ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.inventory_canonical_spine import apply_inventory_spine_joins, publisher_expr, title_expr
from app.services.lunar_issue_identity import normalize_lunar_issue_number
from app.services.metadata_aliases import (
    STATIC_PUBLISHER_ALIAS_MAP,
    get_active_db_alias_value,
    normalize_alias_lookup_key,
)

MetadataAutofillSource = Literal[
    "metadata_catalog",
    "metadata_registry",
    "metadata_prior_issue",
    "metadata_ai",
]

PUBLISHER_AUTOFILL_CONFIDENCE_THRESHOLD = 0.84

_SOURCE_CONFIDENCE: dict[MetadataAutofillSource, float] = {
    "metadata_catalog": 0.96,
    "metadata_registry": 0.92,
    "metadata_prior_issue": 0.88,
    "metadata_ai": 0.80,
}

_ALIAS_CONFIDENCE = 0.86


def _normalize_spaces(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass(frozen=True)
class PublisherAutofillCandidate:
    publisher: str
    confidence: float
    source: MetadataAutofillSource
    detail: str


def _series_key(value: str | None) -> str:
    return _normalize_spaces(value).lower()


def _issue_key(value: str | None) -> str:
    if not value:
        return ""
    return normalize_lunar_issue_number(_normalize_spaces(value)).lower()


def _lookup_release_catalog(
    session: Session,
    *,
    owner_user_id: int | None,
    canonical_series: str,
    canonical_issue: str | None,
) -> PublisherAutofillCandidate | None:
    series_key = _series_key(canonical_series)
    if not series_key:
        return None

    stmt = (
        select(ReleaseSeries, ReleaseIssue)
        .join(ReleaseIssue, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(func.lower(ReleaseSeries.series_name) == series_key)
    )
    if owner_user_id is not None:
        stmt = stmt.where(ReleaseIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt).all()
    if not rows:
        return None

    issue_key = _issue_key(canonical_issue)
    if issue_key:
        filtered = [
            (series, issue)
            for series, issue in rows
            if _issue_key(issue.issue_number) == issue_key
        ]
        if filtered:
            rows = filtered

    publisher_counts: dict[str, int] = {}
    for series, _ in rows:
        pub = _normalize_spaces(series.publisher)
        if pub:
            publisher_counts[pub] = publisher_counts.get(pub, 0) + 1
    if not publisher_counts:
        return None
    publisher = max(publisher_counts.items(), key=lambda item: item[1])[0]
    count = publisher_counts[publisher]
    confidence = _SOURCE_CONFIDENCE["metadata_catalog"]
    if issue_key == "" or len(publisher_counts) > 1:
        confidence = min(confidence, 0.90)
    return PublisherAutofillCandidate(
        publisher=publisher,
        confidence=confidence,
        source="metadata_catalog",
        detail=f"release_catalog matches={count}",
    )


def _lookup_series_registry(
    session: Session,
    *,
    canonical_series: str,
) -> PublisherAutofillCandidate | None:
    series_key = _series_key(canonical_series)
    if not series_key:
        return None
    rows = session.exec(
        select(CanonicalSeries.canonical_publisher, func.count())
        .where(func.lower(CanonicalSeries.canonical_title) == series_key)
        .where(CanonicalSeries.is_active.is_(True))
        .group_by(CanonicalSeries.canonical_publisher)
        .order_by(func.count().desc())
    ).all()
    if not rows:
        return None
    publisher, count = rows[0]
    pub = _normalize_spaces(str(publisher))
    if not pub:
        return None
    confidence = _SOURCE_CONFIDENCE["metadata_registry"]
    if len(rows) > 1:
        confidence = min(confidence, 0.89)
    return PublisherAutofillCandidate(
        publisher=pub,
        confidence=confidence,
        source="metadata_registry",
        detail=f"canonical_series matches={int(count)}",
    )


def _lookup_prior_inventory_issues(
    session: Session,
    *,
    owner_user_id: int | None,
    canonical_series: str,
) -> PublisherAutofillCandidate | None:
    series_key = _series_key(canonical_series)
    if not series_key:
        return None

    stmt = (
        select(Publisher.name, func.count())
        .join(ComicTitle, ComicTitle.publisher_id == Publisher.id)
        .join(ComicIssue, ComicIssue.comic_title_id == ComicTitle.id)
        .where(func.lower(ComicTitle.name) == series_key)
    )
    if owner_user_id is not None:
        stmt = apply_inventory_spine_joins(
            select(publisher_expr(), func.count()).select_from(InventoryCopy)
        ).where(
            func.lower(title_expr()) == series_key,
            InventoryCopy.user_id == owner_user_id,
        )
        rows = session.exec(stmt.group_by(publisher_expr()).order_by(func.count().desc())).all()
    else:
        from sqlalchemy import func

        from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries

        rows = session.exec(
            select(CatalogPublisher.name, func.count())
            .select_from(CatalogIssue)
            .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
            .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
            .where(func.lower(CatalogSeries.name) == series_key)
            .group_by(CatalogPublisher.name)
            .order_by(func.count().desc())
        ).all()
    if not rows:
        return None
    publisher, count = rows[0]
    pub = _normalize_spaces(str(publisher))
    if not pub:
        return None
    return PublisherAutofillCandidate(
        publisher=pub,
        confidence=_SOURCE_CONFIDENCE["metadata_prior_issue"],
        source="metadata_prior_issue",
        detail=f"inventory_series matches={int(count)}",
    )


def _tokenize_haystack(*parts: str | None) -> list[str]:
    haystack = " ".join(_normalize_spaces(part) for part in parts if part)
    if not haystack:
        return []
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'&.\-]*", haystack)


def _publisher_marker_context(raw_text: str, canonical_series: str | None) -> str:
    """Limit publisher marker scans to text near this line item (P90-09E)."""
    if not raw_text.strip():
        return ""
    series_key = _series_key(canonical_series)
    if not series_key:
        return ""
    lower = raw_text.lower()
    idx = lower.find(series_key)
    if idx < 0:
        parts = series_key.split()
        if parts:
            idx = lower.find(parts[0])
    if idx < 0:
        return ""
    start = max(0, idx - 160)
    end = min(len(raw_text), idx + max(len(series_key), 20) + 160)
    return raw_text[start:end]


def _lookup_publisher_aliases(
    session: Session,
    *,
    canonical_series: str | None,
    raw_text: str,
) -> PublisherAutofillCandidate | None:
    from app.services.metadata_enrichment import SOURCE_LINE_PUBLISHER_MARKERS

    # Only scan the series title for alias tokens — not the full order raw_text, which can
    # mention unrelated publishers and poison every line item (P90-09D).
    tokens = _tokenize_haystack(canonical_series)
    for token in tokens:
        alias_key = normalize_alias_lookup_key(token)
        if alias_key in STATIC_PUBLISHER_ALIAS_MAP:
            return PublisherAutofillCandidate(
                publisher=STATIC_PUBLISHER_ALIAS_MAP[alias_key],
                confidence=_ALIAS_CONFIDENCE,
                source="metadata_registry",
                detail=f"publisher_alias_map token={token}",
            )
        db_alias = get_active_db_alias_value(
            session,
            alias_type="publisher",
            alias_value=token,
        )
        if db_alias:
            return PublisherAutofillCandidate(
                publisher=db_alias,
                confidence=_ALIAS_CONFIDENCE,
                source="metadata_registry",
                detail=f"publisher_db_alias token={token}",
            )
    for publisher, pattern in SOURCE_LINE_PUBLISHER_MARKERS.items():
        context = _publisher_marker_context(raw_text, canonical_series)
        if context and pattern.search(context):
            return PublisherAutofillCandidate(
                publisher=publisher,
                confidence=_ALIAS_CONFIDENCE,
                source="metadata_registry",
                detail=f"publisher_marker {publisher}",
            )
    return None


def _lookup_ai_metadata(
    *,
    canonical_series: str | None,
    raw_text: str,
) -> PublisherAutofillCandidate | None:
    from app.services.metadata_enrichment import (
        _infer_publisher_from_source_text,
        _infer_publisher_from_title,
    )

    inferred = _infer_publisher_from_source_text(canonical_series, raw_text)
    if inferred is None:
        inferred = _infer_publisher_from_title(canonical_series)
    if inferred is None:
        return None
    return PublisherAutofillCandidate(
        publisher=inferred,
        confidence=_ALIAS_CONFIDENCE,
        source="metadata_ai",
        detail="metadata_heuristic_inference",
    )


def resolve_blank_publisher(
    session: Session,
    *,
    owner_user_id: int | None,
    canonical_series: str | None,
    canonical_issue: str | None,
    raw_text: str,
) -> PublisherAutofillCandidate | None:
    """Try sources in priority order; return the first candidate meeting confidence threshold."""
    if not _series_key(canonical_series):
        return None

    series = canonical_series or ""
    steps: list[PublisherAutofillCandidate | None] = [
        _lookup_release_catalog(
            session,
            owner_user_id=owner_user_id,
            canonical_series=series,
            canonical_issue=canonical_issue,
        ),
        _lookup_series_registry(session, canonical_series=series),
        _lookup_prior_inventory_issues(
            session,
            owner_user_id=owner_user_id,
            canonical_series=series,
        ),
        _lookup_publisher_aliases(session, canonical_series=series, raw_text=raw_text),
        _lookup_ai_metadata(canonical_series=series, raw_text=raw_text),
    ]
    for candidate in steps:
        if candidate is None:
            continue
        if candidate.confidence >= PUBLISHER_AUTOFILL_CONFIDENCE_THRESHOLD:
            return candidate
    return None
