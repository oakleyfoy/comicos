"""Intake/P106.1 fingerprint search logging, debug bundles, and cross-publisher guardrails."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from sqlmodel import Session

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint
from app.services.barcode_validation_service import effective_publisher_for_barcode
from app.services.catalog_cover_harvest_service import resolve_catalog_image_local_path
from app.services.catalog_fingerprint_service import (
    color_histogram_hex,
    fingerprint_image_path,
    hamming_distance,
    hash_match_confidence,
    search_similar_catalog_fingerprints,
)
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id
from app.services.photo_import_fingerprint_service import FingerprintCatalogHit
from app.services.photo_import_storage_service import REPO_ROOT
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)


def _comicvine_id_keys(external: dict | None) -> tuple[str, ...]:
    if not isinstance(external, dict):
        return ()
    bucket = external.get("COMICVINE")
    if not isinstance(bucket, dict):
        return ()
    return tuple(sorted(str(k) for k in bucket if str(k).isdigit()))


LOG_TAG = "FINGERPRINT_SEARCH_DEBUG"
BUNDLE_MATCH_LIMIT = 10
SEARCH_DETAIL_LIMIT = 20

_active_ctx: ContextVar["FingerprintSearchDebugContext | None"] = ContextVar(
    "intake_fingerprint_search_debug_ctx",
    default=None,
)


@dataclass
class FingerprintSearchDebugContext:
    intake_item_id: int | None = None
    barcode: str | None = None
    fingerprint_image_region: str | None = None
    fingerprint_region_safe: bool | None = None


@contextmanager
def fingerprint_search_debug_context(ctx: FingerprintSearchDebugContext) -> Iterator[None]:
    token = _active_ctx.set(ctx)
    try:
        yield
    finally:
        _active_ctx.reset(token)


def get_fingerprint_search_debug_context() -> FingerprintSearchDebugContext | None:
    return _active_ctx.get()


def fingerprint_debug_bundle_dir(intake_item_id: int) -> Path:
    return REPO_ROOT / "data" / "debug" / "fingerprint" / f"item_{int(intake_item_id)}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _histogram_score(query_hex: str, candidate_hex: str) -> float:
    if not query_hex or not candidate_hex:
        return 0.0
    n = min(len(query_hex), len(candidate_hex))
    if n == 0:
        return 0.0
    matches = sum(1 for i in range(n) if query_hex[i] == candidate_hex[i])
    return round(matches / n, 4)


def _dominant_score_component(*, phash_d: int, dhash_d: int, ahash_d: int) -> str:
    pairs = [("phash", phash_d), ("dhash", dhash_d), ("ahash", ahash_d)]
    pairs.sort(key=lambda x: x[1])
    return pairs[0][0]


def _match_detail_row(
    session: Session,
    *,
    rank: int,
    fp_row: CatalogImageFingerprint,
    confidence: float,
    phash: str,
    dhash: str,
    ahash: str,
    query_colorhash: str,
) -> dict[str, Any]:
    phash_d = hamming_distance(phash, fp_row.phash or "") if fp_row.phash else 64
    dhash_d = hamming_distance(dhash, fp_row.dhash or "") if fp_row.dhash else 64
    ahash_d = hamming_distance(ahash, fp_row.ahash or "") if fp_row.ahash else 64
    hist = _histogram_score(query_colorhash, str(fp_row.colorhash or ""))
    issue_id = int(fp_row.issue_id or 0)
    identity = load_catalog_issue_identity(session, issue_id) if issue_id else None
    from app.models.catalog_master import CatalogIssue

    issue = session.get(CatalogIssue, issue_id) if issue_id else None
    cover_path: str | None = None
    source_url: str | None = None
    if fp_row.image_id:
        image = session.get(CatalogImage, int(fp_row.image_id))
        if image is not None:
            source_url = image.source_url
            local = resolve_catalog_image_local_path(session, image)
            if local is not None:
                cover_path = str(local)
    gcd_id = extract_gcd_issue_id(issue.external_source_ids) if issue else None
    cv_ids = list(_comicvine_id_keys(issue.external_source_ids if issue else None))
    dominant = _dominant_score_component(phash_d=phash_d, dhash_d=dhash_d, ahash_d=ahash_d)
    return {
        "rank": rank,
        "catalog_issue_id": issue_id,
        "series": identity.series if identity else None,
        "title": (issue.title if issue else None) or (identity.series if identity else None),
        "issue_number": identity.issue_number if identity else None,
        "publisher": identity.publisher if identity else None,
        "source": "catalog_fingerprint",
        "source_url": source_url,
        "cover_path": cover_path,
        "gcd_issue_id": gcd_id,
        "comicvine_issue_id": cv_ids[0] if cv_ids else None,
        "phash_distance": phash_d,
        "ahash_distance": ahash_d,
        "dhash_distance": dhash_d,
        "histogram_score": hist,
        "final_score": round(confidence * 100.0, 2),
        "confidence": round(float(confidence), 4),
        "dominant_score_component": dominant,
        "catalog_image_id": fp_row.image_id,
    }


def build_fingerprint_search_details(
    session: Session,
    *,
    crop_path: Path,
    limit: int = SEARCH_DETAIL_LIMIT,
) -> tuple[list[FingerprintCatalogHit], dict[str, Any], list[dict[str, Any]]]:
    if not crop_path.is_file():
        return [], {}, []
    try:
        phash, dhash, ahash = fingerprint_image_path(crop_path)
    except OSError:
        return [], {}, []
    query_colorhash = color_histogram_hex(crop_path)
    from PIL import Image

    with Image.open(crop_path) as img:
        width, height = img.size
    summary: dict[str, Any] = {
        "fingerprint_image_path": str(crop_path.resolve()),
        "image_width": int(width),
        "image_height": int(height),
        "sha256": _sha256_file(crop_path),
        "phash": phash,
        "ahash": ahash,
        "dhash": dhash,
        "color_histogram": query_colorhash,
        "top_20_match_count": 0,
    }
    similar = search_similar_catalog_fingerprints(
        session, phash=phash, dhash=dhash, ahash=ahash, limit=limit
    )
    summary["top_20_match_count"] = len(similar)
    hits: list[FingerprintCatalogHit] = []
    details: list[dict[str, Any]] = []
    for idx, (row, confidence, distance) in enumerate(similar, start=1):
        if row.issue_id is None:
            continue
        hits.append(
            FingerprintCatalogHit(
                issue_id=int(row.issue_id),
                score=round(confidence * 100.0, 2),
                confidence=float(confidence),
                min_hamming_distance=int(distance),
            )
        )
        details.append(
            _match_detail_row(
                session,
                rank=idx,
                fp_row=row,
                confidence=confidence,
                phash=phash,
                dhash=dhash,
                ahash=ahash,
                query_colorhash=query_colorhash,
            )
        )
    return hits, summary, details


def log_fingerprint_search_debug(*, ctx: FingerprintSearchDebugContext, summary: dict[str, Any], matches: list[dict[str, Any]]) -> None:
    payload = {
        "intake_item_id": ctx.intake_item_id,
        "barcode": ctx.barcode,
        "fingerprint_image_region": ctx.fingerprint_image_region,
        "fingerprint_region_safe": ctx.fingerprint_region_safe,
        **summary,
        "matches": matches,
    }
    logger.info("%s %s", LOG_TAG, json.dumps(payload, default=str))


def write_fingerprint_search_debug_bundle(
    *,
    crop_path: Path,
    intake_item_id: int,
    summary: dict[str, Any],
    matches: list[dict[str, Any]],
) -> Path:
    root = fingerprint_debug_bundle_dir(intake_item_id)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(crop_path, root / "search_image.jpg")
    bundle = {"search": summary, "matches": matches}
    (root / "search_fingerprint.json").write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    for idx, match in enumerate(matches[:BUNDLE_MATCH_LIMIT], start=1):
        tag = f"{idx:02d}"
        (root / f"match_{tag}.json").write_text(json.dumps(match, indent=2, default=str), encoding="utf-8")
        cover = match.get("cover_path")
        if cover and Path(str(cover)).is_file():
            try:
                shutil.copy2(Path(str(cover)), root / f"match_{tag}.jpg")
            except OSError:
                pass
    return root


def execute_catalog_fingerprint_search(
    session: Session,
    *,
    crop_path: Path,
    limit: int = 10,
) -> list[FingerprintCatalogHit]:
    hits, summary, details = build_fingerprint_search_details(
        session, crop_path=crop_path, limit=SEARCH_DETAIL_LIMIT
    )
    ctx = get_fingerprint_search_debug_context()
    if ctx is not None:
        log_fingerprint_search_debug(ctx=ctx, summary=summary, matches=details)
        bundle_id = ctx.intake_item_id
    else:
        logger.info(
            "%s %s",
            LOG_TAG,
            json.dumps({"search": summary, "top_20_match_count": summary.get("top_20_match_count"), "matches": details}, default=str),
        )
        bundle_id = None
    if bundle_id is not None:
        write_fingerprint_search_debug_bundle(
            crop_path=crop_path,
            intake_item_id=int(bundle_id),
            summary=summary,
            matches=details,
        )
    return hits[: max(1, limit)]


def publishers_cross_conflict(*, barcode_publisher: str | None, catalog_publisher: str | None) -> bool:
    if not barcode_publisher or not catalog_publisher:
        return False
    left = normalize_series_name(barcode_publisher)
    right = normalize_series_name(catalog_publisher)
    if not left or not right:
        return False
    return left != right


def filter_cross_publisher_fingerprint_review_rows(
    *,
    barcode: str,
    rows: list[dict[str, Any]],
    hints_publisher: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Drop visual candidates that conflict with barcode-encoded publisher."""
    barcode_pub = effective_publisher_for_barcode(barcode, hints_publisher)
    if not barcode_pub:
        return rows, None
    kept: list[dict[str, Any]] = []
    for row in rows:
        if publishers_cross_conflict(barcode_publisher=barcode_pub, catalog_publisher=row.get("publisher")):
            continue
        kept.append(row)
    if kept:
        return kept, None
    if rows:
        return [], "cross_publisher_visual_mismatch"
    return [], None


def filter_cross_publisher_fingerprint_recovery_candidates(
    session: Session,
    *,
    barcode: str,
    candidates: list[Any],
    hints_publisher: str | None = None,
) -> tuple[list[Any], str | None]:
    from app.models.catalog_master import CatalogIssue, CatalogPublisher

    barcode_pub = effective_publisher_for_barcode(barcode, hints_publisher)
    if not barcode_pub:
        return candidates, None
    kept = []
    for cand in candidates:
        pub = getattr(cand, "publisher", None)
        if pub is None and getattr(cand, "catalog_issue_id", None):
            issue = session.get(CatalogIssue, int(cand.catalog_issue_id))
            if issue and issue.publisher_id:
                pub_row = session.get(CatalogPublisher, int(issue.publisher_id))
                pub = pub_row.name if pub_row else None
        if publishers_cross_conflict(barcode_publisher=barcode_pub, catalog_publisher=pub):
            continue
        kept.append(cand)
    if kept:
        return kept, None
    if candidates:
        return [], "cross_publisher_visual_mismatch"
    return [], None
