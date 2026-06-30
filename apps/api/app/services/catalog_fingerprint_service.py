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


# A genuine perceptual-hash cover match sits within ~10-12 differing bits out of 64.
# Anything looser is a coincidental layout/color collision, not the same cover.
STRONG_MATCH_MAX_DISTANCE = 12


def hash_match_confidence(distance: int, *, bits: int = 64) -> float:
    """Honest distance->confidence: 0 distance ~= 0.99, and it decays linearly to 0.

    There is no artificial floor. Previously this returned >= 0.60 for *any* image
    (even a maximally different one), which let unrelated covers surface as "91%"
    nearest neighbors. Confidence now tracks real Hamming distance.
    """
    if distance <= 0:
        return 0.99
    ratio = 1.0 - (distance / max(bits, 1))
    return max(0.0, min(0.99, ratio))


def is_strong_fingerprint_match(distance: int) -> bool:
    return 0 <= distance <= STRONG_MATCH_MAX_DISTANCE


def fingerprint_image_path(path: str | Path) -> tuple[str, str, str]:
    return _bits_from_image(Path(path))


def color_histogram_hex(path: str | Path, *, bins: int = 8) -> str:
    """Compact RGB histogram for scanner matching (8 bins per channel → 24 hex chars)."""
    with Image.open(Path(path)) as img:
        rgb = img.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
        pixels = list(rgb.getdata())
    if not pixels:
        return ""
    r_bins = [0] * bins
    g_bins = [0] * bins
    b_bins = [0] * bins
    step = 256 // bins
    for r, g, b in pixels:
        r_bins[min(bins - 1, r // max(step, 1))] += 1
        g_bins[min(bins - 1, g // max(step, 1))] += 1
        b_bins[min(bins - 1, b // max(step, 1))] += 1
    total = len(pixels)
    parts: list[str] = []
    for bucket in (r_bins, g_bins, b_bins):
        for count in bucket:
            parts.append(f"{int(count * 15 / total):x}")
    return "".join(parts)


def fingerprint_image_metadata(path: str | Path) -> dict[str, int | str]:
    p = Path(path)
    phash, dhash, ahash = fingerprint_image_path(p)
    with Image.open(p) as img:
        width, height = img.size
    file_size = p.stat().st_size
    return {
        "phash": phash,
        "dhash": dhash,
        "ahash": ahash,
        "colorhash": color_histogram_hex(p),
        "width": int(width),
        "height": int(height),
        "file_size_bytes": int(file_size),
    }


def fingerprint_catalog_image(session: Session, image_id: int, *, dry_run: bool = False) -> CatalogImageFingerprint | None:
    image = session.get(CatalogImage, image_id)
    if image is None or not image.local_path:
        return None
    path = resolve_catalog_image_local_path(session, image)
    if path is None:
        return None
    phash, dhash, ahash = fingerprint_image_path(path)
    colorhash = color_histogram_hex(path)
    if dry_run:
        return CatalogImageFingerprint(image_id=image_id, phash=phash, dhash=dhash, ahash=ahash, colorhash=colorhash)
    row = session.exec(select(CatalogImageFingerprint).where(CatalogImageFingerprint.image_id == image_id)).first()
    if row is None:
        row = CatalogImageFingerprint(
            image_id=image_id,
            issue_id=image.issue_id,
            variant_id=image.variant_id,
            phash=phash,
            dhash=dhash,
            ahash=ahash,
            colorhash=colorhash,
        )
        session.add(row)
    else:
        row.phash = phash
        row.dhash = dhash
        row.ahash = ahash
        row.colorhash = colorhash
        row.updated_at = utc_now()
        session.add(row)
    session.flush()
    return row


def _fingerprint_distance_and_confidence(
    row: CatalogImageFingerprint,
    *,
    phash: str | None,
    dhash: str | None,
    ahash: str | None,
) -> tuple[int, float] | None:
    pairs: list[tuple[str, str]] = []
    if phash and row.phash:
        pairs.append((phash, row.phash))
    if dhash and row.dhash:
        pairs.append((dhash, row.dhash))
    if ahash and row.ahash:
        pairs.append((ahash, row.ahash))
    # The extractor currently stores phash == ahash, so de-duplicate identical
    # probe/candidate pairs to keep one signal from being counted twice.
    distances: list[int] = []
    seen: set[tuple[str, str]] = set()
    for probe, candidate in pairs:
        if (probe, candidate) in seen:
            continue
        seen.add((probe, candidate))
        distances.append(hamming_distance(probe, candidate))
    if not distances:
        return None
    # Require broad agreement across the independent hashes: a true cover match is
    # close on all of them. Using the *mean* (not the best-of-N minimum) stops a
    # single coincidentally-close hash from inflating an unrelated cover.
    distance = round(sum(distances) / len(distances))
    return distance, hash_match_confidence(distance)


def _fingerprint_rows_for_phash_prefix(session: Session, phash: str, *, prefix_len: int) -> list[CatalogImageFingerprint]:
    if prefix_len <= 0:
        return list(session.exec(select(CatalogImageFingerprint).where(CatalogImageFingerprint.phash != None)))  # noqa: E711
    prefix = phash[:prefix_len]
    return list(
        session.exec(
            select(CatalogImageFingerprint).where(
                CatalogImageFingerprint.phash != None,  # noqa: E711
                CatalogImageFingerprint.phash.startswith(prefix),
            )
        )
    )


def search_similar_catalog_fingerprints(
    session: Session,
    *,
    phash: str | None = None,
    dhash: str | None = None,
    ahash: str | None = None,
    limit: int = 10,
) -> list[tuple[CatalogImageFingerprint, float, int]]:
    """Nearest-neighbor catalog fingerprint search (one row per catalog issue, best image win)."""
    if not phash and not dhash and not ahash:
        return []
    probe_phash = phash or ""
    prefix_lengths = (16, 12, 8, 0) if probe_phash else (0,)
    rows: list[CatalogImageFingerprint] = []
    for prefix_len in prefix_lengths:
        if probe_phash:
            rows = _fingerprint_rows_for_phash_prefix(session, probe_phash, prefix_len=prefix_len)
        else:
            rows = list(session.exec(select(CatalogImageFingerprint)))
        if len(rows) >= max(limit * 4, 40) or prefix_len == 0:
            break

    best_by_issue: dict[int, tuple[CatalogImageFingerprint, float, int]] = {}
    for row in rows:
        if row.issue_id is None:
            continue
        scored = _fingerprint_distance_and_confidence(row, phash=phash, dhash=dhash, ahash=ahash)
        if scored is None:
            continue
        distance, confidence = scored
        iid = int(row.issue_id)
        prev = best_by_issue.get(iid)
        if prev is None or confidence > prev[1]:
            best_by_issue[iid] = (row, confidence, distance)

    ranked = sorted(best_by_issue.values(), key=lambda item: (-item[1], item[2], int(item[0].image_id or 0)))
    return ranked[: max(1, limit)]


def find_similar_by_hash(
    session: Session,
    *,
    phash: str | None = None,
    dhash: str | None = None,
    ahash: str | None = None,
    limit: int = 10,
) -> list[tuple[CatalogImageFingerprint, float]]:
    similar = search_similar_catalog_fingerprints(
        session, phash=phash, dhash=dhash, ahash=ahash, limit=limit
    )
    return [(row, confidence) for row, confidence, _distance in similar]
