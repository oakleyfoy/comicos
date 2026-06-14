"""ComicVine API pacing helpers — velocity spacing, hourly per-resource caps, response cache."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

# Official ComicVine guidance: 200 requests per resource per hour; velocity blocks for bursty traffic.
COMICVINE_OFFICIAL_REQUESTS_PER_RESOURCE_HOUR = 200
COMICVINE_MIN_SECONDS_BETWEEN_REQUESTS = 1.0
HOUR_SECONDS = 3600.0


def comicvine_resource_name(path: str) -> str:
    cleaned = path.strip("/").split("/")[0] or "unknown"
    return cleaned.lower()


class ComicVineHourlyBudget:
    """Rolling 1-hour window per API resource (volumes, issues, …)."""

    def __init__(self, *, max_per_hour: int) -> None:
        self.max_per_hour = max(1, max_per_hour)
        self._timestamps: dict[str, deque[float]] = {}

    def _prune(self, resource: str, now: float) -> deque[float]:
        bucket = self._timestamps.setdefault(resource, deque())
        cutoff = now - HOUR_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return bucket

    def wait_if_needed(self, resource: str) -> None:
        now = time.monotonic()
        bucket = self._prune(resource, now)
        if len(bucket) < self.max_per_hour:
            return
        sleep_for = bucket[0] + HOUR_SECONDS - now
        if sleep_for > 0:
            LOGGER.warning(
                "ComicVine hourly cap (%s/%s) reached for resource %s; sleeping %.0fs",
                self.max_per_hour,
                "hour",
                resource,
                sleep_for,
            )
            time.sleep(sleep_for)
            self._prune(resource, time.monotonic())

    def record(self, resource: str) -> None:
        self._prune(resource, time.monotonic()).append(time.monotonic())


def comicvine_cache_key(path: str, params: dict[str, Any] | None) -> str:
    safe_params = sorted((k, v) for k, v in (params or {}).items() if k != "api_key")
    raw = json.dumps({"path": path, "params": safe_params}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_comicvine_cache(cache_dir: Path, key: str) -> dict[str, Any] | None:
    path = cache_dir / f"{key}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and ("results" in payload or payload.get("error") == "OK"):
            return payload
    except (OSError, json.JSONDecodeError):
        return None
    return None


def write_comicvine_cache(cache_dir: Path, key: str, payload: dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
