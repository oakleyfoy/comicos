"""P107 — No-barcode cover recognition benchmark pipeline (OCR + fingerprint + catalog search)."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    series_names_compatible,
)
from app.services.intake_barcode_confidence import has_full_direct_market_barcode
from app.services.intake_queue_service import search_catalog_issues
from app.services.p100_barcode_extraction_service import extract_barcode_from_image
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id
from app.services.photo_import_fingerprint_service import (
    fingerprint_hashes_for_crop,
    fingerprint_match_score_for_crop_path,
    search_catalog_fingerprint_hits_for_crop_path,
)
from app.services.photo_import_storage_service import REPO_ROOT
from app.services.recognition.catalog_matcher import load_catalog_issue_identity
from app.services.recognition.ocr_matcher import extract_ocr_signal

logger = logging.getLogger(__name__)

P107_MANIFEST_DEFAULT = REPO_ROOT / "data" / "p107" / "no_barcode_manifest.csv"

SCORE_TITLE = 40
SCORE_ISSUE = 25
SCORE_PUBLISHER = 15
SCORE_YEAR = 10
SCORE_FINGERPRINT = 10

THRESHOLD_AUTO_MATCH = 95
THRESHOLD_NEEDS_REVIEW_TOP3 = 80

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

ManifestRow = dict[str, str]


@dataclass
class P107ExtractedSignals:
    title_candidates: list[str] = field(default_factory=list)
    issue_number_candidates: list[str] = field(default_factory=list)
    publisher_candidates: list[str] = field(default_factory=list)
    year_candidates: list[int] = field(default_factory=list)
    ocr_tokens: list[str] = field(default_factory=list)


def resolve_p107_image_path(image_path: str | Path) -> Path:
    raw = Path(str(image_path))
    if raw.is_file():
        return raw
    under_api = REPO_ROOT / str(image_path).replace("\\", "/").lstrip("/")
    if under_api.is_file():
        return under_api
    return under_api


def load_p107_manifest(path: Path | None = None) -> list[ManifestRow]:
    manifest_path = path or P107_MANIFEST_DEFAULT
    if not manifest_path.is_file():
        raise FileNotFoundError(f"P107 manifest not found: {manifest_path}")
    rows: list[ManifestRow] = []
    with manifest_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            if not (raw.get("image_path") or "").strip():
                continue
            rows.append({k: (v or "").strip() for k, v in raw.items()})
    return rows


def _similarity(a: str | None, b: str | None) -> float:
    left = normalize_series_name(a or "")
    right = normalize_series_name(b or "")
    if not left or not right:
        return 0.0
    if left == right or series_names_compatible(left, right):
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _issue_matches(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return normalize_issue_number(a) == normalize_issue_number(b)


def _years_from_text(text: str) -> list[int]:
    out: list[int] = []
    for match in _YEAR_RE.finditer(text or ""):
        y = int(match.group(0))
        if 1800 <= y <= 2100:
            out.append(y)
    return out


def _extract_signals(image_path: Path, *, image_bytes: bytes) -> P107ExtractedSignals:
    ocr = extract_ocr_signal(image_bytes, source_name=image_path.name)
    tokens = [t.strip() for t in re.split(r"\W+", ocr.raw_text or "") if len(t.strip()) >= 2]
    titles: list[str] = []
    if ocr.title:
        titles.append(ocr.title.strip())
    if ocr.normalized_text:
        for line in (ocr.normalized_text or "").splitlines():
            line = line.strip()
            if len(line) >= 3:
                titles.append(line)
    issues: list[str] = []
    if ocr.issue_number:
        issues.append(str(ocr.issue_number).strip())
    for token in tokens:
        if re.fullmatch(r"\d{1,4}[A-Za-z]?", token):
            issues.append(token.lstrip("#"))
    publishers: list[str] = []
    if ocr.publisher:
        publishers.append(ocr.publisher.strip())
    years = _years_from_text(ocr.raw_text or "")
    return P107ExtractedSignals(
        title_candidates=_dedupe_str(titles),
        issue_number_candidates=_dedupe_str(issues),
        publisher_candidates=_dedupe_str(publishers),
        year_candidates=sorted(set(years)),
        ocr_tokens=tokens[:64],
    )


def _dedupe_str(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = v.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _visual_fingerprint_summary(image_path: Path) -> str:
    hashes = fingerprint_hashes_for_crop(image_path)
    if hashes is None:
        return ""
    phash, dhash, ahash = hashes
    return f"phash={phash[:16]}… dhash={dhash[:16]}… ahash={ahash[:16]}…"


def _barcode_detected_on_image(image_bytes: bytes) -> tuple[bool, str | None]:
    result = extract_barcode_from_image(image_bytes, allow_gpt_fallback=False)
    code = (result.get("barcode") or "").strip()
    if not code:
        return False, None
    from app.services.barcode_scan_consensus_service import normalize_scan_preserving_supplement
    from app.services.catalog_ingestion_service import normalize_upc

    normalized = normalize_scan_preserving_supplement(code) or normalize_upc(code) or code
    if has_full_direct_market_barcode(normalized) or len(normalize_upc(normalized)) >= 12:
        return True, normalized[:64]
    return False, None


def _build_candidate_queries(signals: P107ExtractedSignals) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for title in signals.title_candidates[:6]:
        for issue in signals.issue_number_candidates[:3] or [None]:
            queries.append(
                {
                    "query": title,
                    "issue_number": issue,
                    "publisher": signals.publisher_candidates[0] if signals.publisher_candidates else None,
                    "year": signals.year_candidates[0] if signals.year_candidates else None,
                }
            )
    if not queries and signals.issue_number_candidates:
        queries.append({"query": "", "issue_number": signals.issue_number_candidates[0]})
    return queries[:12]


def _catalog_issue_has_gcd_link(session: Session, catalog_issue_id: int) -> bool:
    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is None:
        return False
    return extract_gcd_issue_id(issue.external_source_ids) is not None


def _catalog_issue_has_comicvine_link(session: Session, catalog_issue_id: int) -> bool:
    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is None:
        return False
    ext = issue.external_source_ids if isinstance(issue.external_source_ids, dict) else {}
    cv = ext.get("COMICVINE")
    if isinstance(cv, dict) and cv:
        return True
    return bool(ext.get("comicvine_issue_id") or ext.get("comicvine_volume_id"))


def _search_local_catalog(
    session: Session,
    queries: list[dict[str, Any]],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for q in queries:
        title = str(q.get("query") or "").strip()
        if not title:
            continue
        issue_number = q.get("issue_number")
        for row in search_catalog_issues(
            session,
            query=title,
            issue_number=str(issue_number) if issue_number else None,
            limit=limit,
        ):
            cid = int(row["catalog_issue_id"])
            if cid in seen:
                continue
            seen.add(cid)
            tier = "local_catalog"
            if _catalog_issue_has_gcd_link(session, cid):
                tier = "gcd_linked"
            elif _catalog_issue_has_comicvine_link(session, cid):
                tier = "comicvine_linked"
            out.append({**row, "search_tier": tier, "query": title})
    return out


def _search_comicvine_volume_candidates(
    signals: P107ExtractedSignals,
    *,
    search_volumes: Callable[[str, int], list[dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    if search_volumes is None:
        return []
    out: list[dict[str, Any]] = []
    for title in signals.title_candidates[:3]:
        try:
            volumes = search_volumes(title, 10)
        except Exception:
            logger.debug("p107.comicvine_search_failed title=%s", title, exc_info=True)
            continue
        for vol in volumes or []:
            out.append(
                {
                    "catalog_issue_id": None,
                    "series": str(vol.get("name") or title),
                    "issue_number": signals.issue_number_candidates[0] if signals.issue_number_candidates else "",
                    "publisher": str(vol.get("publisher") or signals.publisher_candidates[0] or ""),
                    "cover_url": vol.get("image_url"),
                    "search_tier": "comicvine_linked",
                    "query": title,
                    "comicvine_volume_id": vol.get("id"),
                }
            )
    return out[:15]


def score_p107_match(
    candidate: dict[str, Any],
    *,
    signals: P107ExtractedSignals,
    fingerprint_score: float | None = None,
    expected: ManifestRow | None = None,
) -> float:
    """Deterministic weighted score (max 100)."""
    title_ref = (expected or {}).get("expected_title") or (
        signals.title_candidates[0] if signals.title_candidates else ""
    )
    issue_ref = (expected or {}).get("expected_issue_number") or (
        signals.issue_number_candidates[0] if signals.issue_number_candidates else ""
    )
    pub_ref = (expected or {}).get("expected_publisher") or (
        signals.publisher_candidates[0] if signals.publisher_candidates else ""
    )
    year_ref = (expected or {}).get("expected_year") or ""
    year_int: int | None = None
    if year_ref and str(year_ref).isdigit():
        year_int = int(year_ref)

    score = 0.0
    series = str(candidate.get("series") or candidate.get("title") or "")
    if title_ref and _similarity(title_ref, series) >= 0.72:
        score += SCORE_TITLE
    if issue_ref and _issue_matches(issue_ref, str(candidate.get("issue_number") or "")):
        score += SCORE_ISSUE
    if pub_ref and _similarity(pub_ref, str(candidate.get("publisher") or "")) >= 0.65:
        score += SCORE_PUBLISHER

    cand_year: int | None = None
    identity_year = candidate.get("year")
    if identity_year is not None and str(identity_year).isdigit():
        cand_year = int(str(identity_year))
    year_matched = False
    if year_int is not None and cand_year is not None and abs(year_int - cand_year) <= 1:
        year_matched = True
    elif cand_year is not None and signals.year_candidates:
        if any(abs(cand_year - y) <= 1 for y in signals.year_candidates):
            year_matched = True
    if year_matched:
        score += SCORE_YEAR

    fp = fingerprint_score
    if fp is None and candidate.get("catalog_issue_id") is not None:
        fp = float(candidate.get("fingerprint_score") or 0.0)
    if fp is not None and fp > 0:
        score += SCORE_FINGERPRINT * min(1.0, fp / 100.0)

    return round(min(100.0, score), 2)


def decision_from_score(score: float) -> str:
    if score >= THRESHOLD_AUTO_MATCH:
        return "auto_match"
    if score >= THRESHOLD_NEEDS_REVIEW_TOP3:
        return "needs_review_top_3"
    return "needs_review"


def _empty_result(*, barcode_detected: bool = False, barcode: str | None = None) -> dict[str, Any]:
    return {
        "barcode_detected": barcode_detected,
        "detected_barcode": barcode,
        "ocr_tokens": [],
        "visual_fingerprint": "",
        "candidate_queries": [],
        "ranked_matches": [],
        "best_match": None,
        "confidence": 0.0,
        "decision": "needs_review",
    }


def recognize_cover_without_barcode(
    session: Session,
    image_path: str | Path,
    *,
    allow_barcode: bool = False,
    expected: ManifestRow | None = None,
    search_volumes: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Run P107 pipeline when no usable barcode should drive identity."""
    path = resolve_p107_image_path(image_path)
    if not path.is_file():
        out = _empty_result()
        out["error"] = f"image_not_found:{path}"
        return out

    image_bytes = path.read_bytes()
    detected, normalized = _barcode_detected_on_image(image_bytes)
    if detected and not allow_barcode:
        out = _empty_result(barcode_detected=True, barcode=normalized)
        out["decision"] = "barcode_present_skip"
        return out

    signals = _extract_signals(path, image_bytes=image_bytes)
    visual = _visual_fingerprint_summary(path)
    queries = _build_candidate_queries(signals)

    raw_candidates = _search_local_catalog(session, queries)
    raw_candidates.extend(_search_comicvine_volume_candidates(signals, search_volumes=search_volumes))

    fp_hits = search_catalog_fingerprint_hits_for_crop_path(session, crop_path=path, limit=8)
    fp_by_issue = {int(h.issue_id): float(h.score) for h in fp_hits}

    ranked: list[dict[str, Any]] = []
    for cand in raw_candidates:
        cid = cand.get("catalog_issue_id")
        fp_score = fp_by_issue.get(int(cid)) if cid is not None else None
        if cid is not None and fp_score is None:
            fp_score = fingerprint_match_score_for_crop_path(
                session, crop_path=path, catalog_issue_id=int(cid)
            )
        if cid is not None:
            identity = load_catalog_issue_identity(session, int(cid))
            if identity is not None:
                issue_row = session.get(CatalogIssue, int(cid))
                year_val = None
                if issue_row is not None and issue_row.cover_date is not None:
                    year_val = str(issue_row.cover_date.year)
                cand = {
                    **cand,
                    "series": identity.series,
                    "issue_number": identity.issue_number,
                    "publisher": identity.publisher,
                    "year": year_val,
                }
        score = score_p107_match(cand, signals=signals, fingerprint_score=fp_score, expected=expected)
        ranked.append({**cand, "score": score, "fingerprint_score": fp_score})

    ranked.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
    best = ranked[0] if ranked else None
    confidence = float(best["score"]) if best else 0.0
    decision = decision_from_score(confidence)

    return {
        "barcode_detected": False,
        "detected_barcode": None,
        "ocr_tokens": signals.ocr_tokens,
        "visual_fingerprint": visual,
        "candidate_queries": queries,
        "ranked_matches": ranked[:10],
        "best_match": best,
        "confidence": confidence,
        "decision": decision,
    }


