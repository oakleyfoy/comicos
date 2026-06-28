"""P106.1 — GCD issue recovery when the scanned barcode has no row in gcd_issue.barcode."""

from __future__ import annotations

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
from app.services.photo_import_fingerprint_service import search_catalog_fingerprint_hits_for_crop_path
from app.services.recognition.ocr_matcher import extract_ocr_signal

logger = logging.getLogger(__name__)

P106_1_RECOVERY_STAGE = "p106_1_non_barcode"
P106_1_IMPORT_REASON = "gcd_non_barcode_recovery"
_MIN_UNIQUE_SCORE = 10
_SECOND_BEST_GAP = 3
_FINGERPRINT_BOOST = 4
_FINGERPRINT_MIN_CONFIDENCE = 0.82


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
) -> IntakeGcdRecoveryHints:
    del session, image_path, p105  # reserved for future intake hooks

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

    if image_bytes:
        ocr = extract_ocr_signal(image_bytes, source_name=f"intake-{getattr(item, 'id', 0)}")
        ocr_confidence = float(ocr.confidence or 0.0)
        if ocr_confidence >= 0.35:
            ocr_title = (ocr.title or "").strip() or None
            ocr_issue = (ocr.issue_number or "").strip() or None
            ocr_publisher = (ocr.publisher or "").strip() or None
            blob = (ocr.raw_text or "").lower()
            facsimile = bool(_REPRINT_DIGEST.search(blob))

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
    aliases = _series_norm_aliases(series_norm) if series_norm else []

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
    )


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


def _series_matches(hints: IntakeGcdRecoveryHints, row: dict[str, Any]) -> bool:
    if not hints.series_norm_aliases:
        return True
    series_name = str(row.get("series") or "")
    row_norm = normalize_series_name(series_name)
    for alias in hints.series_norm_aliases:
        if row_norm == alias or series_names_compatible(row_norm, alias):
            return True
    if hints.ocr_title:
        ocr_norm = normalize_series_name(hints.ocr_title)
        if row_norm == ocr_norm or series_names_compatible(row_norm, ocr_norm):
            return True
        if ocr_norm:
            title = str(row.get("title") or "")
            if ocr_norm in normalize_series_name(f"{series_name} {title}"):
                return True
    return False


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


def _fingerprint_gcd_boost(
    session: Session,
    *,
    image_path: Path | None,
    gcd_issue_id: int,
) -> float:
    if image_path is None or not image_path.is_file():
        return 0.0
    hits = search_catalog_fingerprint_hits_for_crop_path(session, crop_path=image_path, limit=5)
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


def _score_candidate(
    session: Session,
    *,
    row: dict[str, Any],
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
) -> int:
    score = 0
    if hints.issue_number:
        if normalize_issue_number(str(row.get("issue_number") or "")) == normalize_issue_number(hints.issue_number):
            score += 4
    if _publisher_matches(hints.publisher, str(row.get("publisher") or "")):
        score += 3
    if _series_matches(hints, row):
        score += 2
    else:
        return 0
    if _year_matches(hints, row):
        score += 2
    else:
        score -= 2
    score += int(_title_overlap_score(hints, row))
    reprint_row = _row_is_reprint_or_facsimile(row)
    if hints.facsimile_or_reprint:
        score += 2 if reprint_row else -4
    elif reprint_row and hints.year and hints.year >= 2010:
        score -= 1
    score += int(
        _fingerprint_gcd_boost(session, image_path=image_path, gcd_issue_id=int(row["gcd_issue_id"]))
    )
    return score


def _pick_unique_high_confidence_candidate(
    session: Session,
    *,
    candidates: list[dict[str, Any]],
    hints: IntakeGcdRecoveryHints,
    image_path: Path | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not hints.issue_number or not hints.publisher:
        return None, []
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in candidates:
        s = _score_candidate(session, row=row, hints=hints, image_path=image_path)
        if s > 0:
            scored.append((s, row))
    if not scored:
        return None, []
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_score, top_row = scored[0]
    if top_score < _MIN_UNIQUE_SCORE:
        return None, [r for _, r in scored[:5]]
    if len(scored) >= 2 and (top_score - scored[1][0]) < _SECOND_BEST_GAP:
        return None, [r for _, r in scored[:5]]
    return top_row, [top_row]


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
    if int(prior_diagnosis.get("gcd_match_count") or 0) > 0:
        return base
    if prior_diagnosis.get("already_resolved"):
        return base
    if not hints.issue_number or not hints.publisher:
        base.update(
            {
                "recovery_stage": P106_1_RECOVERY_STAGE,
                "recovery_reason": "insufficient_metadata",
                "ready_to_auto_import": False,
            }
        )
        return base

    candidates = _query_gcd_empty_barcode_candidates(gcd_path, issue_number=hints.issue_number)
    publisher_filtered = [
        c
        for c in candidates
        if _publisher_matches(hints.publisher, str(c.get("publisher") or ""))
    ]
    winner, ranked = _pick_unique_high_confidence_candidate(
        session,
        candidates=publisher_filtered,
        hints=hints,
        image_path=image_path,
    )

    base.update(
        {
            "recovery_stage": P106_1_RECOVERY_STAGE,
            "exact_barcode_path": False,
            "bypass_p1035_text_matching": True,
            "recovery_hints": {
                "publisher": hints.publisher,
                "series": hints.series,
                "issue_number": hints.issue_number,
                "year": hints.year,
                "ocr_title": hints.ocr_title,
                "facsimile_or_reprint": hints.facsimile_or_reprint,
            },
            "gcd_non_barcode_candidate_count": len(publisher_filtered),
            "gcd_non_barcode_ranked": ranked[:5],
        }
    )

    if winner is None:
        reason = (
            "ambiguous_gcd_non_barcode_candidates"
            if ranked
            else "no_gcd_non_barcode_match"
        )
        base.update(
            {
                "ready_to_auto_import": False,
                "status": P106_STATUS_REVIEW_REQUIRED if ranked else P106_STATUS_UNRESOLVED,
                "reason": reason,
                "final_reason": reason,
                "gcd_match_count": 0,
            }
        )
        return base

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
    return base


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
) -> dict[str, Any]:
    if int(prior_diagnosis.get("gcd_match_count") or 0) > 0:
        return prior_diagnosis
    hints = gather_intake_gcd_recovery_hints(
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
