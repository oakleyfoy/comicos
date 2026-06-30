"""P106.1 — GCD issue recovery when the scanned barcode has no row in gcd_issue.barcode."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue
from app.services.barcode_scan_consensus_service import normalize_scan_preserving_supplement
from app.services.barcode_validation_service import (
    barcode_encoded_issue_number,
    effective_publisher_for_barcode,
    validate_barcode_catalog_match,
)
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    series_names_compatible,
)
from app.services.p102_gcd_modern_acquisition_service import YEAR_EXPR, _REPRINT_DIGEST
from app.services.p1035_gcd_identity_backfill_service import _series_norm_aliases
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id, parse_key_date
from app.services.p106_barcode_gap_resolver_service import (
    P106_STATUS_AUTO_ATTACHED,
    P106_STATUS_AUTO_IMPORTED,
    P106_STATUS_REVIEW_REQUIRED,
    P106_STATUS_UNRESOLVED,
    resolve_catalog_issue_for_gcd_barcode,
)
from app.services.intake_p106_1_execution_trace_service import (
    gated_search_catalog_fingerprint_hits_for_crop_path,
    log_p106_1_before_fingerprint,
)
from app.services.recognition.ocr_matcher import extract_ocr_signal

logger = logging.getLogger(__name__)

P106_1_RECOVERY_STAGE = "p106_1_non_barcode"
P106_1_IMPORT_REASON = "gcd_non_barcode_recovery"
_MIN_UNIQUE_SCORE = 10
_SECOND_BEST_GAP = 3
_FINGERPRINT_BOOST = 4
_FINGERPRINT_MIN_CONFIDENCE = 0.82
FINGERPRINT_CATALOG_MATCH_SOURCE = "catalog_image_fingerprint"
FINGERPRINT_CONFLICT_WITH_POOL_REASON = "fingerprint_candidate_conflicts_with_barcode_issue_or_publisher"
_GENERIC_SERIES_TOKENS = frozenset(
    {
        "marvel",
        "comic",
        "comics",
        "issue",
        "facsimile",
        "variant",
        "cover",
        "edition",
    }
)
_STRONG_SINGLE_SERIES_TOKENS = frozenset(
    {
        "spider",
        "spiderman",
        "batman",
        "superman",
        "wolverine",
        "hulk",
        "thor",
        "daredevil",
    }
)
SeriesMatchState = str  # matched | mismatched | unavailable


@dataclass(frozen=True)
class FingerprintRecoveryCandidate:
    catalog_issue_id: int
    gcd_issue_id: int | None
    confidence: float
    match_source: str = FINGERPRINT_CATALOG_MATCH_SOURCE


def has_reliable_series_hint(series_hint: str | None) -> bool:
    """True when the series/title hint is specific enough to filter GCD candidates."""
    if series_hint is None or not str(series_hint).strip():
        return False
    norm = normalize_series_name(str(series_hint).strip())
    if len(norm) < 4:
        return False
    if norm.isdigit():
        return False
    tokens = [t for t in norm.split() if t]
    if not tokens:
        return False
    if all(t in _GENERIC_SERIES_TOKENS for t in tokens):
        return False
    if len(tokens) == 1:
        token = tokens[0]
        if token in _GENERIC_SERIES_TOKENS:
            return False
        if len(token) < 5 and token not in _STRONG_SINGLE_SERIES_TOKENS:
            return False
    return True


@dataclass
class IntakeGcdRecoveryHints:
    publisher: str | None
    series: str | None
    issue_number: str | None
    year: int | None
    ocr_title: str | None
    ocr_issue_number: str | None
    ocr_publisher: str | None
    facsimile_or_reprint: bool = False
    series_norm_aliases: list[str] = field(default_factory=list)
    ocr_confidence: float = 0.0
    raw_ocr_text_excerpt: str | None = None
    ocr_engine_available: bool = True
    ocr_error: str | None = None
    fingerprint_candidates: list[FingerprintRecoveryCandidate] = field(default_factory=list)
    fingerprint_candidate_catalog_issue_id: int | None = None
    fingerprint_candidate_gcd_issue_id: int | None = None
    fingerprint_confidence: float | None = None
    fingerprint_match_source: str | None = None
    fingerprint_image_region: str = "unknown"
    fingerprint_region_safe: bool = True
    fingerprint_suppressed_reason: str | None = None


def _qualified_fingerprint_candidates(
    candidates: list[FingerprintRecoveryCandidate],
) -> list[FingerprintRecoveryCandidate]:
    return [c for c in candidates if float(c.confidence) >= _FINGERPRINT_MIN_CONFIDENCE]


def _fingerprint_candidate_payload(candidate: FingerprintRecoveryCandidate) -> dict[str, Any]:
    return {
        "catalog_issue_id": int(candidate.catalog_issue_id),
        "gcd_issue_id": int(candidate.gcd_issue_id) if candidate.gcd_issue_id is not None else None,
        "confidence": float(candidate.confidence),
        "match_source": candidate.match_source,
    }


def _resolve_fingerprint_recovery_candidates(
    session: Session,
    *,
    image_path: Path | None,
    intake_item_id: int | None = None,
    fingerprint_region_safe: bool = True,
    fingerprint_image_region: str = "unknown",
    full_cover_followup_required: bool = False,
) -> list[FingerprintRecoveryCandidate]:
    if intake_item_id is not None:
        log_p106_1_before_fingerprint(
            intake_item_id=int(intake_item_id),
            fingerprint_region_safe=fingerprint_region_safe,
            fingerprint_image_region=fingerprint_image_region,
            full_cover_followup_required=full_cover_followup_required,
        )
    if not fingerprint_region_safe or full_cover_followup_required:
        return []
    if image_path is None or not image_path.is_file():
        return []
    logger.info(
        "p106_1.fingerprint_search crop_path=%s exists=%s",
        image_path,
        image_path.is_file(),
    )
    hits = gated_search_catalog_fingerprint_hits_for_crop_path(session, crop_path=image_path, limit=5)
    out: list[FingerprintRecoveryCandidate] = []
    for hit in hits:
        catalog_issue_id = int(hit.issue_id)
        issue = session.get(CatalogIssue, catalog_issue_id)
        linked = extract_gcd_issue_id(issue.external_source_ids) if issue else None
        out.append(
            FingerprintRecoveryCandidate(
                catalog_issue_id=catalog_issue_id,
                gcd_issue_id=int(linked) if linked is not None else None,
                confidence=float(hit.confidence),
                match_source=FINGERPRINT_CATALOG_MATCH_SOURCE,
            )
        )
    return out


def _primary_fingerprint_fields(
    candidates: list[FingerprintRecoveryCandidate],
) -> tuple[int | None, int | None, float | None, str | None]:
    qualified = _qualified_fingerprint_candidates(candidates)
    if len(qualified) != 1:
        return None, None, None, None
    fp = qualified[0]
    return (
        int(fp.catalog_issue_id),
        int(fp.gcd_issue_id) if fp.gcd_issue_id is not None else None,
        float(fp.confidence),
        fp.match_source,
    )


def _build_fingerprint_instrumentation(
    hints: IntakeGcdRecoveryHints,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qualified = _qualified_fingerprint_candidates(hints.fingerprint_candidates)
    payload: dict[str, Any] = {
        "fingerprint_candidate_count": len(qualified),
        "fingerprint_candidates": [
            _fingerprint_candidate_payload(c) for c in hints.fingerprint_candidates[:5]
        ],
        "fingerprint_narrowed_candidate_count": 0,
        "fingerprint_candidate_used": False,
        "fingerprint_candidate_outside_pool": False,
        "fingerprint_conflict_reason": None,
    }
    if hints.fingerprint_candidate_gcd_issue_id is not None:
        payload["fingerprint_candidate_gcd_issue_id"] = int(hints.fingerprint_candidate_gcd_issue_id)
    if extra:
        payload.update(extra)
    return payload


def _resolve_target_gcd_for_fingerprint(
    session: Session,
    candidate: FingerprintRecoveryCandidate,
) -> int | None:
    if candidate.gcd_issue_id is not None:
        return int(candidate.gcd_issue_id)
    issue = session.get(CatalogIssue, int(candidate.catalog_issue_id))
    if issue is None:
        return None
    linked = extract_gcd_issue_id(issue.external_source_ids)
    return int(linked) if linked is not None else None


def _gcd_barcode_column_empty(raw: Any) -> bool:
    if raw is None:
        return True
    return not str(raw).strip()


def _edition_text_blob(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("title") or ""),
        str(row.get("notes") or ""),
        str(row.get("series") or ""),
    ]
    return " ".join(parts).lower()


def _row_is_reprint_or_facsimile(row: dict[str, Any]) -> bool:
    return bool(_REPRINT_DIGEST.search(_edition_text_blob(row)))


def _parse_year_hint(raw: Any) -> int | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    if len(text) >= 4 and text[:4].isdigit():
        y = int(text[:4])
        if 1800 <= y <= 2100:
            return y
    return None


def gather_intake_gcd_recovery_hints(
    session: Session,
    *,
    item: Any,
    normalized_barcode: str,
    image_path: Path | None,
    image_bytes: bytes | None,
    p105: Any,
    fingerprint_region_safe: bool | None = None,
    fingerprint_image_region: str | None = None,
    full_cover_followup_required: bool = False,
) -> IntakeGcdRecoveryHints:
    publisher = (item.matched_publisher or "").strip() or None
    if not publisher:
        publisher = effective_publisher_for_barcode(normalized_barcode, None)

    issue_number = (item.matched_issue_number or "").strip() or None
    encoded_issue: str | None = None
    encoded = barcode_encoded_issue_number(normalized_barcode)
    if encoded is not None:
        encoded_issue = str(encoded)

    year = _parse_year_hint(item.matched_year)
    series = (item.matched_series or "").strip() or None

    ocr_title: str | None = None
    ocr_issue: str | None = None
    ocr_publisher: str | None = None
    facsimile = False
    ocr_confidence = 0.0
    raw_ocr_excerpt: str | None = None
    ocr_engine_available = True
    ocr_error: str | None = None

    if image_bytes:
        ocr = extract_ocr_signal(image_bytes, source_name=f"intake-{getattr(item, 'id', 0)}")
        ocr_confidence = float(ocr.confidence or 0.0)
        ocr_engine_available = bool(getattr(ocr, "ocr_engine_available", True))
        ocr_error = getattr(ocr, "ocr_error", None)
        raw_text = (ocr.raw_text or "").strip()
        if raw_text:
            raw_ocr_excerpt = raw_text[:500]
        blob = raw_text.lower()
        facsimile = bool(_REPRINT_DIGEST.search(blob))
        ocr_title = (ocr.title or "").strip() or None
        ocr_issue = (ocr.issue_number or "").strip() or None
        ocr_publisher = (ocr.publisher or "").strip() or None

    if p105 is not None and getattr(p105, "fingerprint_confirmed", False):
        facsimile = facsimile or bool(
            _REPRINT_DIGEST.search(str(getattr(p105, "correction_reason", "") or "").lower())
        )

    if not publisher and ocr_publisher:
        publisher = ocr_publisher

    if (
        ocr_issue
        and issue_number
        and encoded_issue
        and ocr_issue != encoded_issue
        and ocr_confidence >= 0.5
    ):
        issue_number = ocr_issue
    elif not issue_number and encoded_issue:
        issue_number = encoded_issue

    if not series and ocr_title:
        if has_reliable_series_hint(ocr_title) or ocr_confidence >= 0.35:
            series = ocr_title

    validation = validate_barcode_catalog_match(
        normalized_barcode,
        publisher=publisher,
        issue_number=issue_number,
        year=str(year) if year is not None else (item.matched_year or None),
    )
    if validation.status == "exact_match" and not publisher:
        publisher = effective_publisher_for_barcode(normalized_barcode, None)

    series_norm = normalize_series_name(series) if series else ""
    aliases = _series_norm_aliases(series_norm) if series_norm and has_reliable_series_hint(series) else []

    from app.services.intake_fingerprint_image_region_service import assess_fingerprint_image_region

    region = assess_fingerprint_image_region(image_path, image_bytes=image_bytes)
    region_safe = region.fingerprint_region_safe if fingerprint_region_safe is None else fingerprint_region_safe
    region_kind = fingerprint_image_region or region.fingerprint_image_region
    intake_id = int(getattr(item, "id", 0) or 0)
    fingerprint_candidates: list[FingerprintRecoveryCandidate] = []
    if region_safe and not full_cover_followup_required:
        fingerprint_candidates = _resolve_fingerprint_recovery_candidates(
            session,
            image_path=image_path,
            intake_item_id=intake_id or None,
            fingerprint_region_safe=region_safe,
            fingerprint_image_region=region_kind,
            full_cover_followup_required=full_cover_followup_required,
        )
    elif intake_id:
        log_p106_1_before_fingerprint(
            intake_item_id=intake_id,
            fingerprint_region_safe=region_safe,
            fingerprint_image_region=region_kind,
            full_cover_followup_required=full_cover_followup_required,
        )
    fp_catalog_id, fp_gcd_id, fp_conf, fp_source = _primary_fingerprint_fields(fingerprint_candidates)

    return IntakeGcdRecoveryHints(
        publisher=publisher,
        series=series,
        issue_number=issue_number,
        year=year,
        ocr_title=ocr_title,
        ocr_issue_number=ocr_issue,
        ocr_publisher=ocr_publisher,
        facsimile_or_reprint=facsimile,
        series_norm_aliases=aliases,
        ocr_confidence=ocr_confidence,
        raw_ocr_text_excerpt=raw_ocr_excerpt,
        ocr_engine_available=ocr_engine_available,
        ocr_error=ocr_error,
        fingerprint_candidates=fingerprint_candidates,
        fingerprint_candidate_catalog_issue_id=fp_catalog_id,
        fingerprint_candidate_gcd_issue_id=fp_gcd_id,
        fingerprint_confidence=fp_conf,
        fingerprint_match_source=fp_source,
        fingerprint_image_region=region_kind,
        fingerprint_region_safe=region_safe,
        fingerprint_suppressed_reason=region.fingerprint_suppressed_reason,
    )


def build_p106_1_intake_hint_snapshot(
    session: Session,
    *,
    item: Any,
    barcode: str,
    image_path: Path | None,
    image_bytes: bytes | None,
    p105: Any,
    full_cover_followup_required: bool = False,
    fingerprint_region_safe: bool | None = None,
    fingerprint_image_region: str | None = None,
) -> tuple[IntakeGcdRecoveryHints, dict[str, Any]]:
    """Gather cover/barcode hints once for logging and P106.1 enrichment."""
    hints = gather_intake_gcd_recovery_hints(
        session,
        item=item,
        normalized_barcode=barcode,
        image_path=image_path,
        image_bytes=image_bytes,
        p105=p105,
        fingerprint_region_safe=fingerprint_region_safe,
        fingerprint_image_region=fingerprint_image_region,
        full_cover_followup_required=full_cover_followup_required,
    )
    fp_count = len(_qualified_fingerprint_candidates(hints.fingerprint_candidates))
    snapshot = {
        "barcode": barcode,
        "intake_item_id": getattr(item, "id", None),
        "image_path": str(image_path) if image_path else None,
        "image_bytes_present": bool(image_bytes),
        "ocr_title": hints.ocr_title,
        "ocr_issue_number": hints.ocr_issue_number,
        "ocr_publisher": hints.ocr_publisher,
        "ocr_confidence": hints.ocr_confidence,
        "inferred_series_hint": hints.series,
        "series_hint_reliable": has_reliable_series_hint(hints.series),
        "facsimile_or_reprint": hints.facsimile_or_reprint,
        "fingerprint_candidate_count": fp_count,
        "fingerprint_candidate_catalog_issue_id": hints.fingerprint_candidate_catalog_issue_id,
        "fingerprint_candidate_gcd_issue_id": hints.fingerprint_candidate_gcd_issue_id,
        "fingerprint_confidence": hints.fingerprint_confidence,
        "fingerprint_match_source": hints.fingerprint_match_source,
        "raw_ocr_text_excerpt": hints.raw_ocr_text_excerpt,
        "ocr_engine_available": hints.ocr_engine_available,
        "ocr_error": hints.ocr_error,
        "recovery_hints_issue": hints.issue_number,
        "recovery_hints_publisher": hints.publisher,
        "recovery_hints_year": hints.year,
        "p105_fingerprint_confirmed": bool(getattr(p105, "fingerprint_confirmed", False)) if p105 else False,
    }
    return hints, snapshot


def _issue_number_sql_variants(issue_number: str | None) -> list[str]:
    raw = str(issue_number or "").strip().lstrip("#")
    if not raw:
        return []
    norms = {raw, normalize_issue_number(raw)}
    if raw.isdigit():
        norms.add(f"{int(raw)}")
        norms.add(f"{int(raw)}.00")
    return [v for v in norms if v]


def _query_gcd_empty_barcode_candidates(gcd_path: Path, *, issue_number: str | None) -> list[dict[str, Any]]:
    if not gcd_path.is_file():
        return []
    issue_norm = normalize_issue_number(str(issue_number or ""))
    variants = _issue_number_sql_variants(issue_number)
    if not issue_norm or not variants:
        return []
    placeholders = ", ".join("?" * len(variants))
    sql = f"""
            SELECT i.id AS gcd_issue_id,
                   p.name AS publisher,
                   s.name AS series,
                   i.number AS issue_number,
                   i.barcode AS barcode_raw,
                   i.key_date AS key_date,
                   s.year_began AS year_began,
                   i.title AS title,
                   i.notes AS notes,
                   {YEAR_EXPR} AS pub_year
            FROM gcd_issue i
            JOIN gcd_series s ON s.id = i.series_id
            LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
            WHERE (i.barcode IS NULL OR length(trim(COALESCE(i.barcode, ''))) = 0)
              AND trim(i.number) IN ({placeholders})
            """
    conn = sqlite3.connect(gcd_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, tuple(variants)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        if not _gcd_barcode_column_empty(row["barcode_raw"]):
            continue
        if normalize_issue_number(str(row["issue_number"] or "")) != issue_norm:
            continue
        out.append(
            {
                "gcd_issue_id": int(row["gcd_issue_id"]),
                "publisher": row["publisher"],
                "series": row["series"],
                "issue_number": row["issue_number"],
                "barcode_raw": row["barcode_raw"],
                "key_date": row["key_date"],
                "year_began": row["year_began"],
                "title": row["title"],
                "notes": row["notes"],
                "pub_year": row["pub_year"],
            }
        )
    return out


def _publisher_matches(hint: str | None, candidate: str | None) -> bool:
    if not hint or not candidate:
        return False
    a = normalize_series_name(hint)
    b = normalize_series_name(candidate)
    if a == b:
        return True
    return series_names_compatible(a, b)


def _series_match_evaluation(
    hints: IntakeGcdRecoveryHints,
    row: dict[str, Any],
) -> tuple[SeriesMatchState, float, dict[str, Any]]:
    raw_series_hint = hints.series
    normalized_series_hint = normalize_series_name(raw_series_hint) if raw_series_hint else ""
    candidate_series_normalized = normalize_series_name(str(row.get("series") or ""))
    series_hint_reliable = has_reliable_series_hint(raw_series_hint)
    meta = {
        "raw_series_hint": raw_series_hint,
        "normalized_series_hint": normalized_series_hint or None,
        "series_hint_reliable": series_hint_reliable,
        "candidate_series_normalized": candidate_series_normalized or None,
        "series_similarity": 0.0,
        "series_match_state": "unavailable",
    }
    if not series_hint_reliable:
        return "unavailable", 0.0, meta
    aliases = hints.series_norm_aliases or ([normalized_series_hint] if normalized_series_hint else [])
    for alias in aliases:
        if not alias:
            continue
        if candidate_series_normalized == alias or series_names_compatible(candidate_series_normalized, alias):
            meta["series_similarity"] = 1.0
            meta["series_match_state"] = "matched"
            return "matched", 1.0, meta
    meta["series_match_state"] = "mismatched"
    return "mismatched", 0.0, meta


def _gcd_issue_ids_from_prior_diagnosis(prior_diagnosis: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for match in prior_diagnosis.get("gcd_matches") or []:
        if isinstance(match, dict) and match.get("gcd_issue_id") is not None:
            ids.add(int(match["gcd_issue_id"]))
    for hit in prior_diagnosis.get("gcd_exact_hits") or []:
        if isinstance(hit, dict) and hit.get("gcd_issue_id") is not None:
            ids.add(int(hit["gcd_issue_id"]))
    for hit in prior_diagnosis.get("gcd_prefix_hits") or []:
        if isinstance(hit, dict) and hit.get("gcd_issue_id") is not None:
            ids.add(int(hit["gcd_issue_id"]))
    return ids


def _fingerprint_gcd_issue_ids(
    session: Session,
    *,
    image_path: Path | None,
    hints: IntakeGcdRecoveryHints | None = None,
) -> set[int]:
    if hints is not None and hints.fingerprint_candidates:
        return {
            int(c.gcd_issue_id)
            for c in _qualified_fingerprint_candidates(hints.fingerprint_candidates)
            if c.gcd_issue_id is not None
        }
    if image_path is None or not image_path.is_file():
        return set()
    out: set[int] = set()
    for candidate in _resolve_fingerprint_recovery_candidates(session, image_path=image_path):
        if candidate.gcd_issue_id is not None:
            out.add(int(candidate.gcd_issue_id))
    return out


def _has_secondary_scoring_discriminator(
    session: Session,
    *,
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
    prior_diagnosis: dict[str, Any],
    publisher_filtered: list[dict[str, Any]],
) -> bool:
    if has_reliable_series_hint(hints.series):
        return True
    if hints.facsimile_or_reprint:
        return True
    if has_reliable_series_hint(hints.ocr_title):
        return True
    if _fingerprint_gcd_issue_ids(session, image_path=image_path, hints=hints):
        return True
    if len(_qualified_fingerprint_candidates(hints.fingerprint_candidates)) == 1:
        return True
    pool_ids = {int(c["gcd_issue_id"]) for c in publisher_filtered}
    if _gcd_issue_ids_from_prior_diagnosis(prior_diagnosis) & pool_ids:
        return True
    return False


def _try_narrow_pool_by_single_fingerprint(
    session: Session,
    *,
    hints: IntakeGcdRecoveryHints,
    publisher_filtered: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]] | None, str | None, dict[str, Any]]:
    """When exactly one qualified fingerprint exists, narrow to its GCD row or report pool conflict."""
    fp_meta = _build_fingerprint_instrumentation(hints)
    qualified = _qualified_fingerprint_candidates(hints.fingerprint_candidates)
    if len(qualified) != 1:
        if len(qualified) > 1:
            fp_meta["fingerprint_conflict_reason"] = "multiple_fingerprint_candidates"
        return None, None, fp_meta

    target_gcd = _resolve_target_gcd_for_fingerprint(session, qualified[0])
    if target_gcd is None:
        return None, None, fp_meta

    fp_meta["fingerprint_candidate_gcd_issue_id"] = int(target_gcd)
    pool_match = [c for c in publisher_filtered if int(c["gcd_issue_id"]) == int(target_gcd)]
    if not pool_match:
        fp_meta.update(
            {
                "fingerprint_candidate_outside_pool": True,
                "fingerprint_conflict_reason": FINGERPRINT_CONFLICT_WITH_POOL_REASON,
            }
        )
        return [], FINGERPRINT_CONFLICT_WITH_POOL_REASON, fp_meta
    if len(pool_match) == 1:
        fp_meta.update(
            {
                "fingerprint_candidate_used": True,
                "fingerprint_narrowed_candidate_count": 1,
            }
        )
        return pool_match, None, fp_meta
    return None, None, fp_meta


def _prepare_scoring_candidates(
    session: Session,
    *,
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
    prior_diagnosis: dict[str, Any],
    publisher_filtered: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    """Narrow who enters scoring; return block reason when pool is too broad."""
    fp_meta = _build_fingerprint_instrumentation(hints)
    if not publisher_filtered:
        return [], None, fp_meta

    narrowed_by_fp, fp_block, fp_meta = _try_narrow_pool_by_single_fingerprint(
        session,
        hints=hints,
        publisher_filtered=publisher_filtered,
    )
    if fp_block:
        return narrowed_by_fp or [], fp_block, fp_meta
    if narrowed_by_fp is not None:
        return narrowed_by_fp, None, fp_meta

    if len(publisher_filtered) == 1:
        return publisher_filtered, None, fp_meta

    if has_reliable_series_hint(hints.series):
        matched = [
            c
            for c in publisher_filtered
            if _series_match_evaluation(hints, c)[0] == "matched"
        ]
        return matched, None, fp_meta

    if not _has_secondary_scoring_discriminator(
        session,
        hints=hints,
        image_path=image_path,
        prior_diagnosis=prior_diagnosis,
        publisher_filtered=publisher_filtered,
    ):
        return [], "insufficient_series_or_title_hint", fp_meta

    narrowed = list(publisher_filtered)
    if hints.facsimile_or_reprint:
        facsimile_rows = [c for c in narrowed if _row_is_reprint_or_facsimile(c)]
        if facsimile_rows:
            narrowed = facsimile_rows
    if has_reliable_series_hint(hints.ocr_title):
        title_rows = [c for c in narrowed if _title_overlap_score(hints, c) > 0]
        if title_rows:
            narrowed = title_rows
    prior_ids = _gcd_issue_ids_from_prior_diagnosis(prior_diagnosis)
    if prior_ids:
        prior_rows = [c for c in narrowed if int(c["gcd_issue_id"]) in prior_ids]
        if prior_rows:
            narrowed = prior_rows
    fp_ids = _fingerprint_gcd_issue_ids(session, image_path=image_path, hints=hints)
    if fp_ids:
        fp_rows = [c for c in narrowed if int(c["gcd_issue_id"]) in fp_ids]
        if fp_rows:
            narrowed = fp_rows

    if len(narrowed) > 1:
        return [], "insufficient_series_or_title_hint", fp_meta
    if len(narrowed) == 1 and fp_ids:
        fp_meta.update(
            {
                "fingerprint_candidate_used": True,
                "fingerprint_narrowed_candidate_count": 1,
            }
        )
    return narrowed, None, fp_meta


def _series_matches(hints: IntakeGcdRecoveryHints, row: dict[str, Any]) -> bool:
    state, _, _ = _series_match_evaluation(hints, row)
    return state == "matched"


def _year_matches(hints: IntakeGcdRecoveryHints, row: dict[str, Any]) -> bool:
    if hints.year is None:
        return True
    row_year = row.get("pub_year")
    if row_year is None:
        _, parsed, _ = parse_key_date(str(row.get("key_date") or ""), row.get("year_began"))
        row_year = parsed
    if row_year is None:
        return False
    return abs(int(row_year) - int(hints.year)) <= 1


def _title_overlap_score(hints: IntakeGcdRecoveryHints, row: dict[str, Any]) -> float:
    if not hints.ocr_title:
        return 0.0
    blob = _edition_text_blob(row)
    tokens = [t for t in re.split(r"\W+", hints.ocr_title.lower()) if len(t) >= 4]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in blob)
    return min(3.0, float(hits) * 1.5)


def _fingerprint_pts_for_row(
    session: Session,
    hints: IntakeGcdRecoveryHints,
    *,
    gcd_issue_id: int,
) -> float:
    for candidate in _qualified_fingerprint_candidates(hints.fingerprint_candidates):
        target = candidate.gcd_issue_id
        if target is None:
            target = _resolve_target_gcd_for_fingerprint(session, candidate)
        if target is not None and int(target) == int(gcd_issue_id):
            return float(_FINGERPRINT_BOOST)
    return 0.0


def _fingerprint_gcd_boost(
    session: Session,
    *,
    image_path: Path | None,
    gcd_issue_id: int,
    hints: IntakeGcdRecoveryHints | None = None,
) -> float:
    if hints is not None and hints.fingerprint_candidates:
        return _fingerprint_pts_for_row(session, hints, gcd_issue_id=gcd_issue_id)
    if image_path is None or not image_path.is_file():
        return 0.0
    hits = gated_search_catalog_fingerprint_hits_for_crop_path(session, crop_path=image_path, limit=5)
    for hit in hits:
        if hit.confidence < _FINGERPRINT_MIN_CONFIDENCE:
            continue
        issue = session.get(CatalogIssue, int(hit.issue_id))
        if issue is None:
            continue
        linked = extract_gcd_issue_id(issue.external_source_ids)
        if linked is not None and int(linked) == int(gcd_issue_id):
            return float(_FINGERPRINT_BOOST)
    return 0.0


def _score_candidate_breakdown(
    session: Session,
    *,
    row: dict[str, Any],
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
) -> tuple[int, dict[str, Any]]:
    """Score components for instrumentation (same rules as _score_candidate)."""
    breakdown: dict[str, Any] = {
        "gcd_issue_id": int(row.get("gcd_issue_id") or 0),
        "publisher": row.get("publisher"),
        "series": row.get("series"),
        "issue_number": row.get("issue_number"),
        "title": row.get("title"),
        "pub_year": row.get("pub_year"),
        "title_pts": 0.0,
        "issue_pts": 0,
        "publisher_pts": 0,
        "series_pts": 0,
        "year_pts": 0,
        "facsimile_pts": 0,
        "fingerprint_pts": 0.0,
        "total": 0,
        "series_match_failed": None,
        "raw_series_hint": hints.series,
        "normalized_series_hint": normalize_series_name(hints.series) if hints.series else None,
        "series_hint_reliable": has_reliable_series_hint(hints.series),
        "candidate_series_normalized": normalize_series_name(str(row.get("series") or "")) or None,
        "series_similarity": 0.0,
        "series_match_state": "unavailable",
    }
    score = 0
    if hints.issue_number:
        if normalize_issue_number(str(row.get("issue_number") or "")) == normalize_issue_number(hints.issue_number):
            breakdown["issue_pts"] = 4
            score += 4
    if _publisher_matches(hints.publisher, str(row.get("publisher") or "")):
        breakdown["publisher_pts"] = 3
        score += 3
    series_state, series_sim, series_meta = _series_match_evaluation(hints, row)
    breakdown.update(series_meta)
    if series_state == "mismatched":
        breakdown["series_match_failed"] = True
        breakdown["total"] = 0
        return 0, breakdown
    if series_state == "matched":
        breakdown["series_pts"] = 2
        score += 2
    if _year_matches(hints, row):
        breakdown["year_pts"] = 2
        score += 2
    else:
        breakdown["year_pts"] = -2
        score -= 2
    title_pts = _title_overlap_score(hints, row)
    breakdown["title_pts"] = title_pts
    score += int(title_pts)
    reprint_row = _row_is_reprint_or_facsimile(row)
    if hints.facsimile_or_reprint:
        fac_pts = 2 if reprint_row else -4
        breakdown["facsimile_pts"] = fac_pts
        score += fac_pts
    elif reprint_row and hints.year and hints.year >= 2010:
        breakdown["facsimile_pts"] = -1
        score -= 1
    fp_pts = _fingerprint_gcd_boost(
        session,
        image_path=image_path,
        gcd_issue_id=int(row["gcd_issue_id"]),
        hints=hints,
    )
    breakdown["fingerprint_pts"] = fp_pts
    score += int(fp_pts)
    breakdown["total"] = score
    return score, breakdown


def _score_candidate(
    session: Session,
    *,
    row: dict[str, Any],
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
) -> int:
    score, _ = _score_candidate_breakdown(session, row=row, hints=hints, image_path=image_path)
    return score


def _pick_unique_high_confidence_candidate(
    session: Session,
    *,
    candidates: list[dict[str, Any]],
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    decision: dict[str, Any] = {
        "min_unique_score": _MIN_UNIQUE_SCORE,
        "second_best_gap_required": _SECOND_BEST_GAP,
        "decision_reason": None,
        "winning_candidate": None,
        "second_candidate": None,
        "score_gap": None,
        "candidates_scored": [],
    }
    if not hints.issue_number or not hints.publisher:
        decision["decision_reason"] = "missing_issue_or_publisher_hints"
        return None, [], decision
    scored: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for row in candidates:
        s, breakdown = _score_candidate_breakdown(session, row=row, hints=hints, image_path=image_path)
        decision["candidates_scored"].append(breakdown)
        if s > 0:
            scored.append((s, row, breakdown))
    if not scored:
        decision["decision_reason"] = "no_positive_scores"
        return None, [], decision
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_score, top_row, top_breakdown = scored[0]
    decision["winning_candidate"] = top_breakdown
    if len(scored) >= 2:
        decision["second_candidate"] = scored[1][2]
        decision["score_gap"] = top_score - scored[1][0]
    else:
        decision["score_gap"] = None
    if top_score < _MIN_UNIQUE_SCORE:
        decision["decision_reason"] = "top_score_below_min_unique"
        return None, [r for _, r, _ in scored[:5]], decision
    if len(scored) >= 2 and (top_score - scored[1][0]) < _SECOND_BEST_GAP:
        decision["decision_reason"] = "score_gap_below_second_best_threshold"
        return None, [r for _, r, _ in scored[:5]], decision
    decision["decision_reason"] = "unique_high_confidence_winner"
    return top_row, [top_row], decision


def _fingerprint_similarity_for_instrumentation(
    session: Session,
    *,
    image_path: Path | None,
    ranked_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if image_path is None or not image_path.is_file():
        return []
    hits = gated_search_catalog_fingerprint_hits_for_crop_path(session, crop_path=image_path, limit=5)
    out: list[dict[str, Any]] = []
    for hit in hits:
        issue = session.get(CatalogIssue, int(hit.issue_id))
        linked = extract_gcd_issue_id(issue.external_source_ids) if issue else None
        out.append(
            {
                "catalog_issue_id": int(hit.issue_id),
                "confidence": float(hit.confidence),
                "gcd_issue_id": int(linked) if linked is not None else None,
            }
        )
    del ranked_rows  # reserved for future per-candidate fingerprint alignment
    return out


def _log_p106_1_instrumentation(
    *,
    barcode: str,
    hints: IntakeGcdRecoveryHints,
    prior_diagnosis: dict[str, Any],
    instrumentation: dict[str, Any],
) -> None:
    payload = {
        "barcode": barcode,
        "decoded_barcode": prior_diagnosis.get("normalized_barcode") or barcode,
        "ocr_issue_number": hints.ocr_issue_number,
        "ocr_title": hints.ocr_title,
        "ocr_publisher": hints.ocr_publisher,
        "ocr_year": hints.year,
        "recovery_hints_issue": hints.issue_number,
        "recovery_hints_publisher": hints.publisher,
        "recovery_hints_series": hints.series,
        "recovery_hints_year": hints.year,
        "facsimile_or_reprint_hint": hints.facsimile_or_reprint,
        **instrumentation,
    }
    logger.info("p106_1.instrumentation %s", json.dumps(payload, default=str))


def _recovery_hints_payload(hints: IntakeGcdRecoveryHints) -> dict[str, Any]:
    return {
        "publisher": hints.publisher,
        "series": hints.series,
        "issue_number": hints.issue_number,
        "year": hints.year,
        "ocr_title": hints.ocr_title,
        "ocr_issue_number": hints.ocr_issue_number,
        "ocr_publisher": hints.ocr_publisher,
        "ocr_confidence": hints.ocr_confidence,
        "raw_ocr_text_excerpt": hints.raw_ocr_text_excerpt,
        "facsimile_or_reprint": hints.facsimile_or_reprint,
        "series_hint_reliable": has_reliable_series_hint(hints.series),
        "ocr_engine_available": hints.ocr_engine_available,
        "ocr_error": hints.ocr_error,
        "fingerprint_candidate_count": len(_qualified_fingerprint_candidates(hints.fingerprint_candidates)),
        "fingerprint_candidate_catalog_issue_id": hints.fingerprint_candidate_catalog_issue_id,
        "fingerprint_candidate_gcd_issue_id": hints.fingerprint_candidate_gcd_issue_id,
        "fingerprint_confidence": hints.fingerprint_confidence,
        "fingerprint_match_source": hints.fingerprint_match_source,
        "fingerprint_image_region": hints.fingerprint_image_region,
        "fingerprint_region_safe": hints.fingerprint_region_safe,
        "fingerprint_suppressed_reason": hints.fingerprint_suppressed_reason,
    }


def _fingerprint_only_auto_import_allowed(
    *,
    barcode: str,
    hints: IntakeGcdRecoveryHints,
    winner: dict[str, Any],
) -> tuple[bool, str | None]:
    winner_publisher = str(winner.get("publisher") or "")
    if _publisher_matches(hints.publisher, winner_publisher):
        publisher_ok = True
    else:
        prefix_pub = effective_publisher_for_barcode(barcode, None)
        publisher_ok = bool(prefix_pub and _publisher_matches(prefix_pub, winner_publisher))
    if not publisher_ok:
        return False, "fingerprint_only_without_publisher_agreement"
    validation = validate_barcode_catalog_match(
        barcode,
        publisher=winner_publisher,
        issue_number=str(winner.get("issue_number") or ""),
        year=str(hints.year) if hints.year is not None else None,
    )
    if validation.status != "exact_match":
        return False, validation.reason or "barcode_catalog_conflict"
    return True, None


def _merge_pool_instrumentation(
    instrumentation: dict[str, Any],
    pool_fp_meta: dict[str, Any],
    hints: IntakeGcdRecoveryHints,
) -> None:
    instrumentation.update(pool_fp_meta)
    instrumentation.setdefault(
        "fingerprint_candidate_count",
        len(_qualified_fingerprint_candidates(hints.fingerprint_candidates)),
    )


def _ocr_unavailable_instrumentation(hints: IntakeGcdRecoveryHints) -> dict[str, Any]:
    if hints.ocr_engine_available:
        return {}
    return {
        "ocr_engine_available": False,
        "ocr_error": hints.ocr_error or "Local Tesseract OCR engine is unavailable on this host.",
    }


def _finalize_p106_1_diagnosis_with_fingerprint_review(
    session: Session,
    base: dict[str, Any],
    *,
    hints: IntakeGcdRecoveryHints,
    barcode: str,
) -> dict[str, Any]:
    from app.services.intake_fingerprint_image_region_service import (
        FingerprintRegionAssessment,
        merge_fingerprint_region_instrumentation,
    )
    from app.services.p106_fingerprint_review_fallback_service import attach_fingerprint_review_to_diagnosis

    merge_fingerprint_region_instrumentation(
        base,
        FingerprintRegionAssessment(
            fingerprint_image_region=hints.fingerprint_image_region,
            fingerprint_region_safe=hints.fingerprint_region_safe,
            fingerprint_suppressed_reason=hints.fingerprint_suppressed_reason,
        ),
    )
    if not hints.fingerprint_region_safe:
        base.pop("needs_review_top_candidates", None)
        return base
    attach_fingerprint_review_to_diagnosis(session, base, hints=hints, barcode=barcode)
    return base


def diagnose_gcd_non_barcode_recovery(
    session: Session,
    *,
    barcode: str,
    gcd_path: Path,
    cache_path: Path | None,
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
    prior_diagnosis: dict[str, Any],
) -> dict[str, Any]:
    """Build a P106-compatible diagnosis when barcode lookup missed but metadata finds one GCD issue."""
    base = dict(prior_diagnosis)
    base["normalized_barcode"] = normalize_scan_preserving_supplement(barcode) or barcode
    base["fingerprint_candidate_count"] = len(_qualified_fingerprint_candidates(hints.fingerprint_candidates))
    if int(prior_diagnosis.get("gcd_match_count") or 0) > 0:
        base["p106_1_skipped"] = True
        base["p106_1_skip_reason"] = "prior_p106_gcd_match_count_nonzero"
        return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)
    if prior_diagnosis.get("already_resolved"):
        return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)
    if not hints.issue_number or not hints.publisher:
        instrumentation = {
            "decision_reason": "insufficient_metadata",
            "ready_to_auto_import": False,
            "gcd_candidates": [],
            **_ocr_unavailable_instrumentation(hints),
        }
        _log_p106_1_instrumentation(
            barcode=barcode,
            hints=hints,
            prior_diagnosis=prior_diagnosis,
            instrumentation=instrumentation,
        )
        base.update(
            {
                "recovery_stage": P106_1_RECOVERY_STAGE,
                "recovery_reason": "insufficient_metadata",
                "ready_to_auto_import": False,
                "recovery_hints": _recovery_hints_payload(hints),
                "p106_1_instrumentation": instrumentation,
            }
        )
        return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)

    candidates = _query_gcd_empty_barcode_candidates(gcd_path, issue_number=hints.issue_number)
    publisher_filtered = [
        c
        for c in candidates
        if _publisher_matches(hints.publisher, str(c.get("publisher") or ""))
    ]
    scorable, pool_block, pool_fp_meta = _prepare_scoring_candidates(
        session,
        hints=hints,
        image_path=image_path,
        prior_diagnosis=prior_diagnosis,
        publisher_filtered=publisher_filtered,
    )
    if pool_block:
        instrumentation = {
            "decision_reason": pool_block,
            "ready_to_auto_import": False,
            "empty_barcode_candidate_count": len(candidates),
            "publisher_filtered_count": len(publisher_filtered),
            "scorable_candidate_count": 0,
            "series_hint_reliable": has_reliable_series_hint(hints.series),
            **_ocr_unavailable_instrumentation(hints),
        }
        _merge_pool_instrumentation(instrumentation, pool_fp_meta, hints)
        _log_p106_1_instrumentation(
            barcode=barcode,
            hints=hints,
            prior_diagnosis=prior_diagnosis,
            instrumentation=instrumentation,
        )
        base.update(
            {
                "recovery_stage": P106_1_RECOVERY_STAGE,
                "recovery_reason": pool_block,
                "recovery_block_reason": pool_block,
                "ready_to_auto_import": False,
                "status": P106_STATUS_REVIEW_REQUIRED,
                "reason": pool_block,
                "final_reason": pool_block,
                "gcd_match_count": 0,
                "recovery_hints": _recovery_hints_payload(hints),
                "p106_1_instrumentation": instrumentation,
            }
        )
        return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)

    winner, ranked, pick_decision = _pick_unique_high_confidence_candidate(
        session,
        candidates=scorable,
        hints=hints,
        image_path=image_path,
    )
    fingerprint_hits = _fingerprint_similarity_for_instrumentation(
        session, image_path=image_path, ranked_rows=ranked
    )
    instrumentation = {
        "empty_barcode_candidate_count": len(candidates),
        "publisher_filtered_count": len(publisher_filtered),
        "scorable_candidate_count": len(scorable),
        "series_hint_reliable": has_reliable_series_hint(hints.series),
        "fingerprint_top_hits": fingerprint_hits,
        "pick_decision": pick_decision,
        "gcd_candidates": pick_decision.get("candidates_scored") or [],
        "fingerprint_candidate_count": base.get("fingerprint_candidate_count"),
        **_ocr_unavailable_instrumentation(hints),
    }
    _merge_pool_instrumentation(instrumentation, pool_fp_meta, hints)
    fingerprint_narrowed = bool(pool_fp_meta.get("fingerprint_candidate_used"))

    base.update(
        {
            "recovery_stage": P106_1_RECOVERY_STAGE,
            "exact_barcode_path": False,
            "bypass_p1035_text_matching": True,
            "recovery_hints": _recovery_hints_payload(hints),
            "gcd_non_barcode_candidate_count": len(publisher_filtered),
            "gcd_non_barcode_ranked": ranked[:5],
            "p106_1_instrumentation": instrumentation,
        }
    )

    if winner is None:
        reason = (
            "ambiguous_gcd_non_barcode_candidates"
            if ranked
            else "no_gcd_non_barcode_match"
        )
        if pool_block:
            reason = pool_block
        block_reason = pick_decision.get("decision_reason") or reason
        instrumentation["decision_reason"] = block_reason
        instrumentation["ready_to_auto_import"] = False
        instrumentation["ui_finish_reason"] = (
            "GCD barcode match needs review"
            if reason == "ambiguous_gcd_non_barcode_candidates"
            else None
        )
        _log_p106_1_instrumentation(
            barcode=barcode,
            hints=hints,
            prior_diagnosis=prior_diagnosis,
            instrumentation=instrumentation,
        )
        base.update(
            {
                "ready_to_auto_import": False,
                "status": P106_STATUS_REVIEW_REQUIRED if ranked else P106_STATUS_UNRESOLVED,
                "reason": reason,
                "final_reason": reason,
                "recovery_block_reason": block_reason,
                "gcd_match_count": 0,
            }
        )
        return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)

    if fingerprint_narrowed:
        allowed, fp_block = _fingerprint_only_auto_import_allowed(
            barcode=barcode,
            hints=hints,
            winner=winner,
        )
        if not allowed:
            block_reason = fp_block or "fingerprint_auto_import_blocked"
            instrumentation["decision_reason"] = block_reason
            instrumentation["ready_to_auto_import"] = False
            instrumentation["fingerprint_conflict_reason"] = block_reason
            _log_p106_1_instrumentation(
                barcode=barcode,
                hints=hints,
                prior_diagnosis=prior_diagnosis,
                instrumentation=instrumentation,
            )
            base.update(
                {
                    "ready_to_auto_import": False,
                    "status": P106_STATUS_REVIEW_REQUIRED,
                    "reason": block_reason,
                    "final_reason": block_reason,
                    "recovery_block_reason": block_reason,
                    "gcd_match_count": 0,
                    "gcd_non_barcode_ranked": ranked[:5],
                }
            )
            return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)

    gcd_issue_id = int(winner["gcd_issue_id"])
    gcd_match = {
        "gcd_issue_id": gcd_issue_id,
        "publisher": winner.get("publisher"),
        "series": winner.get("series"),
        "issue_number": winner.get("issue_number"),
        "key_date": winner.get("key_date"),
        "year_began": winner.get("year_began"),
        "title": winner.get("title"),
        "barcode_raw": winner.get("barcode_raw"),
        "match_source_field": "non_barcode_recovery",
    }
    catalog_id = resolve_catalog_issue_for_gcd_barcode(
        session,
        cache_path=cache_path,
        gcd_match=gcd_match,
        gcd_issue_id=gcd_issue_id,
    )

    instrumentation["decision_reason"] = "unique_gcd_non_barcode_recovery"
    instrumentation["ready_to_auto_import"] = True
    instrumentation["winning_gcd_issue_id"] = gcd_issue_id
    instrumentation["catalog_issue_id"] = catalog_id
    _log_p106_1_instrumentation(
        barcode=barcode,
        hints=hints,
        prior_diagnosis=prior_diagnosis,
        instrumentation=instrumentation,
    )

    base.update(
        {
            "gcd_match_count": 1,
            "gcd_matches": [gcd_match],
            "gcd_issue_id": gcd_issue_id,
            "catalog_issue_id": catalog_id,
            "ready_to_auto_import": True,
            "reason": "unique_gcd_non_barcode_recovery",
            "final_reason": "unique_gcd_non_barcode_recovery",
            "import_reason": P106_1_IMPORT_REASON,
        }
    )

    if catalog_id is not None:
        base.update(
            {
                "status": P106_STATUS_AUTO_ATTACHED,
                "proposed_action": "auto_attach",
            }
        )
    else:
        base.update(
            {
                "status": P106_STATUS_AUTO_IMPORTED,
                "proposed_action": "auto_import",
            }
        )
    return _finalize_p106_1_diagnosis_with_fingerprint_review(session, base, hints=hints, barcode=barcode)


def enrich_gap_diagnosis_with_gcd_non_barcode_recovery(
    session: Session,
    *,
    item: Any,
    barcode: str,
    gcd_path: Path,
    cache_path: Path | None,
    image_path: Path | None,
    image_bytes: bytes | None,
    prior_diagnosis: dict[str, Any],
    p105: Any,
    recovery_hints: IntakeGcdRecoveryHints | None = None,
) -> dict[str, Any]:
    if int(prior_diagnosis.get("gcd_match_count") or 0) > 0:
        logger.info(
            "p106_1.skipped barcode=%s prior_gcd_match_count=%s prior_reason=%s prior_status=%s",
            barcode,
            prior_diagnosis.get("gcd_match_count"),
            prior_diagnosis.get("reason"),
            prior_diagnosis.get("status"),
        )
        return prior_diagnosis
    hints = recovery_hints or gather_intake_gcd_recovery_hints(
        session,
        item=item,
        normalized_barcode=barcode,
        image_path=image_path,
        image_bytes=image_bytes,
        p105=p105,
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=barcode,
        gcd_path=gcd_path,
        cache_path=cache_path,
        hints=hints,
        image_path=image_path,
        prior_diagnosis=prior_diagnosis,
    )
    if diag.get("ready_to_auto_import"):
        logger.info(
            "p106_1.non_barcode_recovery barcode=%s gcd_issue_id=%s action=%s",
            barcode,
            diag.get("gcd_issue_id"),
            diag.get("proposed_action"),
        )
    return diag