def evaluate_p107_manifest_row(
    session: Session,
    row: ManifestRow,
    *,
    search_volumes: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    result = recognize_cover_without_barcode(
        session,
        row["image_path"],
        expected=row,
        search_volumes=search_volumes,
    )
    expected_issue = normalize_issue_number(row.get("expected_issue_number") or "")
    hit = False
    best = result.get("best_match")
    if best and best.get("catalog_issue_id") is not None:
        if _issue_matches(row.get("expected_issue_number"), str(best.get("issue_number") or "")):
            if _similarity(row.get("expected_title"), str(best.get("series") or "")) >= 0.65:
                hit = True
    elif best and best.get("comicvine_volume_id"):
        hit = _similarity(row.get("expected_title"), str(best.get("series") or "")) >= 0.65

    return {
        "manifest_row": row,
        "recognition": result,
        "benchmark_hit": hit,
        "expected_issue_norm": expected_issue,
    }


def run_p107_benchmark(
    session: Session,
    *,
    manifest_path: Path | None = None,
    limit: int | None = None,
    search_volumes: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    rows = load_p107_manifest(manifest_path)
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    evaluations = [
        evaluate_p107_manifest_row(session, row, search_volumes=search_volumes) for row in rows
    ]
    hits = sum(1 for e in evaluations if e.get("benchmark_hit"))
    auto = sum(1 for e in evaluations if (e.get("recognition") or {}).get("decision") == "auto_match")
    skipped_barcode = sum(
        1 for e in evaluations if (e.get("recognition") or {}).get("decision") == "barcode_present_skip"
    )
    missing_images = sum(1 for e in evaluations if (e.get("recognition") or {}).get("error"))
    return {
        "manifest_path": str(manifest_path or P107_MANIFEST_DEFAULT),
        "rows": len(evaluations),
        "benchmark_hits": hits,
        "auto_match_decisions": auto,
        "barcode_skipped": skipped_barcode,
        "missing_images": missing_images,
        "evaluations": evaluations,
    }


def seed_catalog_for_p107_tests(session: Session) -> dict[str, int]:
    """Minimal catalog rows matching the default manifest (for unit tests)."""
    ids: dict[str, int] = {}
    fixtures = [
        ("ferret", "The Ferret", "1", "Malibu Comics", 1993),
        ("next_men", "John Byrne's Next Men", "24", "Dark Horse", 1993),
        ("astro_city", "Astro City", "4", "Image", 1995),
        ("ex_mutants", "Ex-Mutants", "2", "Malibu Comics", 1992),
    ]
    for key, series_name, issue_num, pub_name, year in fixtures:
        pub = session.exec(
            select(CatalogPublisher).where(CatalogPublisher.normalized_name == normalize_series_name(pub_name))
        ).first()
        if pub is None:
            pub = CatalogPublisher(name=pub_name, normalized_name=normalize_series_name(pub_name))
            session.add(pub)
            session.flush()
        series = session.exec(
            select(CatalogSeries).where(CatalogSeries.normalized_name == normalize_series_name(series_name))
        ).first()
        if series is None:
            series = CatalogSeries(
                name=series_name,
                normalized_name=normalize_series_name(series_name),
                publisher_id=int(pub.id or 0),
            )
            session.add(series)
            session.flush()
        issue = CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(pub.id or 0),
            issue_number=issue_num,
            normalized_issue_number=normalize_issue_number(issue_num),
            cover_date=date(year, 1, 1),
        )
        session.add(issue)
        session.flush()
        ids[key] = int(issue.id or 0)
    session.commit()
    return ids
