"""Deterministic structured errors for OCR / cover pipelines (persisted append-only strings)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from subprocess import TimeoutExpired
from typing import Any

from PIL import UnidentifiedImageError


PROCESSING_ERROR_V1_PREFIX = "PROCESSING_ERROR_V1:"
SAFE_MESSAGE_MAX = 480


ERROR_CODE_tesseract_timeout = "ocr_tesseract_timeout"
ERROR_CODE_barcode_derivation_truncated = "barcode_derivation_truncated"
ERROR_CODE_fingerprint_generation_timeout = "fingerprint_generation_timeout"
ERROR_CODE_quality_analysis_timeout = "quality_analysis_timeout"
ERROR_CODE_quality_analysis_failed = "quality_analysis_failed"
ERROR_CODE_cover_image_corrupt = "cover_image_corrupt"
ERROR_CODE_cover_image_oversized = "cover_image_oversized"
ERROR_CODE_cover_image_dimensions_exceeded = "cover_image_dimensions_exceeded"
ERROR_CODE_cover_image_unsupported_type = "cover_image_unsupported_type"
ERROR_CODE_retry_exhausted = "retry_exhausted_batch_item"
ERROR_CODE_generic_pipeline_failure = "pipeline_failure"


def _timeout_code_for_stage(stage: str) -> str:
    if stage == "ocr_tesseract":
        return ERROR_CODE_tesseract_timeout
    if stage == "fingerprint_generation":
        return ERROR_CODE_fingerprint_generation_timeout
    if stage == "quality_analysis":
        return ERROR_CODE_quality_analysis_timeout
    sanitized = "".join(char if char.isalnum() or char == "_" else "_" for char in stage).strip("_")
    return (sanitized + "_timeout") if sanitized else "processing_timeout"


@dataclass(frozen=True)
class StructuredProcessingError:
    error_code: str
    error_type: str
    safe_message: str
    retryable: bool
    occurred_at: str
    details: dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_message(message: str) -> str:
    cleaned = " ".join(str(message).split()).strip()
    if not cleaned:
        return "Processing failed."
    if "traceback" in cleaned.lower():
        cleaned = cleaned.splitlines()[0][:SAFE_MESSAGE_MAX]
    if len(cleaned) > SAFE_MESSAGE_MAX:
        cleaned = cleaned[:SAFE_MESSAGE_MAX] + "…"
    return cleaned


def dumps_structured_error(
    *,
    error_code: str,
    error_type: str,
    safe_message: str,
    retryable: bool,
    occurred_at: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    payload_dict: dict[str, Any] = {
        "error_code": error_code,
        "error_type": error_type,
        "safe_message": _sanitize_message(safe_message),
        "retryable": bool(retryable),
        "occurred_at": occurred_at or utc_now_iso(),
        "details": details or {},
    }
    try:
        body = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        body = json.dumps(
            {
                "error_code": ERROR_CODE_generic_pipeline_failure,
                "error_type": "serialization",
                "safe_message": "Processing failed.",
                "retryable": False,
                "occurred_at": occurred_at or utc_now_iso(),
                "details": {},
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    serialized = PROCESSING_ERROR_V1_PREFIX + body
    return serialized[:2000]


def try_parse_structured_error(stored: str | None) -> StructuredProcessingError | None:
    if not stored:
        return None
    trimmed = stored.strip()
    if not trimmed.startswith(PROCESSING_ERROR_V1_PREFIX):
        return None
    raw_json = trimmed[len(PROCESSING_ERROR_V1_PREFIX) :]
    try:
        decoded = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    try:
        details = decoded.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        return StructuredProcessingError(
            error_code=str(decoded["error_code"]),
            error_type=str(decoded["error_type"]),
            safe_message=str(decoded["safe_message"]),
            retryable=bool(decoded["retryable"]),
            occurred_at=str(decoded["occurred_at"]),
            details={str(k): v for k, v in details.items()},
        )
    except (KeyError, TypeError, ValueError):
        return None


def public_safe_message(stored: str | None) -> str | None:
    parsed = try_parse_structured_error(stored)
    if parsed is not None:
        return parsed.safe_message
    if not stored:
        return None
    return _sanitize_message(stored)


def classify_exception(exc: BaseException, *, stage: str) -> StructuredProcessingError:
    if isinstance(exc, TimeoutExpired):
        return StructuredProcessingError(
            error_code=_timeout_code_for_stage(stage),
            error_type="processing_timeout",
            safe_message=f"Processing step '{stage}' timed out.",
            retryable=True,
            occurred_at=utc_now_iso(),
            details={"stage": stage, "timeout_seconds": getattr(exc, "timeout", None)},
        )

    if isinstance(exc, UnidentifiedImageError):
        return StructuredProcessingError(
            error_code=ERROR_CODE_cover_image_corrupt,
            error_type="corrupt_image",
            safe_message="Image could not be decoded.",
            retryable=False,
            occurred_at=utc_now_iso(),
            details={"stage": stage},
        )

    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {22}:
        return StructuredProcessingError(
            error_code=ERROR_CODE_cover_image_corrupt,
            error_type="io_error",
            safe_message="Image could not be read.",
            retryable=False,
            occurred_at=utc_now_iso(),
            details={"stage": stage},
        )

    failure_type_mapped = ERROR_CODE_generic_pipeline_failure
    retryable = False
    if isinstance(exc, ValueError):
        msg = _sanitize_message(str(exc))
        lowered = msg.lower()
        retryable = True
        if "oversized" in lowered or "exceeds max file" in lowered:
            failure_type_mapped = ERROR_CODE_cover_image_oversized
            retryable = False
        elif "dimensions" in lowered and "exceed" in lowered:
            failure_type_mapped = ERROR_CODE_cover_image_dimensions_exceeded
            retryable = False
        elif "unsupported" in lowered and "mime" in lowered:
            failure_type_mapped = ERROR_CODE_cover_image_unsupported_type
            retryable = False
        elif "corrupt" in lowered or "could not be decoded" in lowered:
            failure_type_mapped = ERROR_CODE_cover_image_corrupt
            retryable = False
        elif "timed out" in lowered:
            failure_type_mapped = _timeout_code_for_stage(stage)
            retryable = True
        elif "retry exhausted" in lowered or ERROR_CODE_retry_exhausted in msg:
            failure_type_mapped = ERROR_CODE_retry_exhausted
            retryable = False
        return StructuredProcessingError(
            error_code=failure_type_mapped,
            error_type="value_error",
            safe_message=msg,
            retryable=retryable,
            occurred_at=utc_now_iso(),
            details={"stage": stage},
        )

    snippet = ""
    hint = getattr(exc, "args", ())
    if hint and isinstance(hint[0], str):
        snippet = hint[0]
    label = type(exc).__name__
    safe_bits = [label]
    if snippet:
        safe_bits.append(snippet.splitlines()[0][:200])
    safe = _sanitize_message(" — ".join(safe_bits))
    return StructuredProcessingError(
        error_code=ERROR_CODE_generic_pipeline_failure,
        error_type=label,
        safe_message=safe,
        retryable=isinstance(exc, TimeoutExpired),
        occurred_at=utc_now_iso(),
        details={"stage": stage},
    )


def structured_error_to_persistent(struct: StructuredProcessingError) -> str:
    return dumps_structured_error(
        error_code=struct.error_code,
        error_type=struct.error_type,
        safe_message=struct.safe_message,
        retryable=struct.retryable,
        occurred_at=struct.occurred_at,
        details=struct.details,
    )


def naive_error_code_guess_legacy(stored: str | None) -> str | None:
    parsed = try_parse_structured_error(stored)
    if parsed is not None:
        return parsed.error_code
    return None
