from __future__ import annotations

from app.services.external_catalog.locg_capture_timing import (
    CaptureTimingAudit,
    IssueCaptureTiming,
)


def test_build_summary_omits_per_issue_timings_by_default() -> None:
    audit = CaptureTimingAudit(issue_timings=[IssueCaptureTiming(issue_title="A")])
    summary = audit.build_summary()
    assert "per_issue_timings" not in summary
    assert summary["per_issue_timings_count"] == 1


def test_build_summary_includes_per_issue_timings_when_requested() -> None:
    audit = CaptureTimingAudit(issue_timings=[IssueCaptureTiming(issue_title="B")])
    summary = audit.build_summary(include_per_issue_timings=True)
    assert len(summary["per_issue_timings"]) == 1
    assert summary["per_issue_timings"][0]["issue_title"] == "B"
