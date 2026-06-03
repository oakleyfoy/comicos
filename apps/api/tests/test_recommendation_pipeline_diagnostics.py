"""Recommendation pipeline memory diagnostics."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.cross_system_build_timing import CrossSystemBuildTiming
from app.services.recommendation_pipeline_diagnostics import (
    PipelineDiagnosticReport,
    RecommendationPipelineTracker,
    process_rss_mb,
)


def test_process_rss_mb_non_negative() -> None:
    assert process_rss_mb() >= 0.0


def test_tracker_records_memory_fields() -> None:
    tracker = RecommendationPipelineTracker(prefix="test")
    tracker.run("step_a", lambda: list(range(100)))
    report = tracker.finish()
    assert isinstance(report, PipelineDiagnosticReport)
    assert report.memory_before_mb >= 0.0
    assert report.memory_after_mb >= 0.0
    assert report.peak_memory_mb >= report.memory_before_mb
    assert len(report.stages) == 1
    stage = report.stages[0]
    assert stage.stage == "step_a"
    assert stage.rows_loaded == 100
    assert stage.memory_before_mb >= 0.0
    assert stage.memory_after_mb >= 0.0
    assert stage.peak_memory_mb >= 0.0


def test_cross_system_timing_exposes_memory_report() -> None:
    timer = CrossSystemBuildTiming()
    timer.run("noop", lambda: {"a": 1})
    timer.log_summary()
    mem = timer.memory_report()
    assert "memory_before_mb" in mem
    assert "memory_after_mb" in mem
    assert "peak_memory_mb" in mem
    assert "stages" in mem
