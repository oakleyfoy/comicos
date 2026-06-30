"""P106.1/P107 — fingerprint review when catalog rows lack GCD linkage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue
from app.services.barcode_validation_service import (
    barcode_encoded_issue_number,
    effective_publisher_for_barcode,
    validate_barcode_catalog_match,
)
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id, effective_catalog_issue_year
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    FINGERPRINT_CATALOG_MATCH_SOURCE,
    FingerprintRecoveryCandidate,
    IntakeGcdRecoveryHints,
    _qualified_fingerprint_candidates,
)
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

FINGERPRINT_REVIEW_SOURCE = "fingerprint"
COMICVINE_REVIEW_SOURCE = "comicvine"
STRICT_FINGERPRINT_CONFIDENCE = 0.92
REVIEW_DECISION_TOP = "needs_review_top_candidates"


def _comicvine_id_keys(external: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(external, dict):
        return ()
    bucket = external.get("COMICVINE")
    if not isinstance(bucket, dict):
        return ()
    return tuple(sorted(str(k) for k in bucket if str(k).isdigit()))


def catalog_identity_family_key(session: Session, catalog_issue_id: int) -> tuple[Any, ...]:
    issue = session.get(CatalogIssue, int(catalog_issue_id))
    if issue is None:
        return (int(catalog_issue_id),)
    identity = load_catalog_issue_identity(session, int(catalog_issue_id))
    pub = normalize_series_name(identity.publisher if identity else "")
    series = normalize_series_name(identity.series if identity else "")
    if not series and issue.title:
        series = normalize_series_name(str(issue.title))
    issue_num = normalize_issue_number(issue.normalized_issue_number or issue.issue_number or "")
    year = effective_catalog_issue_year(
        year=None,
        cover_date=issue.cover_date,
        release_date=issue.release_date,
    )
    cv_keys = _comicvine_id_keys(issue.external_source_ids)
    return (pub, series, issue_num, year, cv_keys)


@dataclass(frozen=True)
class CollapsedFingerprintGroup:
    family_key: tuple[Any, ...]
    catalog_issue_id: int
    confidence: float
    member_count: int


def collapse_fingerprint_candidates(
    session: Session,
    candidates: list[FingerprintRecoveryCandidate],
) -> list[CollapsedFingerprintGroup]:
    qualified = _qualified_fingerprint_candidates(candidates)
    counts: dict[tuple[Any, ...], int] = {}
    best_conf: dict[tuple[Any, ...], float] = {}
    best_id: dict[tuple[Any, ...], int] = {}
    for cand in qualified:
        key = catalog_identity_family_key(session, int(cand.catalog_issue_id))
        counts[key] = counts.get(key, 0) + 1
        conf = float(cand.confidence)
        if key not in best_conf or conf > best_conf[key]:
            best_conf[key] = conf
            best_id[key] = int(cand.catalog_issue_id)
    out = [
        CollapsedFingerprintGroup(
            family_key=key,
            catalog_issue_id=best_id[key],
            confidence=best_conf[key],
            member_count=counts[key],
        )
        for key in best_id
    ]
    out.sort(key=lambda g: (-g.confidence, -g.member_count, g.catalog_issue_id))
    return out


def review_candidate_from_catalog_issue(
    session: Session,
    *,
    catalog_issue_id: int,
    confidence: float,
    source: str = FINGERPRINT_REVIEW_SOURCE,
) -> dict[str, Any] | None:
    identity = load_catalog_issue_identity(session, int(catalog_issue_id))
    issue = session.get(CatalogIssue, int(catalog_issue_id))
    if identity is None or issue is None:
        return None
    year = effective_catalog_issue_year(
        year=None,
        cover_date=issue.cover_date,
        release_date=issue.release_date,
    )
    title = (issue.title or "").strip() or identity.series
    return {
        "catalog_issue_id": int(catalog_issue_id),
        "series": identity.series,
        "title": title,
        "issue_number": identity.issue_number,
        "publisher": identity.publisher,
        "year": str(year) if year is not None else None,
        "confidence": round(float(confidence), 4),
        "source": source,
        "cover_url": identity.cover_image_url,
        "gcd_issue_id": extract_gcd_issue_id(issue.external_source_ids),
        "comicvine_ids": list(_comicvine_id_keys(issue.external_source_ids)),
    }


def build_fingerprint_review_bundle(
    session: Session,
    hints: IntakeGcdRecoveryHints,
    *,
    limit: int = 3,
) -> dict[str, Any]:
    groups = collapse_fingerprint_candidates(session, hints.fingerprint_candidates)
    top_candidates: list[dict[str, Any]] = []
    for group in groups[:limit]:
        row = review_candidate_from_catalog_issue(
            session,
            catalog_issue_id=group.catalog_issue_id,
            confidence=group.confidence,
            source=FINGERPRINT_REVIEW_SOURCE,
        )
        if row is not None:
            row["fingerprint_family_member_count"] = group.member_count
            top_candidates.append(row)
    single_family = len(groups) == 1 and bool(groups)
    return {
        "top_candidates": top_candidates,
        "collapsed_family_count": len(groups),
        "single_family": single_family,
        "qualified_fingerprint_count": len(_qualified_fingerprint_candidates(hints.fingerprint_candidates)),
    }


def _normalize_identity_triple(
    *,
    publisher: str | None,
    series: str | None,
    issue_number: str | None,
) -> tuple[str, str, str]:
    return (
        normalize_series_name(publisher or ""),
        normalize_series_name(series or ""),
        normalize_issue_number(issue_number or ""),
    )


def fingerprint_review_agrees_with_identity(
    review_rows: list[dict[str, Any]],
    *,
    publisher: str | None,
    series: str | None,
    issue_number: str | None,
) -> bool:
    if not review_rows:
        return False
    target = _normalize_identity_triple(publisher=publisher, series=series, issue_number=issue_number)
    for row in review_rows[:3]:
        cand = _normalize_identity_triple(
            publisher=str(row.get("publisher") or ""),
            series=str(row.get("series") or row.get("title") or ""),
            issue_number=str(row.get("issue_number") or ""),
        )
        if cand == target:
            return True
        if cand[1] == target[1] and cand[2] == target[2] and (not target[0] or cand[0] == target[0]):
            return True
    return False


def _barcode_issue_conflict_explainable(barcode: str, issue_number: str | None) -> bool:
    encoded = barcode_encoded_issue_number(barcode)
    if encoded is None or not issue_number:
        return True
    return normalize_issue_number(str(encoded)) == normalize_issue_number(str(issue_number))


def strict_fingerprint_import_gates(
    *,
    barcode: str,
    hints: IntakeGcdRecoveryHints,
    publisher: str | None,
    issue_number: str | None,
    year: str | None,
    fingerprint_confidence: float | None,
) -> tuple[bool, str | None]:
    if fingerprint_confidence is None or float(fingerprint_confidence) < STRICT_FINGERPRINT_CONFIDENCE:
        return False, "fingerprint_below_strict_threshold"
    winner_publisher = str(publisher or "")
    prefix_pub = effective_publisher_for_barcode(barcode, None)
    publisher_ok = False
    if hints.publisher and winner_publisher:
        publisher_ok = normalize_series_name(hints.publisher) == normalize_series_name(winner_publisher)
    if not publisher_ok and prefix_pub and winner_publisher:
        publisher_ok = normalize_series_name(prefix_pub) == normalize_series_name(winner_publisher)
    if not publisher_ok:
        return False, "fingerprint_only_without_publisher_agreement"
    if not _barcode_issue_conflict_explainable(barcode, issue_number):
        return False, "barcode_issue_number_hard_conflict"
    validation = validate_barcode_catalog_match(
        barcode,
        publisher=winner_publisher,
        issue_number=str(issue_number or ""),
        year=str(year or hints.year or ""),
    )
    if validation.status != "exact_match":
        return False, validation.reason or "barcode_catalog_conflict"
    return True, None


def attach_fingerprint_review_to_diagnosis(
    session: Session,
    diagnosis: dict[str, Any],
    *,
    hints: IntakeGcdRecoveryHints,
    barcode: str,
) -> dict[str, Any]:
    if diagnosis.get("needs_full_cover_photo"):
        return {"top_candidates": [], "collapsed_family_count": 0, "single_family": False, "qualified_fingerprint_count": 0}
    if not hints.fingerprint_region_safe:
        return {"top_candidates": [], "collapsed_family_count": 0, "single_family": False, "qualified_fingerprint_count": 0}
    bundle = build_fingerprint_review_bundle(session, hints, limit=3)
    top = bundle["top_candidates"]
    if not top:
        return bundle
    diagnosis["needs_review_top_candidates"] = top
    diagnosis["fingerprint_review"] = {
        "collapsed_family_count": bundle["collapsed_family_count"],
        "single_family": bundle["single_family"],
        "qualified_fingerprint_count": bundle["qualified_fingerprint_count"],
    }
    if bundle["single_family"] and len(top) == 1:
        diagnosis["review_decision"] = REVIEW_DECISION_TOP
        diagnosis["fingerprint_review_primary_catalog_issue_id"] = top[0].get("catalog_issue_id")
    elif len(top) >= 1:
        diagnosis["review_decision"] = REVIEW_DECISION_TOP
    if int(diagnosis.get("gcd_match_count") or 0) == 0 and not diagnosis.get("ready_to_auto_import"):
        diagnosis.setdefault("status", "review_required")
        primary = top[0]
        if not diagnosis.get("gcd_series"):
            diagnosis["gcd_series"] = primary.get("series") or primary.get("title")
        if not diagnosis.get("gcd_issue_number"):
            diagnosis["gcd_issue_number"] = primary.get("issue_number")
        if not diagnosis.get("gcd_publisher"):
            diagnosis["gcd_publisher"] = primary.get("publisher")
    return bundle


def enhance_diagnosis_with_comicvine_fingerprint_consensus(
    diagnosis: dict[str, Any],
    *,
    hints: IntakeGcdRecoveryHints,
    barcode: str,
    comicvine_candidate: dict[str, Any] | None,
) -> None:
    if not comicvine_candidate:
        return
    review_rows = diagnosis.get("needs_review_top_candidates")
    if not isinstance(review_rows, list):
        review_rows = []
    agrees = fingerprint_review_agrees_with_identity(
        review_rows,
        publisher=comicvine_candidate.get("publisher"),
        series=comicvine_candidate.get("series"),
        issue_number=comicvine_candidate.get("issue_number"),
    )
    if not agrees and review_rows:
        return
    top_conf = None
    if review_rows:
        top_conf = float(review_rows[0].get("confidence") or 0.0)
    elif hints.fingerprint_confidence is not None:
        top_conf = float(hints.fingerprint_confidence)
    allowed, block = strict_fingerprint_import_gates(
        barcode=barcode,
        hints=hints,
        publisher=comicvine_candidate.get("publisher"),
        issue_number=comicvine_candidate.get("issue_number"),
        year=str(comicvine_candidate.get("year") or ""),
        fingerprint_confidence=top_conf,
    )
    cv_row = {
        "publisher": comicvine_candidate.get("publisher"),
        "series": comicvine_candidate.get("series"),
        "title": comicvine_candidate.get("series"),
        "issue_number": comicvine_candidate.get("issue_number"),
        "year": comicvine_candidate.get("year"),
        "cover_url": comicvine_candidate.get("cover_url"),
        "source": COMICVINE_REVIEW_SOURCE,
        "catalog_issue_id": comicvine_candidate.get("catalog_issue_id"),
        "import_ready": allowed,
        "import_block_reason": block,
        "fingerprint_agreement": agrees or not review_rows,
    }
    diagnosis["comicvine_review_candidate"] = cv_row
    if allowed and int(diagnosis.get("gcd_match_count") or 0) == 0:
        diagnosis["ready_to_auto_import"] = True
        diagnosis["proposed_action"] = "comicvine_import"
        diagnosis["import_path"] = "comicvine_fingerprint_consensus"


def persist_review_candidates_on_intake_item(
    session: Session,
    *,
    item_id: int,
    diagnosis: dict[str, Any],
    add_candidate_fn: Any,
    clear_candidates_fn: Any,
) -> None:
    if diagnosis.get("needs_full_cover_photo"):
        clear_candidates_fn(session, item_id)
        return
    if diagnosis.get("fingerprint_region_safe") is False:
        clear_candidates_fn(session, item_id)
        return
    region = str(diagnosis.get("fingerprint_image_region") or "")
    if region in {
        "barcode_strip",
        "upc_region",
        "unsafe_partial_cover_barcode_frame",
    }:
        clear_candidates_fn(session, item_id)
        return
    tops = diagnosis.get("needs_review_top_candidates")
    if not isinstance(tops, list) or not tops:
        return
    clear_candidates_fn(session, item_id)
    for rank, row in enumerate(tops[:3]):
        if not isinstance(row, dict):
            continue
        add_candidate_fn(
            session,
            item_id=item_id,
            source=str(row.get("source") or FINGERPRINT_REVIEW_SOURCE),
            rank=rank,
            data={
                "catalog_issue_id": row.get("catalog_issue_id"),
                "variant_id": None,
                "publisher": row.get("publisher"),
                "series": row.get("series") or row.get("title"),
                "issue_number": row.get("issue_number"),
                "cover_url": row.get("cover_url"),
                "score": float(row.get("confidence") or 0.0) * 100.0,
            },
        )
    cv = diagnosis.get("comicvine_review_candidate")
    if isinstance(cv, dict) and cv.get("import_ready"):
        add_candidate_fn(
            session,
            item_id=item_id,
            source=COMICVINE_REVIEW_SOURCE,
            rank=len(tops[:3]),
            data={
                "catalog_issue_id": cv.get("catalog_issue_id"),
                "variant_id": None,
                "publisher": cv.get("publisher"),
                "series": cv.get("series"),
                "issue_number": cv.get("issue_number"),
                "cover_url": cv.get("cover_url"),
                "score": 85.0,
            },
        )
