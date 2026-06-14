from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_fingerprint_service import find_similar_by_hash, fingerprint_image_path, hamming_distance

CATALOG_FINGERPRINT_VERIFIED_THRESHOLD = 0.95


@dataclass(frozen=True)
class CatalogFingerprintMatch:
    issue_id: int
    image_id: int
    confidence: float
    min_hamming_distance: int


@dataclass(frozen=True)
class CatalogIssueIdentity:
    catalog_issue_id: int
    series: str
    issue_number: str
    publisher: str | None
    cover_image_url: str | None


def _probe_bitstring_hashes(image_bytes: bytes) -> tuple[str, str, str]:
    with tempfile.TemporaryDirectory(prefix="recognition-catalog-fp-") as tmpdir:
        path = Path(tmpdir) / "probe.jpg"
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.convert("RGB").save(path, format="JPEG")
        return fingerprint_image_path(path)


def search_catalog_fingerprint_matches(
    session: Session,
    image_bytes: bytes,
    *,
    limit: int = 10,
) -> list[CatalogFingerprintMatch]:
    phash, dhash, ahash = _probe_bitstring_hashes(image_bytes)
    similar = find_similar_by_hash(session, phash=phash, dhash=dhash, ahash=ahash, limit=limit)
    matches: list[CatalogFingerprintMatch] = []
    for row, confidence in similar:
        if row.issue_id is None:
            continue
        distances = []
        if phash and row.phash:
            distances.append(hamming_distance(phash, row.phash))
        if dhash and row.dhash:
            distances.append(hamming_distance(dhash, row.dhash))
        if ahash and row.ahash:
            distances.append(hamming_distance(ahash, row.ahash))
        min_dist = min(distances) if distances else 64
        matches.append(
            CatalogFingerprintMatch(
                issue_id=int(row.issue_id),
                image_id=int(row.image_id),
                confidence=float(confidence),
                min_hamming_distance=min_dist,
            )
        )
    return matches


def load_catalog_issue_identity(session: Session, catalog_issue_id: int) -> CatalogIssueIdentity | None:
    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is None:
        return None
    series = session.get(CatalogSeries, issue.series_id)
    publisher: CatalogPublisher | None = None
    if issue.publisher_id is not None:
        publisher = session.get(CatalogPublisher, issue.publisher_id)
    elif series is not None and series.publisher_id is not None:
        publisher = session.get(CatalogPublisher, series.publisher_id)

    cover_url: str | None = None
    image = session.exec(
        select(CatalogImage)
        .where(CatalogImage.issue_id == catalog_issue_id, CatalogImage.image_type == "cover")
        .order_by(CatalogImage.id)
    ).first()
    if image is not None:
        if image.source_url and str(image.source_url).strip():
            cover_url = str(image.source_url).strip()
        elif image.local_path and str(image.local_path).strip():
            cover_url = str(image.local_path).strip()

    return CatalogIssueIdentity(
        catalog_issue_id=int(issue.id),
        series=series.name if series is not None else "Unknown",
        issue_number=str(issue.issue_number),
        publisher=publisher.name if publisher is not None else None,
        cover_image_url=cover_url,
    )
