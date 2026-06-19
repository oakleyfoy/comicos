"""P100 catalog candidate matching for photo detections."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import func, or_
from sqlmodel import Session, delete, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogVariant
from app.models.photo_import import (
    RECOGNITION_STATUS_AMBIGUOUS,
    RECOGNITION_STATUS_MATCHED,
    RECOGNITION_STATUS_UNKNOWN,
    CAPTURE_MODE_SINGLE_COMIC,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportSession,
)
from app.services.photo_import_candidate_cover_service import (
    cover_and_thumbnail_urls_for_photo_import_candidates,
    cover_urls_for_photo_import_candidates,
)
from app.services.photo_import_cover_similarity_service import cover_similarity_score_for_issue
from app.services.photo_import_crop_service import resolve_crop_abs_path
from app.services.photo_import_fingerprint_service import fingerprint_hashes_for_crop, fingerprint_match_score_for_issue
from app.services.photo_import_learning_service import learning_boost_for_issue
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_issue_number import normalize_photo_issue_number
from app.services.photo_import_session_service import normalize_capture_mode

logger = logging.getLogger(__name__)

NO_ISSUE_SCORE_CAP = 65.0
AUTO_SELECT_MIN_SCORE = 95.0
AUTO_SELECT_MIN_GAP = 15.0
WEIGHT_FINGERPRINT = 0.40
WEIGHT_COVER_SIMILARITY = 0.35
WEIGHT_TEXT = 0.20
WEIGHT_PUBLISHER_META = 0.05
TEXT_ONLY_PENALTY = 12.0
STRONG_VISUAL_BOOST = 5.0

_AMBIGUOUS_SERIES_FAMILIES: dict[str, list[str]] = {
    "x": ["X-Men", "X-Factor", "X-Force", "X-Man", "Uncanny X-Men"],
    "spider": ["Spider-Man", "Spider-Woman", "The Amazing Spider-Man", "Spectacular Spider-Man"],
    "captain": ["Captain America", "Captain Marvel", "Captain Britain"],
    "batman": ["Batman", "Detective Comics", "Batman and the Outsiders"],
    "superman": ["Superman", "Action Comics", "Adventures of Superman"],
}
_LAUNCH_HINTS = ("introducing", "initiative", "premiere", "special", "first issue", "launch")

# Conservative series-name corrections for common AI pluralization / noise.
# Keep this list tiny and unambiguous; never add risky guesses (e.g. Lightning Star -> Lightning Strikes).
_SERIES_ALIASES: dict[str, str] = {
    "babes": "Babe",
}

# matched_on strategies that must never drive bulk auto-confirm (manual selection required).
NON_AUTO_CONFIRM_MATCHED_ON: frozenset[str] = frozenset(
    {
        "fuzzy_series",
        "fuzzy_series_no_issue",
        "fuzzy_series_publisher_no_issue",
        "series_no_issue",
        "series_publisher_no_issue",
        "visible_text_no_issue",
        "character_title_fallback",
    }
)

# Words too weak/common to single out one catalog issue from a subtitle alone.
_WEAK_SUBTITLE_WORDS: frozenset[str] = frozenset(
    {
        "evil",
        "initiative",
        "special",
        "blood",
        "war",
        "origin",
        "origins",
        "begins",
        "returns",
        "rising",
        "rises",
        "reborn",
        "legacy",
        "first",
        "new",
        "dark",
        "death",
        "rebirth",
        "forever",
    }
)
_SUBTITLE_STOPWORDS: frozenset[str] = frozenset({"the", "a", "an", "of", "and", "to", "in", "part"})
_DISTINCTIVE_SUBTITLE_MIN_WORDS = 4


def _meaningful_subtitle_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _SUBTITLE_STOPWORDS]


def _subtitle_is_distinctive(subtitle: str) -> bool:
    """A subtitle is distinctive only when it is a multi-word phrase, not a single weak word."""
    words = _meaningful_subtitle_words(subtitle)
    if not words:
        return False
    if len(words) >= _DISTINCTIVE_SUBTITLE_MIN_WORDS:
        return True
    return False


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
    base_text_score: float = 0.0
    cover_similarity_score: float = 0.0
    fingerprint_score: float = 0.0
    publisher_meta_score: float = 0.0
    visual_score_status: str = "unavailable"
    visual_match_label: str = "No cover available"


def _expand_ambiguous_series_tokens(tokens: list[str]) -> list[str]:
    """Broaden short/ambiguous AI titles so cover ranking can disambiguate (e.g. X vs X-Factor)."""
    expanded: list[str] = list(tokens)
    for raw in tokens:
        key = (raw or "").strip().lower()
        if not key:
            continue
        families: list[str] | None = None
        if key in _AMBIGUOUS_SERIES_FAMILIES:
            families = _AMBIGUOUS_SERIES_FAMILIES[key]
        elif len(key) <= 3 and key in _AMBIGUOUS_SERIES_FAMILIES:
            families = _AMBIGUOUS_SERIES_FAMILIES[key]
        elif key in {"captain", "spider", "batman", "superman"}:
            families = _AMBIGUOUS_SERIES_FAMILIES.get(key)
        if not families:
            continue
        for name in families:
            if name not in expanded:
                expanded.append(name)
    return expanded


def _visual_match_label(*, status: str, cover: float, fingerprint: float) -> str:
    if status == "unavailable":
        return "No cover available"
    if fingerprint >= 55:
        return "Fingerprint match"
    if cover >= 55:
        return "Cover match"
    if cover >= 25 or fingerprint >= 25:
        return "Partial visual match"
    return "Text match only"


def _exact_issue_matched_on(matched_on: str) -> bool:
    return matched_on in {
        "exact_series_issue_publisher",
        "exact_series_issue",
        "alternate_title_issue",
        "visible_text_issue",
    }


def _score_row_with_base(row: ScoredCatalogRow) -> ScoredCatalogRow:
    row.base_text_score = float(row.match_score)
    return row


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


def _series_alias(token: str) -> str | None:
    """Return a conservative corrected series name for a token, else None."""
    if not token:
        return None
    return _SERIES_ALIASES.get(_norm_series(token))


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
        alias = _series_alias(text)
        if alias and alias not in tokens:
            tokens.append(alias)
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
    """A subtitle may pin one specific issue only when it is distinctive or matches catalog text exactly.

    Single weak words (Evil, Initiative, Special, War, ...) must never single out an issue.
    """
    sub = (inp.subtitle_guess or inp.visible_title_text or "").strip().lower()
    if not sub:
        return False

    issue_title = (issue.title or "").strip().lower()
    series_name = (series.name or "").strip().lower()

    # Exact catalog title/series text match is always a strong signal.
    if issue_title and sub == issue_title:
        return True
    if series_name and sub == series_name and len(_meaningful_subtitle_words(sub)) >= 2:
        return True

    # Otherwise require a distinctive multi-word phrase that actually appears in catalog text.
    if not _subtitle_is_distinctive(sub):
        return False
    if issue_title and sub in issue_title:
        return True
    if series_name and sub in series_name:
        return True
    return False


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

    # Series-level baseline tiers (no issue number): exact+publisher > exact > fuzzy+publisher > fuzzy.
    if exact_series and pub_match:
        matched_on = "series_publisher_no_issue"
        score = 58.0
        reason = f"Series + publisher match (no issue on cover): {series.name} #{issue.issue_number}"
    elif exact_series:
        matched_on = "series_no_issue"
        score = 52.0
        reason = f"Series match (no issue on cover): {series.name} #{issue.issue_number}"
    elif pub_match:
        matched_on = "fuzzy_series_publisher_no_issue"
        score = 50.0
        reason = f"Fuzzy series + publisher (no issue on cover): {series.name} #{issue.issue_number}"
    else:
        matched_on = "fuzzy_series_no_issue"
        score = 45.0
        reason = f"Fuzzy series match (no issue on cover): {series.name} #{issue.issue_number}"

    # A subtitle/visible-text signal may boost a SPECIFIC issue only when distinctive or an exact catalog match.
    # Weak single words (Evil, Initiative, ...) never boost a particular issue.
    if uniquely_identified:
        matched_on = "visible_text_no_issue"
        score = min(max(score, 68.0), 72.0)
        reason = f"Series + distinctive subtitle match: {series.name} #{issue.issue_number}"
    else:
        # Launch hint nudges #0/#1 slightly for series-level ordering, but stays below auto-confirm.
        if subtitle and any(hint in subtitle for hint in _LAUNCH_HINTS) and str(issue.issue_number) in {"0", "1", "0.1"}:
            score += 4.0
        score = min(score, NO_ISSUE_SCORE_CAP)

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
    tokens = _expand_ambiguous_series_tokens(_series_tokens(inp))
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
                ranked.append(_score_row_with_base(scored))

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
                ranked.append(_score_row_with_base(scored))

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
                    ranked.append(_score_row_with_base(scored))
                    search_terms.append(f"broad:{token}")

    def _issue_order(row: ScoredCatalogRow) -> float:
        num = re.match(r"\d+", str(row.issue.issue_number or "").strip().lstrip("#"))
        return float(num.group(0)) if num else 1e9

    # Primary: score desc. Tie-break: lower issue number first (so #1/#2 lead a series list), then issue id.
    ranked.sort(key=lambda row: (-row.match_score, _issue_order(row), int(row.issue.id or 0)))
    return ranked[:10], search_terms


def _apply_visual_ranking(
    session: Session,
    *,
    det: PhotoImportDetectedBook,
    ranked: list[ScoredCatalogRow],
) -> list[ScoredCatalogRow]:
    crop_abs = resolve_crop_abs_path(det.crop_path)
    if crop_abs is None or not ranked:
        for row in ranked:
            row.base_text_score = float(row.match_score)
            row.visual_score_status = "unavailable"
            row.visual_match_label = "No cover available"
        return ranked
    logger.debug(
        "photo_import.candidates.visual_compare detection_id=%s visual_comparison_source=crop",
        det.id,
    )
    crop_hashes = fingerprint_hashes_for_crop(crop_abs)
    phash_prefix = crop_hashes[0][:16] if crop_hashes else None
    visually_scored: list[ScoredCatalogRow] = []
    for row in ranked:
        iid = int(row.issue.id or 0)
        base_text = float(row.base_text_score or row.match_score)
        pub_meta = 100.0 if _publisher_matches(row.publisher, det.ai_publisher or det.ai_visible_publisher_text or "") else 0.0
        cover_sim = cover_similarity_score_for_issue(session, crop_path=crop_abs, catalog_issue_id=iid)
        fp_sim = (
            fingerprint_match_score_for_issue(session, crop_hashes=crop_hashes, catalog_issue_id=iid)
            if crop_hashes
            else 0.0
        )
        boost = learning_boost_for_issue(
            catalog_issue_id=iid,
            series_guess=det.ai_series or "",
            crop_phash_prefix=phash_prefix,
        )
        has_visual = cover_sim > 0 or fp_sim > 0
        if has_visual:
            combined = (
                fp_sim * WEIGHT_FINGERPRINT
                + cover_sim * WEIGHT_COVER_SIMILARITY
                + base_text * WEIGHT_TEXT
                + pub_meta * WEIGHT_PUBLISHER_META
                + boost
            )
            if base_text >= 75 and cover_sim < 35 and fp_sim < 35:
                combined = max(0.0, combined - TEXT_ONLY_PENALTY)
            if cover_sim >= 65 or fp_sim >= 65:
                combined = min(100.0, combined + STRONG_VISUAL_BOOST)
            status = "available"
        else:
            combined = min(100.0, base_text + boost)
            status = "unavailable"
        combined = min(100.0, combined)
        label = _visual_match_label(status=status, cover=cover_sim, fingerprint=fp_sim)
        reason_parts = [row.match_reason, label]
        if cover_sim >= 40:
            reason_parts.append(f"cover {cover_sim:.0f}")
        if fp_sim >= 40:
            reason_parts.append(f"fingerprint {fp_sim:.0f}")
        if boost > 0:
            reason_parts.append(f"learning +{boost:.0f}")
        visually_scored.append(
            ScoredCatalogRow(
                issue=row.issue,
                series=row.series,
                publisher=row.publisher,
                match_score=combined,
                match_reason="; ".join(p for p in reason_parts if p),
                matched_on=row.matched_on,
                base_text_score=base_text,
                cover_similarity_score=cover_sim,
                fingerprint_score=fp_sim,
                publisher_meta_score=pub_meta,
                visual_score_status=status,
                visual_match_label=label,
            )
        )
    visually_scored.sort(
        key=lambda row: (-row.match_score, int(row.issue.id or 0)),
    )
    return visually_scored


def _visual_signal_for_auto_select(row: ScoredCatalogRow) -> bool:
    if row.visual_score_status == "available":
        return row.cover_similarity_score >= 50 or row.fingerprint_score >= 50
    return _exact_issue_matched_on(row.matched_on or "")


def _maybe_auto_select_issue(
    det: PhotoImportDetectedBook,
    ranked: list[ScoredCatalogRow],
) -> None:
    if len(ranked) < 1:
        return
    top = ranked[0]
    second_score = ranked[1].match_score if len(ranked) > 1 else 0.0
    if top.match_score < AUTO_SELECT_MIN_SCORE:
        return
    if top.match_score - second_score < AUTO_SELECT_MIN_GAP:
        return
    if (top.matched_on or "") in NON_AUTO_CONFIRM_MATCHED_ON:
        return
    if not _visual_signal_for_auto_select(top):
        return
    det.selected_catalog_issue_id = int(top.issue.id or 0)
    det.selected_variant_id = None


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
    import_row = session.get(PhotoImportSession, int(det.session_id))
    single_comic = import_row is not None and normalize_capture_mode(import_row.capture_mode) == CAPTURE_MODE_SINGLE_COMIC
    if single_comic and scored:
        logger.info(
            "photo_import.candidates.ranking detection_id=%s recognition_source=full_image "
            "text_source=full_image visual_comparison_source=crop display_crop=true",
            detected_book_id,
        )
    scored = _apply_visual_ranking(session, det=det, ranked=scored) if scored else scored

    issue_ids = [int(row.issue.id or 0) for row in scored]
    variant_by_issue: dict[int, CatalogVariant | None] = {}
    variant_id_by_issue: dict[int, int | None] = {}
    for row in scored:
        iid = int(row.issue.id or 0)
        variant = session.exec(
            select(CatalogVariant).where(CatalogVariant.issue_id == row.issue.id).order_by(CatalogVariant.id.asc())
        ).first()
        variant_by_issue[iid] = variant
        variant_id_by_issue[iid] = int(variant.id) if variant and variant.id else None
    covers = cover_and_thumbnail_urls_for_photo_import_candidates(
        session,
        issue_ids=issue_ids,
        variant_id_by_issue=variant_id_by_issue,
    )

    for rank, row in enumerate(scored, start=1):
        iid = int(row.issue.id or 0)
        variant = variant_by_issue.get(iid)
        cover, thumb = covers.get(iid, (None, None))
        breakdown = {
            "base_text_score": row.base_text_score,
            "cover_similarity_score": row.cover_similarity_score,
            "fingerprint_score": row.fingerprint_score,
            "publisher_meta_score": row.publisher_meta_score,
            "final_score": row.match_score,
            "matched_on": row.matched_on,
            "visual_score_status": row.visual_score_status,
            "visual_match_label": row.visual_match_label,
        }
        session.add(
            PhotoImportCandidate(
                detected_book_id=detected_book_id,
                catalog_issue_id=int(row.issue.id or 0),
                variant_id=int(variant.id) if variant and variant.id else None,
                publisher=row.publisher.name if row.publisher else None,
                series=row.series.name,
                issue_number=str(row.issue.issue_number),
                variant_name=variant.variant_name if variant else None,
                cover_url=cover,
                thumbnail_url=thumb or cover,
                release_date=str(getattr(row.issue, "cover_date", "") or "") or None,
                match_score=row.match_score,
                match_reason=row.match_reason,
                matched_on=row.matched_on,
                rank=rank,
                score_breakdown=breakdown,
            )
        )

    det.candidate_count = len(scored)
    if scored:
        det.recognition_status = RECOGNITION_STATUS_MATCHED if scored[0].match_score >= 70 else RECOGNITION_STATUS_UNKNOWN
        if len(scored) > 1 and scored[0].match_score - scored[1].match_score < AUTO_SELECT_MIN_GAP:
            det.recognition_status = RECOGNITION_STATUS_AMBIGUOUS
    else:
        det.recognition_status = RECOGNITION_STATUS_UNKNOWN

    _maybe_auto_select_issue(det, scored)

    top = scored[0] if scored else None
    logger.info(
        "photo_import.candidates detection_id=%s raw_publisher=%r raw_series=%r normalized_series=%r "
        "issue_number=%r subtitle=%r candidate_count=%d strategy=%s top=%s recognition_status=%s no_candidate_reason=%s",
        detected_book_id,
        inp.publisher_guess,
        inp.series_guess,
        _norm_series(inp.series_guess) if inp.series_guess else "",
        inp.issue_number_guess or None,
        inp.subtitle_guess or None,
        len(scored),
        top.matched_on if top else None,
        (
            f"id={top.issue.id} {top.series.name} #{top.issue.issue_number} score={top.match_score:.0f}"
            if top
            else None
        ),
        det.recognition_status,
        None if scored else ("no_text" if not has_text else "no_catalog_match"),
    )

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
