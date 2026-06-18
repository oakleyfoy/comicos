"""P100-14C cover hash similarity between upload crop and catalog cover fingerprints."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint
from app.services.catalog_fingerprint_service import fingerprint_image_path, hamming_distance, hash_match_confidence


def _best_fingerprint_similarity(
    crop_hashes: tuple[str, str, str],
    row: CatalogImageFingerprint,
) -> float:
    phash, dhash, ahash = crop_hashes
    distances: list[int] = []
    if phash and row.phash:
        distances.append(hamming_distance(phash, row.phash))
    if dhash and row.dhash:
        distances.append(hamming_distance(dhash, row.dhash))
    if ahash and row.ahash:
        distances.append(hamming_distance(ahash, row.ahash))
    if not distances:
        return 0.0
    return hash_match_confidence(min(distances)) * 100.0


def cover_similarity_score_for_issue(
    session: Session,
    *,
    crop_path: Path,
    catalog_issue_id: int,
) -> float:
    """Return 0–100 similarity between crop and catalog cover fingerprints for an issue."""
    if not crop_path.is_file():
        return 0.0
    try:
        crop_hashes = fingerprint_image_path(crop_path)
    except OSError:
        return 0.0

    image_ids = [
        int(row.id or 0)
        for row in session.exec(
            select(CatalogImage).where(CatalogImage.issue_id == catalog_issue_id).order_by(CatalogImage.id.asc())
        ).all()
        if row.id
    ]
    if not image_ids:
        return 0.0

    fingerprints = session.exec(
        select(CatalogImageFingerprint).where(CatalogImageFingerprint.issue_id == catalog_issue_id)  # type: ignore[attr-defined]
    ).all()
    if not fingerprints:
        fingerprints = session.exec(
            select(CatalogImageFingerprint).where(CatalogImageFingerprint.image_id.in_(image_ids))  # type: ignore[attr-defined]
        ).all()

    best = 0.0
    for fp in fingerprints:
        best = max(best, _best_fingerprint_similarity(crop_hashes, fp))
    return round(best, 2)
