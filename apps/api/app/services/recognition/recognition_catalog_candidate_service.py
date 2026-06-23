"""P95-06 catalog candidate search + nearby-issue helpers for the recognition review modal.

These power the "Choose Different Issue" gallery and the "Search Catalog" grid. They are a
read-only catalog lookup (CatalogIssue / CatalogSeries / CatalogPublisher / CatalogImage) and
do not touch the recognition fingerprint/OCR pipeline.
"""

from __future__ import annotations

import re

from sqlalchemy import and_, or_
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.import_catalog_resolution_service import normalize_import_title
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
        issue_title=(issue.title.strip() if isinstance(issue.title, str) and issue.title.strip() else None),
        series_start_year=series.start_year if series is not None else None,
        volume_number=series.volume_number if series is not None else None,
        variant=None,
        publisher=publisher.name if publisher is not None else None,
        cover_image_url=_cover_url_for_issue(session, int(issue.id or 0)),
        cover_date=issue.cover_date,
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


def _catalog_token_search_clause(token: str):
    """Match a single query token against series, publisher, and issue title fields."""
    like = f"%{token.lower()}%"
    return or_(
        func.lower(CatalogSeries.name).like(like),
        func.lower(CatalogSeries.normalized_name).like(like),
        func.lower(func.coalesce(CatalogPublisher.name, "")).like(like),
        func.lower(func.coalesce(CatalogPublisher.normalized_name, "")).like(like),
        func.lower(func.coalesce(CatalogIssue.title, "")).like(like),
    )


def _catalog_phrase_search_clause(phrase: str):
    """Match the full query phrase against normalized/canonical series names."""
    normalized = normalize_series_name(phrase)
    if not normalized:
        return None
    like = f"%{normalized}%"
    return or_(
        func.lower(CatalogSeries.normalized_name).like(like),
        func.lower(CatalogSeries.name).like(like),
        func.lower(CatalogSeries.normalized_name).like(f"%{normalize_import_title(phrase).lower()}%"),
    )


def _issue_title_match_score(issue: CatalogIssue, issue_title: str | None) -> float:
    if not (issue_title or "").strip() or not (issue.title or "").strip():
        return 0.0
    want = normalize_import_title(issue_title)
    have = normalize_import_title(str(issue.title))
    if not want or not have:
        return 0.0
    if want == have:
        return 900.0
    if want in have or have in want:
        return 450.0
    return 0.0


def _issue_cover_year(issue: CatalogIssue) -> int | None:
    if issue.cover_date is not None:
        return int(issue.cover_date.year)
    if issue.release_date is not None:
        return int(issue.release_date.year)
    return None


def _search_match_score(
    *,
    issue: CatalogIssue,
    series_row: CatalogSeries,
    publisher_row: CatalogPublisher | None,
    issue_token: str | None,
    alpha_tokens: list[str],
    publisher_filter: str | None,
    year_value: int | None = None,
    issue_title: str | None = None,
) -> float:
    """Higher score = better match. Exact series + issue number rank first."""
    score = 0.0
    if issue_token and issue.normalized_issue_number == normalize_issue_number(issue_token):
        score += 1000.0

    series_name = (series_row.name or "").lower()
    norm_series = (series_row.normalized_name or normalize_import_title(series_row.name)).lower()
    if alpha_tokens:
        joined = " ".join(token.lower() for token in alpha_tokens)
        joined_norm = normalize_import_title(joined)
        if joined_norm == norm_series or joined.lower() == series_name:
            score += 500.0
        elif all(token.lower() in series_name for token in alpha_tokens):
            score += 320.0
        else:
            score += 80.0
        if alpha_tokens and series_name.startswith(alpha_tokens[0].lower()):
            score += 40.0
        # Prefer the core series name "Venom" over "Venom: Lethal Protector" when the query is just "Venom".
        if len(alpha_tokens) == 1 and series_name == alpha_tokens[0].lower():
            score += 60.0

    if (publisher_filter or "").strip() and publisher_row:
        if publisher_filter.strip().lower() in (publisher_row.name or "").lower():
            score += 100.0

    score += _issue_title_match_score(issue, issue_title)

    year_tokens = [t for t in alpha_tokens if _looks_like_year(t)]
    if year_tokens and series_row.start_year is not None:
        for token in year_tokens:
            if int(token) == int(series_row.start_year):
                score += 200.0

    # Explicit GPT year disambiguates same-named series from different eras.
    if year_value is not None and series_row.start_year is not None:
        gap = abs(int(year_value) - int(series_row.start_year))
        if gap == 0:
            score += 400.0
        elif gap <= 1:
            score += 200.0
        elif gap >= 5:
            # Penalize a wrong-era series (e.g. 1983 "The Falcon" for a 2017 book).
            score -= 250.0 + min(gap, 50) * 5.0
    elif year_value is not None and series_row.start_year is None:
        cover_year = _issue_cover_year(issue)
        if cover_year is not None:
            gap = abs(int(year_value) - cover_year)
            if gap == 0:
                score += 350.0
            elif gap <= 1:
                score += 175.0
            elif gap >= 5:
                score -= 250.0 + min(gap, 50) * 5.0
        else:
            score -= 120.0

    if year_value is not None:
        cover_year = _issue_cover_year(issue)
        if cover_year is not None:
            gap = abs(int(year_value) - cover_year)
            if gap == 0:
                score += 300.0
            elif gap <= 1:
                score += 120.0
            elif gap >= 5:
                score -= 200.0 + min(gap, 40) * 4.0

    return score


