"""Stage timing for cross-system candidate build (stderr + optional dict export)."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field


@dataclass
class CrossSystemBuildTiming:
    steps_ms: dict[str, float] = field(default_factory=dict)

    def run(self, name: str, fn):
        started = time.monotonic()
        result = fn()
        elapsed_ms = round((time.monotonic() - started) * 1000.0, 2)
        if elapsed_ms <= 0.0:
            elapsed_ms = 0.01
        self.steps_ms[name] = elapsed_ms
        print(f"timing cross_system.{name} {elapsed_ms:.1f}ms", file=sys.stderr, flush=True)
        return result

    def log_summary(self) -> None:
        total = round(sum(self.steps_ms.values()), 2)
        print(f"timing cross_system.total {total:.1f}ms", file=sys.stderr, flush=True)
