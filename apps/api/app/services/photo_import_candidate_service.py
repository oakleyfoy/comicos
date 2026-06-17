"""P100 catalog candidate matching for photo detections."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import func, or_
from sqlmodel import Session, delete, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogVariant
from app.models.photo_import import (
    RECOGNITION_STATUS_AMBIGUOUS,
    RECOGNITION_STATUS_MATCHED,
    RECOGNITION_STATUS_UNKNOWN,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
)
from app.services.acquisition.catalog_browse_service import _covers_for_issue_ids
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_issue_number import normalize_photo_issue_number

NO_ISSUE_SCORE_CAP = 65.0
_LAUNCH_HINTS = ("introducing", "initiative", "premiere", "special", "first issue", "launch")


@dataclass
class PhotoImportMatchInput:
    series_guess: str = ""
    issue_number_guess: str = ""
    publisher_guess: str = ""
    subtitle_guess: str = ""
    variant_guess: str = ""
    cover_year_guess: str = ""
    visible_title_text: str = ""
    visible_issue_text: str = ""
    visible_publisher_text: str = ""
    visible_character_text: str = ""
    alternate_titles: list[str] = field(default_factory=list)


@dataclass
class ScoredCatalogRow:
    issue: CatalogIssue
    series: CatalogSeries
    publisher: CatalogPublisher | None
    match_score: float
    match_reason: str
    matched_on: str


def _strip_issue(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"^#+\s*", "", str(value).strip())


def _issue_from_detection(det: PhotoImportDetectedBook) -> str:
    for raw in (det.ai_issue_number, det.ai_visible_issue_text):
        if not raw:
            continue
        sanitized = normalize_photo_issue_number(str(raw))
        if sanitized:
            return normalize_issue_number(sanitized)
    return ""


def build_match_input_from_detection(det: PhotoImportDetectedBook) -> PhotoImportMatchInput:
    alternates: list[str] = []
    if det.ai_alternate_titles:
        alternates = [str(t).strip() for t in det.ai_alternate_titles if str(t).strip()]
    return PhotoImportMatchInput(
        series_guess=(det.ai_series or "").strip(),
        issue_number_guess=_issue_from_detection(det),
        publisher_guess=(det.ai_publisher or det.ai_visible_publisher_text or "").strip(),
        subtitle_guess=(det.ai_subtitle_guess or "").strip(),
        variant_guess=(det.ai_variant_guess or det.ai_variant_hint or "").strip(),
        cover_year_guess=(det.ai_cover_year or "").strip(),
        visible_title_text=(det.ai_visible_title_text or "").strip(),
        visible_issue_text=(det.ai_visible_issue_text or "").strip(),
        visible_publisher_text=(det.ai_visible_publisher_text or "").strip(),
        visible_character_text=(det.ai_visible_character_text or "").strip(),
        alternate_titles=alternates,
    )


def _series_tokens(inp: PhotoImportMatchInput) -> list[str]:
    tokens: list[str] = []
    for raw in (
        inp.series_guess,
        inp.visible_title_text,
        inp.subtitle_guess,
        inp.visible_character_text,
        *inp.alternate_titles,
    ):
        text = (raw or "").strip()
        if text and text not in tokens:
            tokens.append(text)
    return tokens


def _norm_series(value: str) -> str:
    return normalize_series_name(value)


def _publisher_matches(publisher: CatalogPublisher | None, guess: str) -> bool:
    if not guess or publisher is None:
        return False
    g = guess.lower()
    name = (publisher.name or "").lower()
    norm = (publisher.normalized_name or "").lower()
    return g in name or name in g or g in norm


def _exact_series(series: CatalogSeries, token: str) -> bool:
    if not token:
        return False
    return _norm_series(series.name) == _norm_series(token)


def _fuzzy_series(series: CatalogSeries, token: str) -> bool:
    if not token:
        return False
    norm_token = _norm_series(token)
    norm_name = _norm_series(series.name)
    if norm_token == norm_name:
        return True
    if norm_token in norm_name or norm_name in norm_token:
        return True
    return norm_token.split()[0] in norm_name if norm_token.split() else False


def _exact_issue(issue: CatalogIssue, issue_num: str) -> bool:
    if not issue_num:
        return False
    norm = normalize_issue_number(issue_num)
    return issue.normalized_issue_number == norm or normalize_issue_number(str(issue.issue_number)) == norm


def _score_row(
    *,
    inp: PhotoImportMatchInput,
    series_token: str,
    issue: CatalogIssue,
    series: CatalogSeries,
    publisher: CatalogPublisher | None,
    matched_on: str,
) -> ScoredCatalogRow | None:
    issue_num = inp.issue_number_guess
    pub = publisher
    if matched_on == "exact_series_issue_publisher":
        if not (_exact_series(series, series_token) and _exact_issue(issue, issue_num)):
            return None
        if not _publisher_matches(pub, inp.publisher_guess):
            return None
        reason = f"Exact series and issue number match: {series.name} #{issue.issue_number} / {pub.name if pub else 'unknown publisher'}"
        return ScoredCatalogRow(issue, series, pub, 98.0, reason, matched_on)
    if matched_on == "exact_series_issue":
        if not (_exact_series(series, series_token) and _exact_issue(issue, issue_num)):
            return None
        reason = f"Exact series and issue number match: {series.name} #{issue.issue_number}"
        return ScoredCatalogRow(issue, series, pub, 92.0, reason, matched_on)
    if matched_on == "alternate_title_issue":
        if not (_exact_issue(issue, issue_num) and _fuzzy_series(series, series_token)):
            return None
        reason = f"Alternate title match: {series_token} #{issue.issue_number}"
        return ScoredCatalogRow(issue, series, pub, 85.0, reason, matched_on)
    if matched_on == "visible_text_issue":
        if not (_exact_issue(issue, issue_num) and _fuzzy_series(series, series_token)):
            return None
        reason = f"Visible title text match: {series_token} #{issue.issue_number}"
        return ScoredCatalogRow(issue, series, pub, 82.0, reason, matched_on)
    if matched_on == "fuzzy_series_publisher":
        if not (_fuzzy_series(series, series_token) and _publisher_matches(pub, inp.publisher_guess)):
            return None
        if issue_num and not _exact_issue(issue, issue_num):
            return None
        reason = f"Fuzzy series with publisher: {series.name} #{issue.issue_number}"
        score = 75.0 if issue_num else 55.0
        return ScoredCatalogRow(issue, series, pub, score, reason, matched_on)
    if matched_on == "fuzzy_series":
        if not _fuzzy_series(series, series_token):
            return None
        if issue_num and not _exact_issue(issue, issue_num):
            return None
        reason = f"Fuzzy series match: {series.name} #{issue.issue_number}"
        score = 68.0 if issue_num else 45.0
        return ScoredCatalogRow(issue, series, pub, score, reason, matched_on)
    if matched_on == "character_title_fallback":
        token = inp.visible_character_text or inp.visible_title_text
        if not token or not _fuzzy_series(series, token):
            return None
        reason = f"Character/title fallback: {series.name} #{issue.issue_number}"
        return ScoredCatalogRow(issue, series, pub, 40.0, reason, matched_on)
    return None


def _subtitle_blob(inp: PhotoImportMatchInput) -> str:
    return " ".join(
        part
        for part in (inp.subtitle_guess, inp.visible_title_text, inp.visible_issue_text, inp.series_guess)
        if part
    ).lower()


def _subtitle_identifies_issue(
    inp: PhotoImportMatchInput,
    *,
    issue: CatalogIssue,
    series: CatalogSeries,
) -> bool:
    sub = (inp.subtitle_guess or "").strip().lower()
    if not sub or len(sub) < 6:
        return False
    series_name = (series.name or "").lower()
    issue_title = (issue.title or "").lower()
    if sub in series_name and len(sub.split()) >= 2:
        return True
    return sub in issue_title and len(sub.split()) >= 2


def _score_no_issue_row(
    *,
    inp: PhotoImportMatchInput,
    series_token: str,
    issue: CatalogIssue,
    series: CatalogSeries,
    publisher: CatalogPublisher | None,
) -> ScoredCatalogRow | None:
    if inp.issue_number_guess:
        return None
    if not inp.series_guess and not series_token:
        return None
    if not (_exact_series(series, inp.series_guess or series_token) or _fuzzy_series(series, series_token)):
        return None

    subtitle = _subtitle_blob(inp)
    uniquely_identified = _subtitle_identifies_issue(inp, issue=issue, series=series)
    exact_series = _exact_series(series, inp.series_guess or series_token)
    pub_match = _publisher_matches(publisher, inp.publisher_guess)

    matched_on = "fuzzy_series_no_issue"
    score = 48.0
    reason = f"Series match without issue number: {series.name} #{issue.issue_number}"

    if exact_series and pub_match:
        matched_on = "series_publisher_no_issue"
        score = 58.0
        reason = f"Series + publisher match (no issue on cover): {series.name} #{issue.issue_number}"
    if subtitle and (uniquely_identified or inp.subtitle_guess):
        matched_on = "visible_text_no_issue"
        score = 62.0
        reason = f"Series + visible subtitle match: {series.name} #{issue.issue_number}"

    if subtitle and any(hint in subtitle for hint in _LAUNCH_HINTS):
        if str(issue.issue_number) in {"0", "1", "0.1"}:
            score += 4.0

    if not uniquely_identified:
        score = min(score, NO_ISSUE_SCORE_CAP)
    else:
        score = min(max(score, 68.0), 72.0)

    return ScoredCatalogRow(issue, series, publisher, score, reason, matched_on)


def _fetch_catalog_rows(session: Session, *, series_fragment: str, issue_num: str, limit: int = 80) -> list[tuple[CatalogIssue, CatalogSeries, CatalogPublisher | None]]:
    if not series_fragment and not issue_num:
        return []
    stmt = (
        select(CatalogIssue, CatalogSeries, CatalogPublisher)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
    )
    frag = series_fragment[:80] if series_fragment else ""
    if frag:
        norm = _norm_series(frag)
        like = f"%{frag}%"
        stmt = stmt.where(
            or_(
                CatalogSeries.name.ilike(like),
                CatalogSeries.normalized_name.ilike(f"%{norm}%"),
                func.lower(CatalogSeries.name).contains(frag.lower()),
            )
        )
    if issue_num:
        norm_issue = normalize_issue_number(issue_num)
        stmt = stmt.where(
            or_(
                CatalogIssue.normalized_issue_number == norm_issue,
                CatalogIssue.issue_number.ilike(f"%{issue_num}%"),
            )
        )
    stmt = stmt.order_by(CatalogIssue.id.desc()).limit(limit)
    return list(session.exec(stmt).all())


def generate_scored_candidates(session: Session, inp: PhotoImportMatchInput) -> tuple[list[ScoredCatalogRow], list[str]]:
    """Return ranked unique candidates and search terms used."""
    search_terms: list[str] = []
    strategies = [
        "exact_series_issue_publisher",
        "exact_series_issue",
        "alternate_title_issue",
        "visible_text_issue",
        "fuzzy_series_publisher",
        "fuzzy_series",
        "character_title_fallback",
    ]
    tokens = _series_tokens(inp)
    if inp.series_guess:
        search_terms.append(f"series:{inp.series_guess}")
    if inp.issue_number_guess:
        search_terms.append(f"issue:{inp.issue_number_guess}")
    if inp.visible_issue_text:
        search_terms.append(f"visible_issue:{inp.visible_issue_text}")
    for alt in inp.alternate_titles:
        search_terms.append(f"alt:{alt}")

    seen_issue_ids: set[int] = set()
    ranked: list[ScoredCatalogRow] = []

    query_tokens = list(tokens)
    if inp.series_guess and inp.series_guess not in query_tokens:
        query_tokens.insert(0, inp.series_guess)

    for token in query_tokens:
        if token:
            search_terms.append(f"query:{token}")
        rows = _fetch_catalog_rows(session, series_fragment=token, issue_num=inp.issue_number_guess)
        if not rows and inp.issue_number_guess:
            rows = _fetch_catalog_rows(session, series_fragment=token, issue_num="")
        strategy_list = strategies if inp.issue_number_guess else []
        for matched_on in strategy_list:
            for issue, series, publisher in rows:
                iid = int(issue.id or 0)
                if iid in seen_issue_ids:
                    continue
                scored = _score_row(
                    inp=inp,
                    series_token=token,
                    issue=issue,
                    series=series,
                    publisher=publisher,
                    matched_on=matched_on,
                )
                if scored is None:
                    continue
                seen_issue_ids.add(iid)
                ranked.append(scored)

        if not inp.issue_number_guess and token:
            search_terms.append(f"series_no_issue:{token}")
            no_issue_rows = _fetch_catalog_rows(session, series_fragment=token, issue_num="", limit=40)
            for issue, series, publisher in no_issue_rows:
                iid = int(issue.id or 0)
                if iid in seen_issue_ids:
                    continue
                scored = _score_no_issue_row(
                    inp=inp,
                    series_token=token,
                    issue=issue,
                    series=series,
                    publisher=publisher,
                )
                if scored is None:
                    continue
                seen_issue_ids.add(iid)
                ranked.append(scored)

    if not ranked and query_tokens:
        for token in query_tokens[:3]:
            rows = _fetch_catalog_rows(session, series_fragment=token, issue_num="", limit=30)
            for issue, series, publisher in rows:
                iid = int(issue.id or 0)
                if iid in seen_issue_ids:
                    continue
                if inp.issue_number_guess:
                    scored = _score_row(
                        inp=inp,
                        series_token=token,
                        issue=issue,
                        series=series,
                        publisher=publisher,
                        matched_on="fuzzy_series",
                    )
                else:
                    scored = _score_no_issue_row(
                        inp=inp,
                        series_token=token,
                        issue=issue,
                        series=series,
                        publisher=publisher,
                    )
                if scored:
                    seen_issue_ids.add(iid)
                    ranked.append(scored)
                    search_terms.append(f"broad:{token}")

    ranked.sort(key=lambda row: row.match_score, reverse=True)
    return ranked[:10], search_terms


def refresh_candidates_for_detection(session: Session, *, detected_book_id: int) -> None:
    det = session.get(PhotoImportDetectedBook, detected_book_id)
    if det is None:
        return
    session.exec(delete(PhotoImportCandidate).where(PhotoImportCandidate.detected_book_id == detected_book_id))

    inp = build_match_input_from_detection(det)
    has_text = bool(
        inp.series_guess
        or inp.visible_title_text
        or inp.alternate_titles
        or inp.visible_character_text
        or inp.subtitle_guess
    )
    scored, _search_terms = generate_scored_candidates(session, inp) if has_text else ([], [])

    issue_ids = [int(row.issue.id or 0) for row in scored]
    covers = _covers_for_issue_ids(session, issue_ids)

    for rank, row in enumerate(scored, start=1):
        variant = session.exec(
            select(CatalogVariant).where(CatalogVariant.issue_id == row.issue.id).order_by(CatalogVariant.id.asc())
        ).first()
        session.add(
            PhotoImportCandidate(
                detected_book_id=detected_book_id,
                catalog_issue_id=int(row.issue.id or 0),
                variant_id=int(variant.id) if variant and variant.id else None,
                publisher=row.publisher.name if row.publisher else None,
                series=row.series.name,
                issue_number=str(row.issue.issue_number),
                variant_name=variant.variant_name if variant else None,
                cover_url=covers.get(int(row.issue.id or 0)),
                release_date=str(getattr(row.issue, "cover_date", "") or "") or None,
                match_score=row.match_score,
                match_reason=row.match_reason,
                matched_on=row.matched_on,
                rank=rank,
            )
        )

    det.candidate_count = len(scored)
    if scored:
        det.recognition_status = RECOGNITION_STATUS_MATCHED if scored[0].match_score >= 70 else RECOGNITION_STATUS_UNKNOWN
        if len(scored) > 1 and scored[0].match_score - scored[1].match_score < 8:
            det.recognition_status = RECOGNITION_STATUS_AMBIGUOUS
    else:
        det.recognition_status = RECOGNITION_STATUS_UNKNOWN

    session.add(det)
    session.commit()


def candidate_debug_info(session: Session, *, detected_book_id: int) -> dict[str, object]:
    det = session.get(PhotoImportDetectedBook, detected_book_id)
    if det is None:
        return {}
    inp = build_match_input_from_detection(det)
    scored, search_terms = generate_scored_candidates(session, inp)
    best_score = scored[0].match_score if scored else 0.0
    return {
        "search_terms_used": search_terms,
        "candidate_count": len(scored),
        "best_match_score": best_score,
        "match_input": {
            "series_guess": inp.series_guess,
            "issue_number_guess": inp.issue_number_guess,
            "publisher_guess": inp.publisher_guess,
            "alternate_titles": inp.alternate_titles,
            "visible_title_text": inp.visible_title_text,
            "visible_issue_text": inp.visible_issue_text,
        },
    }
