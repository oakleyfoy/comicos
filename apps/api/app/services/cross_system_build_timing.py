"""Stage timing + memory diagnostics for cross-system candidate build."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.recommendation_pipeline_diagnostics import RecommendationPipelineTracker


@dataclass
class CrossSystemBuildTiming:
    """Delegates to RecommendationPipelineTracker (timing, RSS, row counts, queries)."""

    steps_ms: dict[str, float] = field(default_factory=dict)
    _tracker: RecommendationPipelineTracker | None = None
    last_report: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self._tracker is None:
            self._tracker = RecommendationPipelineTracker(prefix="cross_system")

    def run(self, name: str, fn):
        assert self._tracker is not None
        return self._tracker.run(name, fn)

    def attach_session(self, session) -> None:
        assert self._tracker is not None
        self._tracker.session = session

    def log_summary(self) -> None:
        import sys

        assert self._tracker is not None
        self.steps_ms = dict(self._tracker.steps_ms)
        report = self._tracker.finish()
        self.last_report = report.to_dict()
        total_ms = round(sum(self.steps_ms.values()), 2)
        print(
            f"timing cross_system.total {total_ms:.1f}ms "
            f"memory_before_mb={report.memory_before_mb} "
            f"memory_after_mb={report.memory_after_mb} "
            f"peak_memory_mb={report.peak_memory_mb} "
            f"queries={report.total_query_count}",
            file=sys.stderr,
            flush=True,
        )

    def memory_report(self) -> dict[str, object]:
        if self.last_report is not None:
            return self.last_report
        assert self._tracker is not None
        return self._tracker.finish().to_dict()
