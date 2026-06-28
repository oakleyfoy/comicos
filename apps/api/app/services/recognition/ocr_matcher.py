from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, UnidentifiedImageError

LOGGER = logging.getLogger(__name__)

from app.services.cover_images import (
    KNOWN_PUBLISHERS,
    _run_tesseract_ocr_with_test_compat,
    get_tesseract_engine_version,
    normalize_ocr_text,
)
from app.services.recognition.recognition_types import RecognitionOCRSignal

_ISSUE_PATTERN = re.compile(r"(?:^|[^0-9A-Za-z])(?:#\s*)?(\d{1,4}[A-Za-z]?)\b")
_COVER_LABEL_PATTERN = re.compile(r"\bcover\s+([a-z0-9]{1,2})\b", re.IGNORECASE)
_VARIANT_PATTERN = re.compile(r"\bvariant\b", re.IGNORECASE)


def _publisher_from_text(lines: list[str]) -> str | None:
    upper_lines = [line.upper() for line in lines if line.strip()]
    for token in KNOWN_PUBLISHERS:
        token_upper = token.upper()
        if any(token_upper in line for line in upper_lines):
            if token_upper == "DC COMICS":
                return "DC"
            if token_upper == "IMAGE COMICS":
                return "Image"
            return token.title() if token.isupper() else token
    return None


def _issue_number_from_text(lines: list[str]) -> str | None:
    for line in lines:
        match = _ISSUE_PATTERN.search(line)
        if match:
            value = match.group(1).strip()
            if value.isdigit() or (value[:-1].isdigit() and value[-1].isalpha()):
                return value.lstrip("#")
    return None


def _variant_from_text(lines: list[str]) -> str | None:
    joined = " ".join(lines)
    cover = _COVER_LABEL_PATTERN.search(joined)
    if cover:
        return f"Cover {cover.group(1).upper()}"
    if _VARIANT_PATTERN.search(joined):
        return "Variant"
    return None


def _title_from_text(lines: list[str], *, issue_number: str | None, publisher: str | None) -> str | None:
    if not lines:
        return None
    blacklist = {"variant", "cover", "comic", "comics", "special", "edition", "issue"}
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if publisher and publisher.lower() in lowered:
            continue
        if issue_number and issue_number.lower() in lowered:
            continue
        if any(token in lowered for token in blacklist) and len(cleaned.split()) <= 2:
            continue
        if len(cleaned) >= 3:
            return cleaned
    return None


def _ocr_confidence(raw_text: str, *, title: str | None, issue_number: str | None, publisher: str | None, variant: str | None) -> float:
    base = 0.0
    if raw_text.strip():
        base += min(0.40, len(raw_text.strip()) / 140.0)
    if title:
        base += 0.28
    if issue_number:
        base += 0.15
    if publisher:
        base += 0.10
    if variant:
        base += 0.07
    return round(max(0.0, min(base, 1.0)), 6)


OCR_UNAVAILABLE_MESSAGE = "Local Tesseract OCR engine is unavailable on this host."


def _empty_ocr_signal(
    *,
    ocr_engine_available: bool = True,
    ocr_error: str | None = None,
) -> RecognitionOCRSignal:
    """OCR-unavailable fallback so recognition can still use image/fingerprint signals."""
    return RecognitionOCRSignal(
        raw_text="",
        normalized_text=None,
        title=None,
        issue_number=None,
        publisher=None,
        variant=None,
        confidence=0.0,
        ocr_engine_available=ocr_engine_available,
        ocr_error=ocr_error,
    )


def extract_ocr_signal(image_bytes: bytes, *, source_name: str = "upload") -> RecognitionOCRSignal:
    try:
        with TemporaryDirectory(prefix="recognition-ocr-") as tmpdir:
            temp_path = Path(tmpdir) / f"{source_name}.png"
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.save(temp_path, format="PNG")
            raw_text = _run_tesseract_ocr_with_test_compat(temp_path, timeout_seconds=15.0)
    except (ValueError, OSError, UnidentifiedImageError) as exc:
        # OCR is a best-effort signal. When the Tesseract engine is unavailable,
        # times out, or the image cannot be rasterized, degrade gracefully to an
        # empty OCR signal rather than failing the whole recognition request.
        LOGGER.warning("recognition OCR skipped source=%r reason=%s", source_name, str(exc)[:300])
        msg = str(exc)
        if isinstance(exc, OSError) or OCR_UNAVAILABLE_MESSAGE in msg:
            return _empty_ocr_signal(
                ocr_engine_available=False,
                ocr_error=OCR_UNAVAILABLE_MESSAGE,
            )
        return _empty_ocr_signal()

    normalized_text = normalize_ocr_text(raw_text)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines and normalized_text:
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]

    publisher = _publisher_from_text(lines)
    issue_number = _issue_number_from_text(lines)
    variant = _variant_from_text(lines)
    title = _title_from_text(lines, issue_number=issue_number, publisher=publisher)
    confidence = _ocr_confidence(raw_text, title=title, issue_number=issue_number, publisher=publisher, variant=variant)
    return RecognitionOCRSignal(
        raw_text=raw_text,
        normalized_text=normalized_text,
        title=title,
        issue_number=issue_number,
        publisher=publisher,
        variant=variant,
        confidence=confidence,
        ocr_engine_available=True,
        ocr_error=None,
    )


def is_valid_comic_image(image_bytes: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.width > 0 and image.height > 0
    except (UnidentifiedImageError, OSError, ValueError):
        return False

