from __future__ import annotations

from io import BytesIO

from PIL import Image
from sqlmodel import Session

from app.models.asset_ledger import CoverImageFingerprint
from app.services.cover_images import generate_perceptual_hash
from app.services.recognition.cover_matcher import score_cover_image


def _image_bytes(color: tuple[int, int, int] = (30, 120, 200)) -> bytes:
    image = Image.new("RGB", (1600, 2400), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_cover_matcher_exact_fingerprint_match(session: Session) -> None:
    image_bytes = _image_bytes()
    phash = generate_perceptual_hash(image_bytes)
    session.add(
        CoverImageFingerprint(
            cover_image_id=1,
            fingerprint_type="phash",
            fingerprint_value=phash,
            derivative_type="medium",
            image_width=1600,
            image_height=2400,
            image_sha256="feedface" * 8,
            extraction_version="test",
        )
    )
    session.commit()

    result = score_cover_image(session, image_bytes)
    assert result.confidence > 0.0
    assert result.best_fingerprint_match is not None
    assert result.best_fingerprint_match["similarity"] == 1.0


def test_cover_matcher_no_match_scores_lower(session: Session) -> None:
    image_bytes = _image_bytes((200, 40, 80))
    session.add(
        CoverImageFingerprint(
            cover_image_id=2,
            fingerprint_type="phash",
            fingerprint_value="f" * 16,
            derivative_type="medium",
            image_width=1600,
            image_height=2400,
            image_sha256="abcd" * 16,
            extraction_version="test",
        )
    )
    session.commit()

    result = score_cover_image(session, image_bytes)
    assert result.confidence < 0.95
    assert result.best_fingerprint_match is not None

