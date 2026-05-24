"""Safeguards for OCR/cover pipelines (timeouts, guards, structured errors)."""

from __future__ import annotations

import threading
import time
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import get_settings
from app.services.ocr_pipeline_runtime import run_with_thread_deadline, validate_pipeline_image_bytes
from app.services.processing_errors import (
    dumps_structured_error,
    public_safe_message,
    try_parse_structured_error,
)


def test_structured_processing_error_round_trip_does_not_leak_prefixed_blob() -> None:
    persisted = dumps_structured_error(
        error_code="test_code",
        error_type="failure",
        safe_message="hello world",
        retryable=True,
        details={"stage": "unit"},
    )
    parsed = try_parse_structured_error(persisted)
    assert parsed is not None
    assert parsed.error_code == "test_code"
    visible = public_safe_message(persisted)
    assert "PROCESSING_ERROR_V1:" not in (visible or "")


def test_run_with_thread_deadline_non_positive_skips_executor() -> None:
    calls: list[int] = []

    def fn() -> int:
        calls.append(1)
        return 42

    assert run_with_thread_deadline(0, fn, stage="inline") == 42
    assert calls == [1]
    calls.clear()
    assert run_with_thread_deadline(-0.001, fn, stage="inline_neg") == 42
    assert calls == [1]


def test_validate_pipeline_image_bytes_accepts_png() -> None:
    settings = get_settings()
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(9, 9, 9)).save(buf, format="PNG")
    body = buf.getvalue()
    w, h, mime = validate_pipeline_image_bytes(
        settings=settings,
        body=body,
        mime_type="image/png",
        stage="test",
    )
    assert mime == "image/png"
    assert w == 32 and h == 32


def test_validate_pipeline_image_bytes_rejects_corrupt_payload() -> None:
    settings = get_settings()
    body = b"not an image\xff"
    with pytest.raises(ValueError, match="corrupt"):
        validate_pipeline_image_bytes(settings=settings, body=body, mime_type=None, stage="test")
