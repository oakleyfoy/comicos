"""Shared OpenAI vision call for comic identification.

Centralizes the HTTP request, image prep, JSON parsing, optional streaming, and a
safe fallback: if the configured model is unavailable on the account, we retry once
with gpt-4o and log loudly so the flow never hard-breaks.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import httpx

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


def prepare_image_bytes_for_vision(image_bytes: bytes, *, max_side_px: int) -> bytes:
    """Downscale large phone photos before the API call (major latency win)."""
    if max_side_px <= 0:
        return image_bytes
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest <= max_side_px:
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=88, optimize=True)
                return out.getvalue()
            scale = max_side_px / float(longest)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            resized = img.resize(new_size, Image.Resampling.LANCZOS)
            out = io.BytesIO()
            resized.save(out, format="JPEG", quality=88, optimize=True)
            return out.getvalue()
    except Exception:  # noqa: BLE001
        logger.warning("gpt_comic_vision.prepare_image_failed bytes=%d", len(image_bytes))
        return image_bytes


def _build_body(
    model: str,
    mime: str,
    b64: str,
    *,
    system: str,
    user: str,
    image_detail: str,
    stream: bool,
) -> dict[str, Any]:
    detail = image_detail if image_detail in {"low", "high", "auto"} else "auto"
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}", "detail": detail},
                    },
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }
    if stream:
        body["stream"] = True
    return body


def _post(model: str, body: dict[str, Any], *, api_key: str, timeout_seconds: float = 180.0) -> str:
    req = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read().decode("utf-8")


def _parse_message_content(api_raw_text: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    api_payload = json.loads(api_raw_text)
    content = api_payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        parsed = {}
    return parsed, api_payload, content


def call_comic_vision(
    image_bytes: bytes,
    *,
    model: str,
    api_key: str,
    log_context: str = "",
    system: str | None = None,
    user: str | None = None,
    image_detail: str = "high",
    max_image_side_px: int | None = None,
    timeout_seconds: float = 180.0,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    """Return (parsed_json, openai_payload, raw_text, model_used)."""
    from app.services.gpt_comic_identification_prompts import (
        COMIC_IDENTIFICATION_SYSTEM,
        COMIC_IDENTIFICATION_USER,
    )

    sys_prompt = system or COMIC_IDENTIFICATION_SYSTEM
    user_prompt = user or COMIC_IDENTIFICATION_USER
    prepared = image_bytes
    if max_image_side_px:
        prepared = prepare_image_bytes_for_vision(image_bytes, max_side_px=max_image_side_px)
    mime = mime_for_image_bytes(prepared)
    b64 = base64.standard_b64encode(prepared).decode("ascii")
    model_used = model
    body = _build_body(
        model,
        mime,
        b64,
        system=sys_prompt,
        user=user_prompt,
        image_detail=image_detail,
        stream=False,
    )
    started = time.monotonic()
    try:
        api_raw_text = _post(model, body, api_key=api_key, timeout_seconds=timeout_seconds)
    except urllib.error.HTTPError as exc:
        if exc.code in {400, 403, 404} and model != FALLBACK_MODEL:
            logger.warning(
                "gpt_comic_vision.model_unavailable model=%s code=%s falling_back_to=%s context=%s",
                model,
                exc.code,
                FALLBACK_MODEL,
                log_context,
            )
            model_used = FALLBACK_MODEL
            body["model"] = FALLBACK_MODEL
            try:
                api_raw_text = _post(FALLBACK_MODEL, body, api_key=api_key, timeout_seconds=timeout_seconds)
            except urllib.error.URLError as exc2:  # noqa: BLE001
                raise ComicVisionError(f"OpenAI request failed (fallback): {exc2}") from exc2
        else:
            raise ComicVisionError(f"OpenAI request failed: {exc}") from exc
    except urllib.error.URLError as exc:  # noqa: BLE001
        raise ComicVisionError(f"OpenAI request failed: {exc}") from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    parsed, api_payload, content = _parse_message_content(api_raw_text)
    logger.info(
        "gpt_comic_vision.response model_used=%s elapsed_ms=%d bytes_in=%d bytes_prepared=%d context=%s",
        model_used,
        elapsed_ms,
        len(image_bytes),
        len(prepared),
        log_context,
    )
    return parsed, api_payload, content, model_used


def stream_comic_vision_text(
    image_bytes: bytes,
    *,
    model: str,
    api_key: str,
    log_context: str = "",
    system: str | None = None,
    user: str | None = None,
    image_detail: str = "low",
    max_image_side_px: int | None = None,
) -> Iterator[str]:
    """Yield incremental text deltas from a streaming OpenAI vision completion."""
    from app.services.gpt_comic_identification_prompts import (
        COMIC_IDENTIFICATION_QUICK_SYSTEM,
        COMIC_IDENTIFICATION_QUICK_USER,
    )

    sys_prompt = system or COMIC_IDENTIFICATION_QUICK_SYSTEM
    user_prompt = user or COMIC_IDENTIFICATION_QUICK_USER
    prepared = image_bytes
    if max_image_side_px:
        prepared = prepare_image_bytes_for_vision(image_bytes, max_side_px=max_image_side_px)
    mime = mime_for_image_bytes(prepared)
    b64 = base64.standard_b64encode(prepared).decode("ascii")
    body = _build_body(
        model,
        mime,
        b64,
        system=sys_prompt,
        user=user_prompt,
        image_detail=image_detail,
        stream=True,
    )
    started = time.monotonic()
    model_used = model
    with httpx.Client(timeout=180.0) as client:
        try:
            with client.stream(
                "POST",
                OPENAI_CHAT_URL,
                json=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            ) as response:
                if response.status_code in {400, 403, 404} and model != FALLBACK_MODEL:
                    logger.warning(
                        "gpt_comic_vision.stream_model_unavailable model=%s status=%s fallback=%s context=%s",
                        model,
                        response.status_code,
                        FALLBACK_MODEL,
                        log_context,
                    )
                    model_used = FALLBACK_MODEL
                    body["model"] = FALLBACK_MODEL
                    yield from _stream_with_httpx(body, api_key=api_key)
                else:
                    response.raise_for_status()
                    yield from _iter_sse_content_deltas(response)
        except httpx.HTTPError as exc:
            raise ComicVisionError(f"OpenAI stream failed: {exc}") from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "gpt_comic_vision.stream_complete model_used=%s elapsed_ms=%d context=%s",
        model_used,
        elapsed_ms,
        log_context,
    )


def _stream_with_httpx(body: dict[str, Any], *, api_key: str) -> Iterator[str]:
    with httpx.Client(timeout=180.0) as client:
        with client.stream(
            "POST",
            OPENAI_CHAT_URL,
            json=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        ) as response:
            response.raise_for_status()
            yield from _iter_sse_content_deltas(response)


def _iter_sse_content_deltas(response: httpx.Response) -> Iterator[str]:
    for line in response.iter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        text = delta.get("content")
        if text:
            yield str(text)


def parse_streamed_json_content(full_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(full_text)
    except json.JSONDecodeError as exc:
        raise ComicVisionError(f"OpenAI returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        return {}
    return parsed