def _catalog_year_distance(
    *,
    issue: CatalogIssue,
    series_row: CatalogSeries,
    year_value: int | None,
) -> int:
    """Sort key: prefer candidates closest to the GPT/catalog year (lower is better)."""
    if year_value is None:
        if series_row.start_year is not None:
            return -int(series_row.start_year)
        return 0
    distances: list[int] = []
    cover_year = _issue_cover_year(issue)
    if cover_year is not None:
        distances.append(abs(cover_year - year_value))
    if series_row.start_year is not None:
        distances.append(abs(int(series_row.start_year) - year_value))
    return min(distances) if distances else 5000


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
    publisher_strict: bool = True,
    year: str | None = None,
    issue_title: str | None = None,
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

    text_query = (q or "").strip()
    phrase_clause = _catalog_phrase_search_clause(text_query) if text_query else None

    if alpha_tokens:
        token_clause = and_(*[_catalog_token_search_clause(token) for token in alpha_tokens])
        if phrase_clause is not None and len(alpha_tokens) >= 2:
            statement = statement.where(or_(phrase_clause, token_clause))
        else:
            statement = statement.where(token_clause)
    elif phrase_clause is not None:
        statement = statement.where(phrase_clause)

    if (publisher or "").strip() and publisher_strict:
        statement = statement.where(func.lower(func.coalesce(CatalogPublisher.name, "")).like(f"%{publisher.strip().lower()}%"))
    if issue_token is not None:
        statement = statement.where(CatalogIssue.normalized_issue_number == normalize_issue_number(issue_token))

    # Over-fetch then rank by match quality (exact series + issue first), then series year for disambiguation.
    rows = session.exec(statement.limit(limit * 8)).all()

    year_value: int | None = None
    if (year or "").strip():
        ymatch = re.search(r"(19|20)\d{2}", year)
        if ymatch:
            year_value = int(ymatch.group(0))

    scored_rows: list[tuple[float, CatalogIssue, CatalogSeries, CatalogPublisher | None]] = []
    for issue, series_row, publisher_row in rows:
        if issue.id is None:
            continue
        match_score = _search_match_score(
            issue=issue,
            series_row=series_row,
            publisher_row=publisher_row,
            issue_token=issue_token,
            alpha_tokens=alpha_tokens,
            publisher_filter=publisher,
            year_value=year_value,
            issue_title=issue_title,
        )
        scored_rows.append((match_score, issue, series_row, publisher_row))

    scored_rows.sort(
        key=lambda row: (
            -row[0],
            _catalog_year_distance(issue=row[1], series_row=row[2], year_value=year_value),
            row[2].name.lower(),
            _issue_numeric_value(row[1].issue_number) if _issue_numeric_value(row[1].issue_number) is not None else 10**9,
            int(row[1].id or 0),
        )
    )
    scored_rows = scored_rows[:limit]

    cards: list[RecognitionCatalogCandidateRead] = []
    for match_score, issue, series_row, publisher_row in scored_rows:
        confidence = min(0.99, 0.55 + match_score / 2000.0)
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
