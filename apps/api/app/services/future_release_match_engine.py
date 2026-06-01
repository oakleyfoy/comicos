from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.next_issue import NextIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.lunar_issue_identity import classify_lunar_issue_row, normalize_lunar_issue_number
from app.services.metadata_enrichment import normalize_series_title_with_aliases
from app.services.next_issue_engine import CONFIDENCE_EXACT, CONFIDENCE_STRONG
from app.services.next_issues import latest_next_issue_rows, persist_next_issues

FutureReleaseConfidence = float


@dataclass(frozen=True)
class FutureLunarReleaseRow:
    release_id: int
    publisher: str
    series_name: str
    issue_number: str
    foc_date: date | None
    release_date: date | None
    variant_count: int


@dataclass(frozen=True)
class FutureReleaseMatchCandidate:
    series_name: str
    issue_number: str
    publisher: str
    foc_date: date | None
    release_date: date | None
    release_id: int
    variant_count: int
    confidence: float


def _normalize_issue_label(value: str) -> str:
    return normalize_lunar_issue_number(value)


def _is_lunar_catalog_issue(release_uuid: str) -> bool:
    classification = classify_lunar_issue_row(release_uuid=release_uuid)
    return classification in {"canonical_lunar_issue", "legacy_flat_variant_issue"}


def _is_future_release(*, foc_date: date | None, release_date: date | None, today: date) -> bool:
    if release_date is not None and release_date > today:
        return True
    if foc_date is not None and foc_date >= today:
        return True
    return False


def _load_future_lunar_releases(session: Session, *, owner_user_id: int, today: date) -> list[FutureLunarReleaseRow]:
    variant_counts = dict(
        session.exec(
            select(ReleaseVariant.issue_id, func.count())
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .group_by(ReleaseVariant.issue_id)
        ).all()
    )
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseSeries.series_name.asc(), ReleaseIssue.issue_number.asc())
    ).all()
    out: list[FutureLunarReleaseRow] = []
    for issue, series in rows:
        if issue.id is None or not _is_lunar_catalog_issue(issue.release_uuid):
            continue
        if not _is_future_release(foc_date=issue.foc_date, release_date=issue.release_date, today=today):
            continue
        out.append(
            FutureLunarReleaseRow(
                release_id=int(issue.id),
                publisher=series.publisher.strip(),
                series_name=series.series_name.strip(),
                issue_number=_normalize_issue_label(issue.issue_number),
                foc_date=issue.foc_date,
                release_date=issue.release_date,
                variant_count=int(variant_counts.get(int(issue.id), 0)),
            )
        )
    return out


def _match_future_release(
    *,
    session: Session,
    series_name: str,
    issue_number: str,
    catalog: list[FutureLunarReleaseRow],
) -> tuple[FutureLunarReleaseRow | None, FutureReleaseConfidence]:
    issue_key = _normalize_issue_label(issue_number)
    series_lower = series_name.strip().lower()
    normalized_series = (
        normalize_series_title_with_aliases(series_name, session=session).canonical_value or series_name
    ).strip().lower()

    for row in catalog:
        if row.issue_number != issue_key:
            continue
        if row.series_name.strip().lower() == series_lower:
            return row, CONFIDENCE_EXACT

    for row in catalog:
        if row.issue_number != issue_key:
            continue
        row_normalized = (
            normalize_series_title_with_aliases(row.series_name, session=session).canonical_value or row.series_name
        ).strip().lower()
        if row_normalized == normalized_series:
            return row, CONFIDENCE_STRONG

    return None, 0.0


def _next_issues_for_matching(session: Session, *, owner_user_id: int) -> list[NextIssue]:
    latest = latest_next_issue_rows(session, owner_user_id=owner_user_id)
    if latest:
        return list(latest.values())
    persist_next_issues(session, owner_user_id=owner_user_id)
    return list(latest_next_issue_rows(session, owner_user_id=owner_user_id).values())


def generate_future_release_matches(session: Session, *, owner_user_id: int) -> list[FutureReleaseMatchCandidate]:
    today = date.today()
    next_rows = _next_issues_for_matching(session, owner_user_id=owner_user_id)
    catalog = _load_future_lunar_releases(session, owner_user_id=owner_user_id, today=today)
    candidates: list[FutureReleaseMatchCandidate] = []

    for next_row in next_rows:
        match, confidence = _match_future_release(
            session=session,
            series_name=next_row.series_name,
            issue_number=next_row.next_issue,
            catalog=catalog,
        )
        if match is None or confidence <= 0:
            continue
        candidates.append(
            FutureReleaseMatchCandidate(
                series_name=next_row.series_name,
                issue_number=match.issue_number,
                publisher=match.publisher,
                foc_date=match.foc_date,
                release_date=match.release_date,
                release_id=match.release_id,
                variant_count=match.variant_count,
                confidence=confidence,
            )
        )

    candidates.sort(key=lambda item: (item.series_name.lower(), item.issue_number))
    return candidates
