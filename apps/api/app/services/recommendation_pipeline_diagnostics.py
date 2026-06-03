"""RSS memory + query-count diagnostics for recommendation rebuild pipelines."""

from __future__ import annotations

import gc
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from sqlalchemy import event
from sqlmodel import Session

T = TypeVar("T")


def process_rss_mb() -> float:
    """Resident set size for this process (platform-specific units normalized to MiB)."""
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = float(usage.ru_maxrss)
        if sys.platform == "darwin":
            return rss / (1024.0 * 1024.0)
        return rss / 1024.0
    except Exception:
        return 0.0


def _rows_loaded(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return None


def _object_count_estimate(value: object) -> int | None:
    rows = _rows_loaded(value)
    if rows is not None:
        return rows
    return None


@dataclass
class StageDiagnostic:
    stage: str
    elapsed_ms: float
    memory_before_mb: float
    memory_after_mb: float
    peak_memory_mb: float
    rows_loaded: int | None = None
    object_count: int | None = None
    query_count: int = 0


@dataclass
class PipelineDiagnosticReport:
    memory_before_mb: float
    memory_after_mb: float
    peak_memory_mb: float
    stages: list[StageDiagnostic] = field(default_factory=list)
    total_query_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_before_mb": self.memory_before_mb,
            "memory_after_mb": self.memory_after_mb,
            "peak_memory_mb": self.peak_memory_mb,
            "total_query_count": self.total_query_count,
            "stages": [
                {
                    "stage": s.stage,
                    "elapsed_ms": s.elapsed_ms,
                    "memory_before_mb": s.memory_before_mb,
                    "memory_after_mb": s.memory_after_mb,
                    "peak_memory_mb": s.peak_memory_mb,
                    "rows_loaded": s.rows_loaded,
                    "object_count": s.object_count,
                    "query_count": s.query_count,
                }
                for s in self.stages
            ],
        }


class _QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def before_cursor_execute(self, *args: object, **kwargs: object) -> None:
        self.count += 1


@dataclass
class RecommendationPipelineTracker:
    """Stage runner with timing, RSS sampling, and optional SQL query counts."""

    prefix: str
    session: Session | None = None
    steps_ms: dict[str, float] = field(default_factory=dict)
    stages: list[StageDiagnostic] = field(default_factory=list)
    memory_before_mb: float = field(default_factory=process_rss_mb)
    peak_memory_mb: float = field(default_factory=process_rss_mb)
    _query_counter: _QueryCounter = field(default_factory=_QueryCounter)
    _listeners: list[tuple[object, str, Callable[..., None]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.session is not None:
            bind = self.session.get_bind()
            for event_name, handler in (
                ("before_cursor_execute", self._query_counter.before_cursor_execute),
            ):
                event.listen(bind, event_name, handler)
                self._listeners.append((bind, event_name, handler))

    def _sample_peak(self) -> None:
        rss = process_rss_mb()
        if rss > self.peak_memory_mb:
            self.peak_memory_mb = rss

    def run(self, name: str, fn: Callable[[], T]) -> T:
        gc.collect()
        q_start = self._query_counter.count
        mem_before = process_rss_mb()
        self._sample_peak()
        started = time.monotonic()
        result = fn()
        elapsed_ms = round((time.monotonic() - started) * 1000.0, 2)
        if elapsed_ms <= 0.0:
            elapsed_ms = 0.01
        mem_after = process_rss_mb()
        self._sample_peak()
        rows = _rows_loaded(result)
        stage = StageDiagnostic(
            stage=name,
            elapsed_ms=elapsed_ms,
            memory_before_mb=round(mem_before, 2),
            memory_after_mb=round(mem_after, 2),
            peak_memory_mb=round(self.peak_memory_mb, 2),
            rows_loaded=rows,
            object_count=_object_count_estimate(result),
            query_count=max(0, self._query_counter.count - q_start),
        )
        self.stages.append(stage)
        self.steps_ms[name] = elapsed_ms
        print(
            f"timing {self.prefix}.{name} {elapsed_ms:.1f}ms "
            f"rss_before={stage.memory_before_mb:.1f}MB rss_after={stage.memory_after_mb:.1f}MB "
            f"peak={stage.peak_memory_mb:.1f}MB rows={stage.rows_loaded} queries={stage.query_count}",
            file=sys.stderr,
            flush=True,
        )
        return result

    def finish(self) -> PipelineDiagnosticReport:
        gc.collect()
        mem_after = process_rss_mb()
        self._sample_peak()
        for bind, event_name, handler in self._listeners:
            try:
                event.remove(bind, event_name, handler)
            except Exception:
                pass
        self._listeners.clear()
        return PipelineDiagnosticReport(
            memory_before_mb=round(self.memory_before_mb, 2),
            memory_after_mb=round(mem_after, 2),
            peak_memory_mb=round(self.peak_memory_mb, 2),
            stages=list(self.stages),
            total_query_count=self._query_counter.count,
        )

    def log_summary(self) -> None:
        report = self.finish()
        total_ms = round(sum(self.steps_ms.values()), 2)
        print(
            f"timing {self.prefix}.total {total_ms:.1f}ms "
            f"memory_before_mb={report.memory_before_mb} "
            f"memory_after_mb={report.memory_after_mb} "
            f"peak_memory_mb={report.peak_memory_mb} "
            f"queries={report.total_query_count}",
            file=sys.stderr,
            flush=True,
        )
