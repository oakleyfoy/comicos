"""Bounded execution helpers + image byte guards for the cover OCR pipeline."""

from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable, TypeVar

from app.core.config import Settings

_PIPELINE_PIL_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

_PIPELINE_MIME_TO_SUFFIX = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

T = TypeVar("T")


class PipelineStepTimeout(RuntimeError):
    """Raised when a bounded worker-thread step exceeds its deadline."""


def run_with_thread_deadline(seconds: float, fn: Callable[[], T], *, stage: str) -> T:
    """Run ``fn`` in a single worker thread with a deadline (best-effort; see stdlib caveats).

    Used for Pillow-heavy steps where subprocess timeouts are unavailable. Not suitable for SQLite
    sessions bound to another thread.
    """

    if seconds <= 0:
        return fn()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=seconds)
        except FutureTimeoutError as exc:
            raise PipelineStepTimeout(f"{stage} timed out.") from exc


def validate_pipeline_image_bytes(
    *,
    settings: Settings,
    body: bytes,
    mime_type: str | None,
    declared_width: int | None = None,
    declared_height: int | None = None,
    stage: str,
) -> tuple[int, int, str]:
    """Fail fast on oversize payloads, unreadable decode, dims, unsupported mime."""
    max_bytes = int(settings.cover_pipeline_max_image_bytes)
    if len(body) > max_bytes:
        raise ValueError(
            f"Cover image oversized: {len(body)} bytes exceeds max file bytes ({max_bytes})."
        )

    from PIL import Image, UnidentifiedImageError

    inferred_mime = None
    width = declared_width
    height = declared_height
    try:
        with Image.open(io.BytesIO(body)) as img:
            fmt = (img.format or "").upper()
            inferred_mime = _PIPELINE_PIL_FORMAT_TO_MIME.get(fmt)
            width = int(width or img.width)
            height = int(height or img.height)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Cover image corrupt or unreadable.") from exc

    normalized_mime = (mime_type or inferred_mime or "").split(";")[0].strip().lower() or None
    if normalized_mime and normalized_mime not in _PIPELINE_MIME_TO_SUFFIX:
        normalized_mime = None
    effective_mime = normalized_mime or inferred_mime
    if effective_mime is None or effective_mime not in _PIPELINE_MIME_TO_SUFFIX:
        raise ValueError("Unsupported MIME type for cover pipeline processing.")

    max_pixels = settings.cover_pipeline_max_image_pixels
    if width > 0 and height > 0 and width * height > max_pixels:
        raise ValueError(
            f"Cover dimensions exceed limit ({width}x{height} exceeds {max_pixels} pixels)."
        )
    max_side = settings.cover_pipeline_max_image_side_px
    if width > max_side or height > max_side:
        raise ValueError(
            f"Cover longest side exceeds limit ({width}x{height}; max_side={max_side})."
        )
    _ = stage
    return width, height, effective_mime
