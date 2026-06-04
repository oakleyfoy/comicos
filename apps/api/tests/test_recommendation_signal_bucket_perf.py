from app.services.recommendation_signal_bucket_perf import DiagnosticPerfRecorder, PerfStep


def test_perf_recorder_top_slow_steps_ordering() -> None:
    rec = DiagnosticPerfRecorder()
    rec.steps = [
        PerfStep(name="fast", duration_ms=1.0),
        PerfStep(name="slow", duration_ms=50.0),
        PerfStep(name="medium", duration_ms=10.0),
    ]
    top = rec.top_slow_steps(2)
    assert len(top) == 2
    assert top[0]["name"] == "slow"
    assert top[1]["name"] == "medium"
    report = rec.build_report()
    assert report["total_runtime_ms"] >= 0
    assert "optimization_plan" in report
    assert len(report["top_10_slowest_steps"]) <= 10
