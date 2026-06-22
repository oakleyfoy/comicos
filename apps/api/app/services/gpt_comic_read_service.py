"""Standalone GPT Comic Read tool.

A clean, independent "photo -> GPT Vision -> answer" flow. This module deliberately
imports nothing from the P100 photo-import pipeline: no sessions, detections,
candidates, catalog, fingerprints, verification, or inventory. It only talks to
OpenAI vision and returns the parsed answer.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.services.gpt_comic_identification_prompts import (
    COMIC_IDENTIFICATION_SYSTEM,
    COMIC_IDENTIFICATION_USER,
)
from app.services.gpt_comic_vision_client import ComicVisionError, call_comic_vision

logger = logging.getLogger(__name__)


class GptComicReadError(Exception):
    """Raised when the GPT Comic Read request cannot be completed."""


class GptComicReadConfigError(GptComicReadError):
    """Raised when required configuration (OpenAI key) is missing."""


class GptComicReadImageError(GptComicReadError):
    """Raised when the uploaded bytes are not a valid image."""


GPT_COMIC_READ_SYSTEM = COMIC_IDENTIFICATION_SYSTEM
GPT_COMIC_READ_USER = COMIC_IDENTIFICATION_USER


@dataclass
class GptComicReadResult:
    publisher: str
    series: str
    issue_number: str | None
    issue_title: str
    year: str
    cover_date: str
    variant_description: str
    barcode: str
    confidence: float
    reasoning: str
    model: str
    image_width: int
    image_height: int
    raw_response: dict[str, Any]
    possible_alternates: list[str] = field(default_factory=list)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def _image_dimensions(image_bytes: bytes) -> tuple[int, int, str]:
    """Return (width, height, mime) or raise GptComicReadImageError."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            fmt = (img.format or "").lower()
    except Exception as exc:  # noqa: BLE001
        raise GptComicReadImageError("Uploaded file is not a valid image") from exc
    mime = "image/png" if fmt == "png" else "image/jpeg"
    return int(width), int(height), mime


def _first_comic(payload: dict[str, Any]) -> dict[str, Any]:
    """The shared prompt returns a comics[] array; this tool only wants one book."""
    comics = payload.get("comics")
    if isinstance(comics, list):
        for item in comics:
            if isinstance(item, dict):
                return item
        return {}
    return payload


def _parse_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = _first_comic(raw_payload)
    issue_raw = payload.get("issue_number")
    issue: str | None = None
    if issue_raw is not None and str(issue_raw).strip().lower() not in {"", "null", "none", "n/a"}:
        issue = _as_str(issue_raw)
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "publisher": _as_str(payload.get("publisher")),
        "series": _as_str(payload.get("series")),
        "issue_number": issue,
        "issue_title": _as_str(payload.get("issue_title")),
        "year": _as_str(payload.get("year")),
        "cover_date": _as_str(payload.get("cover_date")),
        "variant_description": _as_str(payload.get("variant_description")),
        "barcode": _as_str(payload.get("barcode")),
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning": _as_str(payload.get("reasoning")),
        "possible_alternates": _as_str_list(payload.get("possible_alternates")),
    }


def read_comic_with_gpt(image_bytes: bytes, *, filename: str | None = None) -> GptComicReadResult:
    """Send the exact uploaded image bytes to OpenAI vision and return the parsed answer."""
    settings = get_settings()
    width, height, _mime = _image_dimensions(image_bytes)

    if not settings.openai_api_key:
        raise GptComicReadConfigError("OpenAI API key is not configured (settings.openai_api_key is empty)")

    model = settings.gpt_comic_read_model
    logger.info(
        "gpt_comic_read.request filename=%s model=%s image_bytes=%d width=%d height=%d",
        filename,
        model,
        len(image_bytes),
        width,
        height,
    )

    try:
        parsed, api_payload, _raw_text, model_used = call_comic_vision(
            image_bytes,
            model=model,
            api_key=settings.openai_api_key,
            log_context=f"gpt_comic_read filename={filename}",
        )
    except ComicVisionError as exc:
        raise GptComicReadError(str(exc)) from exc

    fields = _parse_payload(parsed)

    result = GptComicReadResult(
        model=model_used,
        image_width=width,
        image_height=height,
        raw_response={"parsed": parsed, "openai_response": api_payload, "model_used": model_used},
        **fields,
    )
    logger.info(
        "gpt_comic_read.parsed filename=%s model_used=%s series=%r issue=%r confidence=%.2f",
        filename,
        model_used,
        result.series,
        result.issue_number,
        result.confidence,
    )
    return result
