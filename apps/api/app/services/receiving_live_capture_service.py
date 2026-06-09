from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from app.schemas.receiving import LiveCaptureSource

LIVE_CAPTURE_DUPLICATE_WINDOW_SECONDS = 30
_LIVE_CAPTURE_CACHE_LOCK = Lock()
_LIVE_CAPTURE_RECENT_KEYS: dict[str, datetime] = {}


def normalize_live_capture_source(value: str | None) -> LiveCaptureSource | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized in {"WEBCAM", "MOBILE_CAMERA", "CONVENTION_SCAN"}:
        return normalized  # type: ignore[return-value]
    return None


def frame_cache_key(*, capture_source: LiveCaptureSource | None, frame_fingerprint: str | None) -> str | None:
    if not frame_fingerprint:
        return None
    source = capture_source or "WEBCAM"
    return f"{source}:{frame_fingerprint}"


def should_suppress_duplicate_capture(
    *,
    capture_source: LiveCaptureSource | None,
    frame_fingerprint: str | None,
    now: datetime | None = None,
) -> bool:
    key = frame_cache_key(capture_source=capture_source, frame_fingerprint=frame_fingerprint)
    if key is None:
        return False

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=LIVE_CAPTURE_DUPLICATE_WINDOW_SECONDS)
    with _LIVE_CAPTURE_CACHE_LOCK:
        stale_keys = [recent_key for recent_key, timestamp in _LIVE_CAPTURE_RECENT_KEYS.items() if timestamp < cutoff]
        for recent_key in stale_keys:
            _LIVE_CAPTURE_RECENT_KEYS.pop(recent_key, None)
        if key in _LIVE_CAPTURE_RECENT_KEYS:
            return True
        _LIVE_CAPTURE_RECENT_KEYS[key] = now
    return False


def reset_live_capture_cache() -> None:
    with _LIVE_CAPTURE_CACHE_LOCK:
        _LIVE_CAPTURE_RECENT_KEYS.clear()


def update_live_capture_stats(
    stats: dict[str, Any] | None,
    *,
    capture_source: LiveCaptureSource | None,
    stable_frame_count: int = 0,
    duplicate_suppressed: bool = False,
    recognition_latency_ms: int | None = None,
) -> dict[str, Any]:
    next_stats = dict(stats or {})
    next_stats["capture_source"] = capture_source
    next_stats["stable_frame_count"] = int(stable_frame_count)
    if duplicate_suppressed:
        next_stats["duplicate_suppressed_count"] = int(next_stats.get("duplicate_suppressed_count", 0)) + 1
    if recognition_latency_ms is not None:
        next_stats["recognition_latency_total_ms"] = int(next_stats.get("recognition_latency_total_ms", 0)) + int(
            recognition_latency_ms
        )
        next_stats["recognition_latency_samples"] = int(next_stats.get("recognition_latency_samples", 0)) + 1
        sample_count = int(next_stats["recognition_latency_samples"])
        total_ms = int(next_stats["recognition_latency_total_ms"])
        next_stats["average_recognition_time_ms"] = round(total_ms / sample_count, 2) if sample_count else 0
    return next_stats
