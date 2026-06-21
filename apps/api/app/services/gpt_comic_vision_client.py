"""Shared OpenAI vision call for comic identification.

Centralizes the HTTP request, high-detail image attachment, JSON parsing, and a
safe fallback: if the configured (reasoning) model is unavailable on the account,
we retry once with gpt-4o and log loudly so the flow never hard-breaks.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from app.services.gpt_comic_identification_prompts import (
    COMIC_IDENTIFICATION_SYSTEM,
    COMIC_IDENTIFICATION_USER,
)

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
FALLBACK_MODEL = "gpt-4o"


class ComicVisionError(Exception):
    """Raised when the OpenAI vision request cannot be completed."""


def mime_for_image_bytes(image_bytes: bytes) -> str:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            fmt = (img.format or "").lower()
    except Exception:  # noqa: BLE001
        return "image/jpeg"
    return "image/png" if fmt == "png" else "image/jpeg"


def _build_body(model: str, mime: str, b64: str) -> dict[str, Any]:
    return {
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


def _post(model: str, mime: str, b64: str, *, api_key: str) -> str:
    req = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=json.dumps(_build_body(model, mime, b64)).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode("utf-8")


def call_comic_vision(
    image_bytes: bytes,
    *,
    model: str,
    api_key: str,
    log_context: str = "",
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    """Return (parsed_json, openai_payload, raw_text, model_used)."""
    mime = mime_for_image_bytes(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    model_used = model
    started = time.monotonic()
    try:
        api_raw_text = _post(model, mime, b64, api_key=api_key)
    except urllib.error.HTTPError as exc:
        # Model not available / not permitted on this account -> fall back, but be loud.
        if exc.code in {400, 403, 404} and model != FALLBACK_MODEL:
            logger.warning(
                "gpt_comic_vision.model_unavailable model=%s code=%s falling_back_to=%s context=%s",
                model,
                exc.code,
                FALLBACK_MODEL,
                log_context,
            )
            model_used = FALLBACK_MODEL
            try:
                api_raw_text = _post(FALLBACK_MODEL, mime, b64, api_key=api_key)
            except urllib.error.URLError as exc2:  # noqa: BLE001
                raise ComicVisionError(f"OpenAI request failed (fallback): {exc2}") from exc2
        else:
            raise ComicVisionError(f"OpenAI request failed: {exc}") from exc
    except urllib.error.URLError as exc:  # noqa: BLE001
        raise ComicVisionError(f"OpenAI request failed: {exc}") from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)

    api_payload = json.loads(api_raw_text)
    content = api_payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        parsed = {}
    logger.info(
        "gpt_comic_vision.response model_used=%s elapsed_ms=%d context=%s",
        model_used,
        elapsed_ms,
        log_context,
    )
    return parsed, api_payload, api_raw_text, model_used
