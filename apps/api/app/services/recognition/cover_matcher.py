from __future__ import annotations

import io
from collections.abc import Iterable

from PIL import Image, ImageStat, UnidentifiedImageError
from sqlmodel import Session, select

from app.models.asset_ledger import CoverImageFingerprint
from app.services.cover_images import (
    generate_average_hash,
    generate_difference_hash,
    generate_perceptual_hash,
    hamming_distance_hex,
    sha256_raw_bytes,
)
from app.services.recognition.recognition_types import RecognitionImageSignal

_FINGERPRINT_TYPES = ("phash", "ahash", "dhash")


def _similarity(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    width = min(len(left), len(right)) * 4
    if width <= 0:
        return 0.0
    distance = hamming_distance_hex(left, right)
    return round(max(0.0, min(1.0, 1.0 - (distance / width))), 6)


def _quality_confidence(image: Image.Image) -> float:
    width, height = image.width, image.height
    if width < 1 or height < 1:
        return 0.0
    aspect = max(width, height) / max(1, min(width, height))
    aspect_score = 1.0 - min(abs(aspect - 1.55) / 2.25, 1.0)
    gray = image.convert("L")
    stat = ImageStat.Stat(gray)
    contrast = 0.0
    if stat.extrema:
        contrast = (stat.extrema[0][1] - stat.extrema[0][0]) / 255.0
    return round(max(0.0, min(1.0, 0.60 * aspect_score + 0.40 * contrast)), 6)


def _iter_fingerprint_rows(session: Session) -> Iterable[CoverImageFingerprint]:
    stmt = select(CoverImageFingerprint).where(CoverImageFingerprint.fingerprint_type.in_(_FINGERPRINT_TYPES))
    return session.exec(stmt).all()


def score_cover_image(
    session: Session,
    image_bytes: bytes,
) -> RecognitionImageSignal:
    phash = generate_perceptual_hash(image_bytes)
    ahash = generate_average_hash(image_bytes)
    dhash = generate_difference_hash(image_bytes)
    sha256 = sha256_raw_bytes(image_bytes)

    best_match: dict[str, object] | None = None
    top_matches: list[dict[str, object]] = []
    fingerprint_confidence = 0.0

    for row in _iter_fingerprint_rows(session):
        candidate_hash = {
            "phash": phash,
            "ahash": ahash,
            "dhash": dhash,
        }.get(row.fingerprint_type)
        if candidate_hash is None:
            continue
        similarity = _similarity(candidate_hash, row.fingerprint_value)
        candidate = {
            "cover_image_id": int(row.cover_image_id),
            "fingerprint_type": row.fingerprint_type,
            "similarity": similarity,
            "image_sha256": row.image_sha256,
        }
        top_matches.append(candidate)
        if similarity >= fingerprint_confidence:
            fingerprint_confidence = similarity
            best_match = candidate

    top_matches.sort(key=lambda row: (-float(row["similarity"]), int(row["cover_image_id"])))
    top_matches = top_matches[:5]

    with Image.open(io.BytesIO(image_bytes)) as image:
        quality_confidence = _quality_confidence(image)

    confidence = round(
        max(
            0.0,
            min(
                1.0,
                0.60 * max(fingerprint_confidence, 0.0)
                + 0.40 * quality_confidence,
            ),
        ),
        6,
    )
    if confidence == 0.0 and (phash or ahash or dhash):
        confidence = round(min(0.35, quality_confidence), 6)

    return RecognitionImageSignal(
        sha256=sha256,
        phash=phash,
        ahash=ahash,
        dhash=dhash,
        confidence=confidence,
        best_fingerprint_match=best_match,
        top_fingerprint_matches=top_matches,
    )

