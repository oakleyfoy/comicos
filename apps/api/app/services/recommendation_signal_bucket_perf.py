"""Performance instrumentation for signal-bucket diagnostics (audit only)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine


@dataclass
class PerfStep:
    name: str
    duration_ms: float
    query_count_delta: int = 0
    rows_scanned: int = 0
    notes: str = ""


@dataclass
class DiagnosticPerfRecorder:
    """Collect step timings and DB query counts for diagnostic scripts."""

    _started: float = field(default_factory=time.monotonic)
    steps: list[PerfStep] = field(default_factory=list)
    _query_total: int = 0
    _query_at_step_start: int = 0
    verification: dict[str, Any] = field(default_factory=dict)

    def elapsed_total_ms(self) -> float:
        return round((time.monotonic() - self._started) * 1000.0, 2)

    @contextmanager
    def step(self, name: str, *, rows_scanned: int = 0, notes: str = "") -> Iterator[None]:
        self._query_at_step_start = self._query_total
        started = time.monotonic()
        try:
            yield
        finally:
            duration_ms = round((time.monotonic() - started) * 1000.0, 2)
            delta = self._query_total - self._query_at_step_start
            self.steps.append(
                PerfStep(
                    name=name,
                    duration_ms=duration_ms,
                    query_count_delta=delta,
                    rows_scanned=rows_scanned,
                    notes=notes,
                )
            )

    def record_query(self) -> None:
        self._query_total += 1

    def top_slow_steps(self, n: int = 10) -> list[dict[str, Any]]:
        ordered = sorted(self.steps, key=lambda s: s.duration_ms, reverse=True)
        return [
            {
                "name": s.name,
                "duration_ms": s.duration_ms,
                "query_count": s.query_count_delta,
                "rows_scanned": s.rows_scanned,
                "notes": s.notes,
            }
            for s in ordered[:n]
        ]

    def total_queries(self) -> int:
        return self._query_total

    def total_rows_scanned(self) -> int:
        return sum(s.rows_scanned for s in self.steps)

    def build_report(self) -> dict[str, Any]:
        return {
            "total_runtime_ms": self.elapsed_total_ms(),
            "total_database_queries": self.total_queries(),
            "total_rows_scanned_reported": self.total_rows_scanned(),
            "top_10_slowest_steps": self.top_slow_steps(10),
            "all_steps": [
                {
                    "name": s.name,
                    "duration_ms": s.duration_ms,
                    "query_count": s.query_count_delta,
                    "rows_scanned": s.rows_scanned,
                    "notes": s.notes,
                }
                for s in self.steps
            ],
            "verification": self.verification,
            "optimization_plan": self._optimization_plan(),
        }

    def _optimization_plan(self) -> list[str]:
        plans: list[str] = []
        v = self.verification
        if v.get("rebuilds_title_index_in_script"):
            plans.append(
                "Cache build_forward_release_title_index once per run; avoid duplicate builds inside list_latest_cross_system_recommendations."
            )
        if v.get("list_latest_builds_decision_context"):
            plans.append(
                "For diagnostics, read cross_system snapshot rows only; skip decision_for_cross_system per row (dominant cost)."
            )
        if v.get("scans_all_market_demand_profiles"):
            plans.append(
                "Replace select(MarketDemandProfile).all() with name-filtered query or preloaded owner-scoped cache."
            )
        if v.get("creator_profile_scan_repeats", 0) > 1:
            plans.append(
                "Load ACTIVE CreatorProfile once per diagnose call; reuse for catalog/variant/full blob checks."
            )
        if v.get("recommendation_lookup_limit", 0) > 50:
            plans.append(
                "Single-title mode should use limit=1 snapshot row match or SQL filter by title, not limit=250 with full decision pipeline."
            )
        if v.get("title_index_row_count", 0) > 500:
            plans.append(
                "Single-title diagnose should not require full forward title index; use targeted release lookup only."
            )
        if not plans:
            plans.append("No dominant bottleneck flagged; inspect top_10_slowest_steps for regressions.")
        plans.append("Target: single-title diagnostic under 10s without recommendation rebuilds.")
        return plans


def attach_query_counter(engine: Engine, recorder: DiagnosticPerfRecorder) -> None:
    """Count SQL execute events for the given engine."""

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        recorder.record_query()
