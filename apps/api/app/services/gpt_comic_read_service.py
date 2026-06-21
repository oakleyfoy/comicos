"""Standalone GPT Comic Read tool.

A clean, independent "photo -> GPT Vision -> answer" flow. This module deliberately
imports nothing from the P100 photo-import pipeline: no sessions, detections,
candidates, catalog, fingerprints, verification, or inventory. It only talks to
OpenAI vision and returns the parsed answer.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.services.gpt_comic_identification_prompts import (
    COMIC_IDENTIFICATION_SYSTEM,
    COMIC_IDENTIFICATION_USER,
)

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


def _parse_payload(payload: dict[str, Any]) -> dict[str, Any]:
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
    import urllib.error
    import urllib.request

    settings = get_settings()
    width, height, mime = _image_dimensions(image_bytes)

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

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": COMIC_IDENTIFICATION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": COMIC_IDENTIFICATION_USER},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                    },
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            api_raw_text = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:  # noqa: BLE001
        raise GptComicReadError(f"OpenAI request failed: {exc}") from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)

    api_payload = json.loads(api_raw_text)
    content = api_payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    fields = _parse_payload(parsed if isinstance(parsed, dict) else {})

    result = GptComicReadResult(
        model=model,
        image_width=width,
        image_height=height,
        raw_response={"parsed": parsed, "openai_response": api_payload},
        **fields,
    )
    logger.info(
        "gpt_comic_read.parsed filename=%s elapsed_ms=%d series=%r issue=%r confidence=%.2f",
        filename,
        elapsed_ms,
        result.series,
        result.issue_number,
        result.confidence,
    )
    return result
