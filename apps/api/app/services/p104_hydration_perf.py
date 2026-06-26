"""P104 cover hydration stage timing and performance summaries."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HydrateStageTiming:
    url_resolve: float = 0.0
    download: float = 0.0
    staging_write: float = 0.0
    original_file_write: float = 0.0
    derivative_resize_write: float = 0.0
    sha256: float = 0.0
    phash_ahash_dhash: float = 0.0
    color_histogram: float = 0.0
    db_update_commit: float = 0.0
    total: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "url_resolve": self.url_resolve,
            "download": self.download,
            "staging_write": self.staging_write,
            "original_file_write": self.original_file_write,
            "derivative_resize_write": self.derivative_resize_write,
            "sha256": self.sha256,
            "phash_ahash_dhash": self.phash_ahash_dhash,
            "color_histogram": self.color_histogram,
            "db_update_commit": self.db_update_commit,
            "total": self.total,
        }


@dataclass
class P104PerformanceSummary:
    assets_timed: int = 0
    url_resolve: float = 0.0
    download: float = 0.0
    staging_write: float = 0.0
    original_file_write: float = 0.0
    derivative_resize_write: float = 0.0
    sha256: float = 0.0
    phash_ahash_dhash: float = 0.0
    color_histogram: float = 0.0
    db_update_commit: float = 0.0
    total: float = 0.0

    def add(self, timing: HydrateStageTiming) -> None:
        self.assets_timed += 1
        self.url_resolve += timing.url_resolve
        self.download += timing.download
        self.staging_write += timing.staging_write
        self.original_file_write += timing.original_file_write
        self.derivative_resize_write += timing.derivative_resize_write
        self.sha256 += timing.sha256
        self.phash_ahash_dhash += timing.phash_ahash_dhash
        self.color_histogram += timing.color_histogram
        self.db_update_commit += timing.db_update_commit
        self.total += timing.total

    def _avg(self, total: float) -> float:
        if self.assets_timed <= 0:
            return 0.0
        return total / self.assets_timed

    def to_dict(self) -> dict[str, Any]:
        n = max(1, self.assets_timed)
        return {
            "assets_timed": self.assets_timed,
            "totals_seconds": {
                "url_resolve": self.url_resolve,
                "download": self.download,
                "staging_write": self.staging_write,
                "original_file_write": self.original_file_write,
                "derivative_resize_write": self.derivative_resize_write,
                "sha256": self.sha256,
                "phash_ahash_dhash": self.phash_ahash_dhash,
                "color_histogram": self.color_histogram,
                "db_update_commit": self.db_update_commit,
                "total": self.total,
            },
            "avg_seconds_per_asset": {
                "url_resolve": self._avg(self.url_resolve),
                "download": self._avg(self.download),
                "staging_write": self._avg(self.staging_write),
                "original_file_write": self._avg(self.original_file_write),
                "derivative_resize_write": self._avg(self.derivative_resize_write),
                "sha256": self._avg(self.sha256),
                "phash_ahash_dhash": self._avg(self.phash_ahash_dhash),
                "color_histogram": self._avg(self.color_histogram),
                "db_update_commit": self._avg(self.db_update_commit),
                "total": self._avg(self.total),
            },
            "pct_of_total_time": {
                "url_resolve": round(100.0 * self.url_resolve / self.total, 2) if self.total else 0.0,
                "download": round(100.0 * self.download / self.total, 2) if self.total else 0.0,
                "staging_write": round(100.0 * self.staging_write / self.total, 2) if self.total else 0.0,
                "original_file_write": round(100.0 * self.original_file_write / self.total, 2) if self.total else 0.0,
                "derivative_resize_write": round(
                    100.0 * self.derivative_resize_write / self.total, 2
                ) if self.total else 0.0,
                "sha256": round(100.0 * self.sha256 / self.total, 2) if self.total else 0.0,
                "phash_ahash_dhash": round(100.0 * self.phash_ahash_dhash / self.total, 2) if self.total else 0.0,
                "color_histogram": round(100.0 * self.color_histogram / self.total, 2) if self.total else 0.0,
                "db_update_commit": round(100.0 * self.db_update_commit / self.total, 2) if self.total else 0.0,
            },
        }

    def format_lines(self) -> list[str]:
        d = self.to_dict()
        lines = [
            "P104 performance summary (stage timing)",
            f"  assets_timed={self.assets_timed}",
        ]
        for key, label in [
            ("url_resolve", "URL resolve"),
            ("download", "Download"),
            ("staging_write", "Staging write"),
            ("original_file_write", "Original file write"),
            ("derivative_resize_write", "Derivative resize/write"),
            ("sha256", "SHA256"),
            ("phash_ahash_dhash", "pHash/aHash/dHash"),
            ("color_histogram", "Color histogram"),
            ("db_update_commit", "DB update/commit"),
            ("total", "Total per asset"),
        ]:
            avg = d["avg_seconds_per_asset"][key]
            pct = d["pct_of_total_time"].get(key, 0.0)
            if key == "total":
                lines.append(f"  {label}: avg={avg:.4f}s")
            else:
                lines.append(f"  {label}: avg={avg:.4f}s ({pct}% of asset time)")
        return lines


class GlobalDownloadRateLimiter:
    """Thread-safe global downloads-per-minute cap."""

    def __init__(self, downloads_per_minute: float) -> None:
        self._min_interval = 60.0 / max(1.0, float(downloads_per_minute))
        self._lock = threading.Lock()
        self._last_at: float | None = None

    def wait(self) -> None:
        with self._lock:
            now = time.perf_counter()
            if self._last_at is not None:
                gap = now - self._last_at
                if gap < self._min_interval:
                    time.sleep(self._min_interval - gap)
                    now = time.perf_counter()
            self._last_at = now
