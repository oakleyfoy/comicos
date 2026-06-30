"""P100-14D fingerprint matching for photo import crops vs catalog_image_fingerprint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from app.models.catalog_master import CatalogImageFingerprint
from app.services.catalog_fingerprint_service import (
    fingerprint_image_path,
    hamming_distance,
    hash_match_confidence,
    search_similar_catalog_fingerprints,
)


@dataclass(frozen=True)
class FingerprintCatalogHit:
    issue_id: int
    score: float
    confidence: float
    min_hamming_distance: int


def fingerprint_hashes_for_crop(crop_path: Path) -> tuple[str, str, str] | None:
    if not crop_path.is_file():
        return None
    try:
        return fingerprint_image_path(crop_path)
    except OSError:
        return None


def fingerprint_match_score_for_issue(
    session: Session,
    *,
    crop_hashes: tuple[str, str, str],
    catalog_issue_id: int,
) -> float:
    """Return 0–100 fingerprint match score for a catalog issue (stronger signal than text-only)."""
    phash, dhash, ahash = crop_hashes
    rows = session.exec(
        select(CatalogImageFingerprint).where(CatalogImageFingerprint.issue_id == catalog_issue_id)  # type: ignore[attr-defined]
    ).all()
    if not rows:
        return 0.0
    best = 0.0
    for row in rows:
        distances: list[int] = []
        if phash and row.phash:
            distances.append(hamming_distance(phash, row.phash))
        if dhash and row.dhash:
            distances.append(hamming_distance(dhash, row.dhash))
        if ahash and row.ahash:
            distances.append(hamming_distance(ahash, row.ahash))
        if distances:
            best = max(best, hash_match_confidence(min(distances)) * 100.0)
    return round(best, 2)


def fingerprint_match_score_for_crop_path(
    session: Session,
    *,
    crop_path: Path,
    catalog_issue_id: int,
) -> float:
    hashes = fingerprint_hashes_for_crop(crop_path)
    if hashes is None:
        return 0.0
    return fingerprint_match_score_for_issue(session, crop_hashes=hashes, catalog_issue_id=catalog_issue_id)


def search_catalog_fingerprint_hits_for_crop_path(
    session: Session,
    *,
    crop_path: Path,
    limit: int = 10,
) -> list[FingerprintCatalogHit]:
    """Global catalog fingerprint search for a photo crop (E1)."""
    from app.services.intake_fingerprint_search_debug_service import execute_catalog_fingerprint_search

    return execute_catalog_fingerprint_search(session, crop_path=crop_path, limit=limit)
