"""P90-09B ranked catalog matching for import draft release resolution."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.metadata_aliases import STATIC_PUBLISHER_ALIAS_MAP, normalize_alias_lookup_key

CatalogSource = Literal["ReleaseIssue", "ExternalCatalogIssue"]

logger = logging.getLogger(__name__)

ACCEPT_SCORE = 70
POSSIBLE_SCORE = 55
STRONG_TITLE_ISSUE_MIN_SCORE = 60
CANDIDATE_LIMIT = 100

_TITLE_SEARCH_STOP = frozenset({"the", "and", "for", "vol", "volume", "live", "ai", "superstar"})
_MIN_TITLE_SEARCH_TOKEN_LEN = 3

IMPORT_PUBLISHER_ALIASES: dict[str, str] = {
    "image comics": "image",
    "image": "image",
    "dc comics": "dc",
    "dc": "dc",
    "marvel comics": "marvel",
    "marvel": "marvel",
    "dark horse comics": "dark horse",
    "dark horse": "dark horse",
    "boom studios": "boom",
    "boom! studios": "boom",
    "boom": "boom",
    "idw publishing": "idw",
    "idw": "idw",
    "dynamite entertainment": "dynamite",
    "dynamite": "dynamite",
    "oni press": "oni",
    "oni": "oni",
    "mad cave studios": "mad cave",
    "mad cave": "mad cave",
    "titan comics": "titan",
    "titan": "titan",
    "vault comics": "vault",
    "vault": "vault",
    "dstlry media": "dstlry",
    "dstlry": "dstlry",
}

_PUBLISHER_SUFFIXES = (" comics", " publishing", " entertainment", " studios", " media")
_PLACEHOLDER_RELEASE_RAW = re.compile(
    r"2024,\s*2024-05,\s*or\s*2024-05-15",
    re.IGNORECASE,
)
_YEAR_ONLY = re.compile(r"^\d{4}$")


@dataclass
class CatalogCandidateRow:
    source: CatalogSource
    source_id: int
    publisher: str
    title: str
    issue_number: str
    release_date: date | None
    cover_name: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None


@dataclass
class ScoredCatalogCandidate:
    candidate: CatalogCandidateRow
    score: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class ImportCatalogResolutionResult:
    matched: bool
    possible_match: bool
    source: CatalogSource | None
    source_id: int | None
    score: int
    release_date: date | None
    publisher: str | None
    series_title: str | None
    issue_number: str | None
    cover_name: str | None
    variant_type: str | None
    cover_artist: str | None
    rejected_reason: str | None
    candidates_examined: int
    top_candidates: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def normalize_import_publisher_key(value: str | None) -> str:
    key = normalize_alias_lookup_key(value)
    if not key:
        return ""
    if key in IMPORT_PUBLISHER_ALIASES:
        return IMPORT_PUBLISHER_ALIASES[key]
    if key in STATIC_PUBLISHER_ALIAS_MAP:
        return STATIC_PUBLISHER_ALIAS_MAP[key].lower()
    stripped = key
    for suffix in _PUBLISHER_SUFFIXES:
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
            break
    if stripped in IMPORT_PUBLISHER_ALIASES:
        return IMPORT_PUBLISHER_ALIASES[stripped]
    return stripped


def normalize_import_title(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = re.sub(r"\(\s*\d{4}\s*\)", " ", text)
    text = re.sub(r"\bvol\.?\s*\d+\b", " ", text)
    text = re.sub(r"\bvolume\s+\d+\b", " ", text, flags=re.IGNORECASE)
    text = text.replace("&", " and ")
    text = re.sub(r"(?<=[a-z])\.(?=[a-z])", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _title_tokens(value: str | None) -> set[str]:
    normalized = normalize_import_title(value)
    if not normalized:
        return set()
    return {token for token in normalized.split() if len(token) > 1}


def _catalog_title_search_tokens(value: str | None) -> list[str]:
    """Distinct tokens for SQL title pre-filter (longest / most selective first)."""
    normalized = normalize_import_title(value)
    if not normalized:
        return []
    tokens = [
        token
        for token in normalized.split()
        if len(token) > 1 and token not in _TITLE_SEARCH_STOP
    ]
    if not tokens:
        tokens = [token for token in normalized.split() if len(token) > 1]
    deduped = sorted(set(tokens), key=len, reverse=True)
    selective = [token for token in deduped if len(token) >= _MIN_TITLE_SEARCH_TOKEN_LEN]
    if not selective:
        selective = deduped[:2]
    return selective[:4]


def _strong_title_issue_match(reasons: list[str]) -> bool:
    return "issue_number_exact" in reasons and any(
        reason in reasons
        for reason in (
            "title_normalized_exact",
            "title_overlap_strong",
            "title_overlap_good",
        )
    )


def _token_overlap_score(left: set[str], right: set[str]) -> tuple[int, str | None]:
    if not left or not right:
        return 0, None
    if left == right:
        return 30, "title_exact"
    intersection = left & right
    if not intersection:
        return 0, None
    union = left | right
    ratio = len(intersection) / len(union)
    if ratio >= 0.85:
        return 28, "title_overlap_strong"
    if ratio >= 0.65:
        return 22, "title_overlap_good"
    if ratio >= 0.45:
        return 12, "title_overlap_partial"
    return 0, None


def _publishers_compatible(left: str | None, right: str | None) -> bool:
    left_key = normalize_import_publisher_key(left)
    right_key = normalize_import_publisher_key(right)
    if not left_key or not right_key:
        return True
    return left_key == right_key or left_key in right_key or right_key in left_key


def _issue_number_key(value: str | None) -> str:
    raw = (value or "").strip().lower().lstrip("#").strip()
    if raw.isdigit():
        return str(int(raw))
    return raw


def issue_number_variants(value: str | None) -> set[str]:
    key = _issue_number_key(value)
    if not key:
        return set()
    variants = {key}
    if key.isdigit():
        variants.add(key.zfill(2))
        variants.add(key.zfill(3))
    return variants


def imported_release_date_is_placeholder(
    *,
    raw_release_date: str | None,
    parsed_release_date: date | None,
    parsed_release_year: int | None = None,
) -> bool:
    raw = (raw_release_date or "").strip()
    if not raw or raw.lower() == "unknown":
        return True
    if _PLACEHOLDER_RELEASE_RAW.search(raw):
        return True
    if _YEAR_ONLY.fullmatch(raw):
        return True
    if parsed_release_date is None:
        return parsed_release_year is not None
    return False


def score_catalog_candidate(
    *,
    input_publisher: str | None,
    input_title: str | None,
    input_issue_number: str | None,
    input_cover_name: str | None,
    input_cover_artist: str | None,
    candidate: CatalogCandidateRow,
) -> ScoredCatalogCandidate:
    score = 0
    reasons: list[str] = []
    in_issue = _issue_number_key(input_issue_number)
    cand_issue = _issue_number_key(candidate.issue_number)
    if in_issue and cand_issue and in_issue == cand_issue:
        score += 35
        reasons.append("issue_number_exact")

    in_title_norm = normalize_import_title(input_title)
    cand_title_norm = normalize_import_title(candidate.title)
    if in_title_norm and cand_title_norm and in_title_norm == cand_title_norm:
        score += 35
        reasons.append("title_normalized_exact")
    else:
        overlap, overlap_reason = _token_overlap_score(_title_tokens(input_title), _title_tokens(candidate.title))
        if overlap:
            score += overlap
            if overlap_reason:
                reasons.append(overlap_reason)

    if _publishers_compatible(input_publisher, candidate.publisher):
        if normalize_import_publisher_key(input_publisher) and normalize_import_publisher_key(candidate.publisher):
            score += 15
            reasons.append("publisher_alias_match")

    cover_tokens = _title_tokens(input_cover_name)
    cand_cover_tokens = _title_tokens(candidate.cover_name or candidate.variant_type)
    if cover_tokens and cand_cover_tokens and (cover_tokens & cand_cover_tokens):
        score += 10
        reasons.append("cover_token_overlap")

    artist_tokens = _title_tokens(input_cover_artist)
    cand_artist_tokens = _title_tokens(candidate.cover_artist)
    if artist_tokens and cand_artist_tokens and (artist_tokens & cand_artist_tokens):
        score += 8
        reasons.append("cover_artist_overlap")

    if candidate.release_date is not None:
        score += 5
        reasons.append("release_date_present")

    if candidate.source == "ReleaseIssue":
        score += 3
        reasons.append("release_issue_source_priority")

    return ScoredCatalogCandidate(candidate=candidate, score=score, reasons=reasons)


def _parse_release_date_from_item(item: dict[str, Any]) -> date | None:
    raw = item.get("parsed_release_date") or item.get("release_date")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            return None
    return None


def _gather_and_score_import_candidates(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None,
    title: str | None,
    issue_number: str | None,
    cover_name: str | None,
    cover_artist: str | None,
) -> list[ScoredCatalogCandidate]:
    candidates: list[CatalogCandidateRow] = []
    candidates.extend(
        _collect_release_issue_candidates(
            session,
            owner_user_id=owner_user_id,
            issue_number=issue_number,
            title=title,
        )
    )
    candidates.extend(
        _collect_external_catalog_candidates(session, issue_number=issue_number, title=title)
    )
    candidates = _dedupe_candidates(candidates)
    scored = [
        score_catalog_candidate(
            input_publisher=publisher,
            input_title=title,
            input_issue_number=issue_number,
            input_cover_name=cover_name,
            input_cover_artist=cover_artist,
            candidate=candidate,
        )
        for candidate in candidates
    ]
    top_score = max((row.score for row in scored), default=0)
    if top_score < STRONG_TITLE_ISSUE_MIN_SCORE:
        extra = _collect_external_catalog_series_candidates(session, title=title)
        if extra:
            candidates = _dedupe_candidates(candidates + extra)
            scored = [
                score_catalog_candidate(
                    input_publisher=publisher,
                    input_title=title,
                    input_issue_number=issue_number,
                    input_cover_name=cover_name,
                    input_cover_artist=cover_artist,
                    candidate=candidate,
                )
                for candidate in candidates
            ]
    return scored


def _title_prefilter_clause(tokens: list[str], *columns: Any) -> Any | None:
    if not tokens:
        return None
    selective = [token for token in tokens if len(token) >= _MIN_TITLE_SEARCH_TOKEN_LEN]
    if not selective:
        selective = tokens[:1]
    if len(selective) >= 2:
        required = selective[:2]
    else:
        required = selective[:1]
    per_token: list[Any] = []
    for token in required:
        pattern = f"%{token}%"
        per_token.append(or_(*[column.ilike(pattern) for column in columns]))  # type: ignore[attr-defined]
    return and_(*per_token)


def _collect_release_issue_candidates(
    session: Session,
    *,
    owner_user_id: int,
    issue_number: str | None,
    title: str | None = None,
) -> list[CatalogCandidateRow]:
    variants = issue_number_variants(issue_number)
    if not variants:
        return []
    search_tokens = _catalog_title_search_tokens(title)
    stmt = (
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.issue_number.in_(list(variants)))  # type: ignore[attr-defined]
    )
    title_clause = _title_prefilter_clause(
        search_tokens,
        ReleaseSeries.series_name,
        ReleaseIssue.title,
    )
    if title_clause is not None:
        stmt = stmt.where(title_clause)
    rows = session.exec(stmt.limit(CANDIDATE_LIMIT)).all()
    candidates: list[CatalogCandidateRow] = []
    for issue, series in rows:
        if issue.id is None:
            continue
        candidates.append(
            CatalogCandidateRow(
                source="ReleaseIssue",
                source_id=issue.id,
                publisher=series.publisher,
                title=series.series_name or issue.title,
                issue_number=issue.issue_number,
                release_date=issue.release_date,
            )
        )
    return candidates


def _external_row_to_candidate(row: ExternalCatalogIssue) -> CatalogCandidateRow | None:
    if row.id is None:
        return None
    display_title = row.series_name or row.title
    return CatalogCandidateRow(
        source="ExternalCatalogIssue",
        source_id=row.id,
        publisher=row.publisher,
        title=display_title,
        issue_number=row.issue_number or "",
        release_date=row.release_date,
    )


def _collect_external_catalog_series_candidates(
    session: Session,
    *,
    title: str | None,
) -> list[CatalogCandidateRow]:
    """LOCG series-title lookup when issue-number pools miss (P90-09E)."""
    search_tokens = _catalog_title_search_tokens(title)
    if not search_tokens:
        return []
    stmt = select(ExternalCatalogIssue)
    title_clause = _title_prefilter_clause(
        search_tokens,
        ExternalCatalogIssue.series_name,
        ExternalCatalogIssue.title,
        ExternalCatalogIssue.normalized_title_key,
    )
    if title_clause is not None:
        stmt = stmt.where(title_clause)
    rows = session.exec(stmt.limit(CANDIDATE_LIMIT)).all()
    candidates: list[CatalogCandidateRow] = []
    for row in rows:
        candidate = _external_row_to_candidate(row)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _dedupe_candidates(rows: list[CatalogCandidateRow]) -> list[CatalogCandidateRow]:
    seen: set[tuple[str, int]] = set()
    out: list[CatalogCandidateRow] = []
    for row in rows:
        key = (row.source, row.source_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _collect_external_catalog_candidates(
    session: Session,
    *,
    issue_number: str | None,
    title: str | None = None,
) -> list[CatalogCandidateRow]:
    variants = issue_number_variants(issue_number)
    if not variants:
        return []
    search_tokens = _catalog_title_search_tokens(title)
    stmt = select(ExternalCatalogIssue).where(
        ExternalCatalogIssue.issue_number.in_(list(variants))  # type: ignore[attr-defined]
    )
    title_clause = _title_prefilter_clause(
        search_tokens,
        ExternalCatalogIssue.series_name,
        ExternalCatalogIssue.title,
        ExternalCatalogIssue.normalized_title_key,
    )
    if title_clause is not None:
        stmt = stmt.where(title_clause)
    rows = session.exec(stmt.limit(CANDIDATE_LIMIT)).all()
    candidates: list[CatalogCandidateRow] = []
    for row in rows:
        candidate = _external_row_to_candidate(row)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _pick_resolution(scored: list[ScoredCatalogCandidate]) -> ImportCatalogResolutionResult:
    if not scored:
        return ImportCatalogResolutionResult(
            matched=False,
            possible_match=False,
            source=None,
            source_id=None,
            score=0,
            release_date=None,
            publisher=None,
            series_title=None,
            issue_number=None,
            cover_name=None,
            variant_type=None,
            cover_artist=None,
            rejected_reason="no_candidates",
            candidates_examined=0,
            top_candidates=[],
            diagnostics={},
        )

    ranked = sorted(scored, key=lambda row: (-row.score, row.candidate.source_id))
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    top_candidates = [
        {
            "source": row.candidate.source,
            "source_id": row.candidate.source_id,
            "score": row.score,
            "title": row.candidate.title,
            "publisher": row.candidate.publisher,
            "issue_number": row.candidate.issue_number,
            "release_date": row.candidate.release_date.isoformat() if row.candidate.release_date else None,
            "reasons": row.reasons,
        }
        for row in ranked[:3]
    ]

    matched = False
    possible_match = False
    rejected_reason: str | None = None

    if best.score >= ACCEPT_SCORE:
        matched = True
    elif best.score >= POSSIBLE_SCORE:
        if second is None or second.score < POSSIBLE_SCORE or (best.score - second.score) >= 15:
            matched = True
        else:
            possible_match = True
            rejected_reason = "ambiguous_candidates"
    else:
        rejected_reason = "below_threshold"

    if (
        not matched
        and best.score >= STRONG_TITLE_ISSUE_MIN_SCORE
        and _strong_title_issue_match(best.reasons)
    ):
        second_weak = second is None or not _strong_title_issue_match(second.reasons)
        if second_weak or best.score > second.score:
            matched = True
            possible_match = False
            rejected_reason = None

    winner = best if matched else None
    return ImportCatalogResolutionResult(
        matched=matched,
        possible_match=possible_match and not matched,
        source=winner.candidate.source if winner else None,
        source_id=winner.candidate.source_id if winner else None,
        score=best.score,
        release_date=winner.candidate.release_date if winner else None,
        publisher=winner.candidate.publisher if winner else None,
        series_title=winner.candidate.title if winner else None,
        issue_number=winner.candidate.issue_number if winner else None,
        cover_name=winner.candidate.cover_name if winner else None,
        variant_type=winner.candidate.variant_type if winner else None,
        cover_artist=winner.candidate.cover_artist if winner else None,
        rejected_reason=None if matched else rejected_reason,
        candidates_examined=len(scored),
        top_candidates=top_candidates,
        diagnostics={},
    )


def resolve_import_catalog_match(
    session: Session | None,
    *,
    owner_user_id: int | None,
    item: dict[str, Any],
) -> ImportCatalogResolutionResult:
    publisher = item.get("publisher") or item.get("canonical_publisher")
    title = item.get("title") or item.get("canonical_title")
    issue_number = item.get("issue_number") or item.get("canonical_issue_number")
    cover_name = item.get("cover_name")
    cover_artist = item.get("cover_artist")

    diagnostics = {
        "normalized_input_title": normalize_import_title(title),
        "normalized_input_publisher": normalize_import_publisher_key(publisher),
        "input_issue_number": _issue_number_key(issue_number),
    }

    if session is None or owner_user_id is None or not issue_number_variants(issue_number):
        result = ImportCatalogResolutionResult(
            matched=False,
            possible_match=False,
            source=None,
            source_id=None,
            score=0,
            release_date=None,
            publisher=None,
            series_title=None,
            issue_number=None,
            cover_name=None,
            variant_type=None,
            cover_artist=None,
            rejected_reason="missing_session_or_issue_number",
            candidates_examined=0,
            top_candidates=[],
            diagnostics=diagnostics,
        )
        return result

    scored = _gather_and_score_import_candidates(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        title=title,
        issue_number=issue_number,
        cover_name=cover_name,
        cover_artist=cover_artist,
    )
    result = _pick_resolution(scored)
    hydrate_diag: dict[str, Any] = {}
    should_try_locg_hydrate = (
        not result.matched
        and result.score < ACCEPT_SCORE
        and bool(normalize_import_title(title))
        and bool(issue_number_variants(issue_number))
    )
    if should_try_locg_hydrate:
        from app.services.import_locg_hydrate_service import (
            hydrate_import_item_from_locg_calendar,
            hydrate_result_to_diagnostics,
            import_locg_hydrate_enabled,
        )

        if import_locg_hydrate_enabled():
            parsed_release = _parse_release_date_from_item(item)
            try:
                hydrate_result = hydrate_import_item_from_locg_calendar(
                    session,
                    title=title,
                    issue_number=issue_number,
                    parsed_release_date=parsed_release,
                )
                hydrate_diag = hydrate_result_to_diagnostics(hydrate_result)
                if hydrate_result.hydrated:
                    scored = _gather_and_score_import_candidates(
                        session,
                        owner_user_id=owner_user_id,
                        publisher=publisher,
                        title=title,
                        issue_number=issue_number,
                        cover_name=cover_name,
                        cover_artist=cover_artist,
                    )
                    result = _pick_resolution(scored)
            except Exception:
                logger.warning(
                    "import_locg_hydrate_resolve_guard title=%r issue=%r",
                    title,
                    issue_number,
                    exc_info=True,
                )
                hydrate_diag = {
                    "locg_hydrate_attempted": True,
                    "locg_hydrated": False,
                    "locg_hydrate_no_match_reason": "resolve_guard",
                }
    result.diagnostics = {
        **diagnostics,
        **hydrate_diag,
        "locg_hydrated": hydrate_diag.get("locg_hydrated", False),
        "candidates_examined": result.candidates_examined,
        "matched": result.matched,
        "score": result.score,
        "matched_source": result.source,
        "matched_release_date": result.release_date.isoformat() if result.release_date else None,
        "rejected_reason": result.rejected_reason,
        "top_candidates": result.top_candidates,
    }
    return result


def catalog_match_fields_for_item(
    resolution: ImportCatalogResolutionResult,
    *,
    include_debug: bool = False,
) -> dict[str, Any]:
    locg_hydrated = bool(resolution.diagnostics.get("locg_hydrated"))
    if resolution.matched and locg_hydrated:
        source_text = "Verified release date from LOCG (live hydrate)"
    elif resolution.matched:
        source_text = "Verified release date from catalog"
    elif resolution.possible_match:
        source_text = "Possible catalog match needs review"
    else:
        source_text = "No verified release date"

    payload: dict[str, Any] = {
        "catalog_match_matched": resolution.matched,
        "catalog_match_possible": resolution.possible_match,
        "catalog_match_source": resolution.source,
        "catalog_match_source_id": resolution.source_id,
        "catalog_match_score": resolution.score,
        "catalog_match_title": resolution.series_title,
        "catalog_match_publisher": resolution.publisher,
        "catalog_match_issue_number": resolution.issue_number,
        "catalog_match_release_date": resolution.release_date,
        "catalog_match_hydrated": locg_hydrated,
        "catalog_match_catalog_source": "LOCG_LIVE_HYDRATED" if locg_hydrated and resolution.matched else None,
        "catalog_match_diagnostics": {
            "rejected_reason": resolution.rejected_reason,
            "candidates_examined": resolution.candidates_examined,
            "top_candidates": resolution.top_candidates,
            **{
                key: value
                for key, value in resolution.diagnostics.items()
                if key.startswith("locg_hydrate")
            },
        },
        "catalog_release_source_text": source_text,
    }
    if include_debug:
        payload["catalog_resolution_debug"] = resolution.diagnostics
    return payload
