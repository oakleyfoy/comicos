from __future__ import annotations

from pathlib import Path

from PIL import Image
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint, utc_now
from app.services.catalog_cover_harvest_service import resolve_catalog_image_local_path


def _bits_from_image(path: Path, *, hash_size: int = 8) -> tuple[str, str, str]:
    with Image.open(path) as img:
        gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())

    # Average hash
    avg = sum(pixels[: hash_size * hash_size]) / (hash_size * hash_size)
    ahash_bits = "".join("1" if px >= avg else "0" for px in pixels[: hash_size * hash_size])

    # Difference hash (horizontal gradients)
    dhash_bits = ""
    for row in range(hash_size):
        for col in range(hash_size):
            left = gray.getpixel((col, row))
            right = gray.getpixel((col + 1, row))
            dhash_bits += "1" if left > right else "0"

    # Perceptual hash (DCT-free simplified: compare to block mean)
    phash_bits = ahash_bits

    return phash_bits, dhash_bits, ahash_bits


def hamming_distance(left: str, right: str) -> int:
    if not left or not right:
        return 64
    length = min(len(left), len(right))
    return sum(1 for i in range(length) if left[i] != right[i]) + abs(len(left) - len(right))


def hash_match_confidence(distance: int, *, bits: int = 64) -> float:
    if distance <= 0:
        return 0.98
    ratio = 1.0 - (distance / max(bits, 1))
    return max(0.0, min(0.97, 0.6 + ratio * 0.37))


def fingerprint_image_path(path: str | Path) -> tuple[str, str, str]:
    return _bits_from_image(Path(path))


def fingerprint_catalog_image(session: Session, image_id: int, *, dry_run: bool = False) -> CatalogImageFingerprint | None:
    image = session.get(CatalogImage, image_id)
    if image is None or not image.local_path:
        return None
    path = resolve_catalog_image_local_path(session, image)
    if path is None:
        return None
    phash, dhash, ahash = fingerprint_image_path(path)
    if dry_run:
        return CatalogImageFingerprint(image_id=image_id, phash=phash, dhash=dhash, ahash=ahash)
    row = session.exec(select(CatalogImageFingerprint).where(CatalogImageFingerprint.image_id == image_id)).first()
    if row is None:
        row = CatalogImageFingerprint(
            image_id=image_id,
            issue_id=image.issue_id,
            variant_id=image.variant_id,
            phash=phash,
            dhash=dhash,
            ahash=ahash,
        )
        session.add(row)
    else:
        row.phash = phash
        row.dhash = dhash
        row.ahash = ahash
        row.updated_at = utc_now()
        session.add(row)
    session.flush()
    return row


def find_similar_by_hash(
    session: Session,
    *,
    phash: str | None = None,
    dhash: str | None = None,
    ahash: str | None = None,
    limit: int = 10,
) -> list[tuple[CatalogImageFingerprint, float]]:
    rows = session.exec(select(CatalogImageFingerprint)).all()
    scored: list[tuple[CatalogImageFingerprint, float]] = []
    for row in rows:
        distances = []
        if phash and row.phash:
            distances.append(hamming_distance(phash, row.phash))
        if dhash and row.dhash:
            distances.append(hamming_distance(dhash, row.dhash))
        if ahash and row.ahash:
            distances.append(hamming_distance(ahash, row.ahash))
        if not distances:
            continue
        distance = min(distances)
        confidence = hash_match_confidence(distance)
        scored.append((row, confidence))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[: max(1, limit)]
