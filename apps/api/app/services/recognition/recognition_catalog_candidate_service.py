"""P95-06 catalog candidate search + nearby-issue helpers for the recognition review modal.

These power the "Choose Different Issue" gallery and the "Search Catalog" grid. They are a
read-only catalog lookup (CatalogIssue / CatalogSeries / CatalogPublisher / CatalogImage) and
do not touch the recognition fingerprint/OCR pipeline.
"""

from __future__ import annotations

import re

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.recognition.recognition_models import RecognitionCatalogCandidateRead

DEFAULT_CANDIDATE_LIMIT = 24
NEARBY_WINDOW = 5

_NUMERIC_ISSUE = re.compile(r"^\d+$")


def _looks_like_issue_token(token: str) -> bool:
    return bool(_NUMERIC_ISSUE.match(token)) and len(token) <= 4 and not _looks_like_year(token)


def _looks_like_year(token: str) -> bool:
    return bool(re.fullmatch(r"(19|20)\d{2}", token))


def _issue_numeric_value(issue_number: str | None) -> int | None:
    if not issue_number:
        return None
    match = re.match(r"\d+", str(issue_number).strip().lstrip("#"))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _cover_url_for_issue(session: Session, catalog_issue_id: int) -> str | None:
    image = session.exec(
        select(CatalogImage)
        .where(CatalogImage.issue_id == catalog_issue_id, CatalogImage.image_type == "cover")
        .order_by(CatalogImage.id)
    ).first()
    if image is None:
        return None
    if image.source_url and str(image.source_url).strip():
        return str(image.source_url).strip()
    if image.local_path and str(image.local_path).strip():
        return str(image.local_path).strip()
    return None


def _to_card(
    session: Session,
    *,
    issue: CatalogIssue,
    series: CatalogSeries | None,
    publisher: CatalogPublisher | None,
    confidence: float,
    source: str,
) -> RecognitionCatalogCandidateRead:
    return RecognitionCatalogCandidateRead(
        catalog_issue_id=int(issue.id or 0),
        series=series.name if series is not None else "Unknown",
        issue_number=str(issue.issue_number),
        variant=None,
        publisher=publisher.name if publisher is not None else None,
        cover_image_url=_cover_url_for_issue(session, int(issue.id or 0)),
        release_date=issue.release_date or issue.cover_date,
        confidence=round(float(confidence), 4),
        source=source,
    )


def _resolve_publisher(session: Session, issue: CatalogIssue, series: CatalogSeries | None) -> CatalogPublisher | None:
    if issue.publisher_id is not None:
        return session.get(CatalogPublisher, issue.publisher_id)
    if series is not None and series.publisher_id is not None:
        return session.get(CatalogPublisher, series.publisher_id)
    return None


def nearby_issues(
    session: Session,
    *,
    catalog_issue_id: int,
    window: int = NEARBY_WINDOW,
) -> list[RecognitionCatalogCandidateRead]:
    """Same-series issues around the given one: current + previous N + next N numeric issues."""
    base = session.get(CatalogIssue, catalog_issue_id)
    if base is None:
        return []
    series = session.get(CatalogSeries, base.series_id)
    publisher = _resolve_publisher(session, base, series)
    base_value = _issue_numeric_value(base.issue_number)

    series_issues = session.exec(
        select(CatalogIssue).where(CatalogIssue.series_id == base.series_id)
    ).all()

    scored: list[tuple[int, CatalogIssue]] = []
    for issue in series_issues:
        value = _issue_numeric_value(issue.issue_number)
        if value is None:
            continue
        if base_value is not None and abs(value - base_value) > window:
            continue
        scored.append((value, issue))
    scored.sort(key=lambda row: (row[0], int(row[1].id or 0)))

    cards: list[RecognitionCatalogCandidateRead] = []
    for value, issue in scored:
        confidence = 1.0 if int(issue.id or 0) == catalog_issue_id else 0.0
        cards.append(
            _to_card(
                session,
                issue=issue,
                series=series,
                publisher=publisher,
                confidence=confidence,
                source="catalog_nearby",
            )
        )
    return cards


def search_catalog_candidates(
    session: Session,
    *,
    q: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
    catalog_issue_id: int | None = None,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> list[RecognitionCatalogCandidateRead]:
    limit = max(1, min(int(limit), 100))

    has_text_query = any(bool((value or "").strip()) for value in (q, series, issue_number, publisher))
    # No text query but an anchor issue id -> nearby same-series gallery.
    if not has_text_query and catalog_issue_id is not None:
        return nearby_issues(session, catalog_issue_id=catalog_issue_id)[:limit]

    alpha_tokens: list[str] = []
    issue_token: str | None = issue_number.strip() if (issue_number or "").strip() else None
    if (q or "").strip():
        for raw in q.split():
            token = raw.strip()
            if not token:
                continue
            if issue_token is None and _looks_like_issue_token(token):
                issue_token = token
                continue
            alpha_tokens.append(token)
    if (series or "").strip():
        alpha_tokens.extend(series.split())

    statement = (
        select(CatalogIssue, CatalogSeries, CatalogPublisher)
        .join(CatalogSeries, CatalogSeries.id == CatalogIssue.series_id)
        .join(
            CatalogPublisher,
            CatalogPublisher.id == CatalogSeries.publisher_id,
            isouter=True,
        )
    )

    for token in alpha_tokens:
        like = f"%{token.lower()}%"
        statement = statement.where(
            func.lower(CatalogSeries.name).like(like) | func.lower(func.coalesce(CatalogPublisher.name, "")).like(like)
        )
    if (publisher or "").strip():
        statement = statement.where(func.lower(func.coalesce(CatalogPublisher.name, "")).like(f"%{publisher.strip().lower()}%"))
    if issue_token is not None:
        statement = statement.where(CatalogIssue.normalized_issue_number == normalize_issue_number(issue_token))

    # Over-fetch then rank deterministically (numeric issue order) for stable galleries.
    rows = session.exec(statement.limit(limit * 4)).all()

    def _sort_key(row: tuple[CatalogIssue, CatalogSeries, CatalogPublisher | None]):
        issue, series_row, _publisher = row
        numeric = _issue_numeric_value(issue.issue_number)
        return (series_row.name.lower(), numeric if numeric is not None else 10**9, str(issue.issue_number))

    rows = sorted(rows, key=_sort_key)[:limit]

    cards: list[RecognitionCatalogCandidateRead] = []
    for issue, series_row, publisher_row in rows:
        if issue.id is None:
            continue
        # Exact normalized-issue + series text match scores higher than a broad text hit.
        confidence = 0.9 if issue_token and issue.normalized_issue_number == normalize_issue_number(issue_token) else 0.6
        cards.append(
            _to_card(
                session,
                issue=issue,
                series=series_row,
                publisher=publisher_row,
                confidence=confidence,
                source="catalog_search",
            )
        )
    return cards
