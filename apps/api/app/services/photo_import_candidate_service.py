"""P100 catalog candidate matching for photo detections."""

from __future__ import annotations

import re

from sqlalchemy import func, or_
from sqlmodel import Session, delete, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogVariant
from app.models.photo_import import PhotoImportCandidate, PhotoImportDetectedBook
from app.services.acquisition.catalog_browse_service import _covers_for_issue_ids


def _norm_issue(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"^#+", "", str(value).strip()).lower()


def _score_issue(
    *,
    series_name: str,
    issue_number: str,
    publisher_name: str | None,
    cover_year: str | None,
    ai_series: str | None,
    ai_issue: str | None,
    ai_publisher: str | None,
    ai_year: str | None,
) -> tuple[float, str]:
    score = 0.0
    reasons: list[str] = []
    if ai_series and series_name.lower() in ai_series.lower():
        score += 40
        reasons.append("series")
    elif ai_series and ai_series.lower() in series_name.lower():
        score += 35
        reasons.append("series_partial")
    if ai_issue and _norm_issue(issue_number) == _norm_issue(ai_issue):
        score += 35
        reasons.append("issue_number")
    if ai_publisher and publisher_name and ai_publisher.lower() in publisher_name.lower():
        score += 15
        reasons.append("publisher")
    if ai_year and cover_year and ai_year in str(cover_year):
        score += 10
        reasons.append("year")
    return score, "+".join(reasons) if reasons else "catalog_search"


def refresh_candidates_for_detection(session: Session, *, detected_book_id: int) -> None:
    det = session.get(PhotoImportDetectedBook, detected_book_id)
    if det is None:
        return
    session.exec(delete(PhotoImportCandidate).where(PhotoImportCandidate.detected_book_id == detected_book_id))

    ai_series = (det.ai_series or "").strip()
    ai_issue = det.ai_issue_number
    ai_pub = det.ai_publisher
    ai_year = det.ai_cover_year

    stmt = (
        select(CatalogIssue, CatalogSeries, CatalogPublisher)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
    )
    if ai_series:
        stmt = stmt.where(
            or_(
                CatalogSeries.name.ilike(f"%{ai_series[:80]}%"),
                func.lower(CatalogSeries.name).contains(ai_series[:80].lower()),
            )
        )
    if ai_issue:
        stmt = stmt.where(CatalogIssue.issue_number.ilike(f"%{_norm_issue(ai_issue)}%"))
    stmt = stmt.order_by(CatalogIssue.id.desc()).limit(40)
    rows = list(session.exec(stmt).all())

    scored: list[tuple[float, str, CatalogIssue, CatalogSeries, CatalogPublisher | None]] = []
    for issue, series, publisher in rows:
        s, reason = _score_issue(
            series_name=series.name,
            issue_number=str(issue.issue_number),
            publisher_name=publisher.name if publisher else None,
            cover_year=str(issue.cover_date or "") if hasattr(issue, "cover_date") else None,
            ai_series=ai_series,
            ai_issue=ai_issue,
            ai_publisher=ai_pub,
            ai_year=ai_year,
        )
        if s <= 0 and ai_series:
            s = 5.0
            reason = "broad_match"
        scored.append((s, reason, issue, series, publisher))

    scored.sort(key=lambda row: row[0], reverse=True)
    top = scored[:10]
    issue_ids = [int(issue.id or 0) for _, _, issue, _, _ in top]
    covers = _covers_for_issue_ids(session, issue_ids)

    for rank, (match_score, reason, issue, series, publisher) in enumerate(top, start=1):
        variant = session.exec(
            select(CatalogVariant).where(CatalogVariant.issue_id == issue.id).order_by(CatalogVariant.id.asc())
        ).first()
        session.add(
            PhotoImportCandidate(
                detected_book_id=detected_book_id,
                catalog_issue_id=int(issue.id or 0),
                variant_id=int(variant.id) if variant and variant.id else None,
                publisher=publisher.name if publisher else None,
                series=series.name,
                issue_number=str(issue.issue_number),
                variant_name=variant.variant_name if variant else None,
                cover_url=covers.get(int(issue.id or 0)),
                release_date=str(getattr(issue, "cover_date", "") or "") or None,
                match_score=match_score,
                match_reason=reason,
                rank=rank,
            )
        )
    det.candidate_count = len(top)
    if top:
        best_score = top[0][0]
        best_issue = top[0][2]
        best_variant = session.exec(
            select(CatalogVariant).where(CatalogVariant.issue_id == best_issue.id).order_by(CatalogVariant.id.asc())
        ).first()
        det.selected_catalog_issue_id = int(best_issue.id or 0)
        det.selected_variant_id = int(best_variant.id) if best_variant and best_variant.id else None
        det.confidence = max(float(det.ai_confidence or 0), best_score / 100.0)
    session.add(det)
    session.commit()
