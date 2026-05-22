from rq.timeouts import TimerDeathPenalty

from app.tasks.jobs import (
    run_local_ai_parse_diagnostic_job,
    run_local_gmail_sync_diagnostic_job,
)
from app.tasks.queue import get_worker_queue_names
from app.workers.worker_runtime import WindowsLocalSimpleWorker


def test_local_worker_diagnostic_job_returns_marker() -> None:
    result = run_local_ai_parse_diagnostic_job("marker-123")

    assert result["status"] == "ok"
    assert result["marker"] == "marker-123"
    assert result["job_type"] == "ai_parse_diagnostic"
    assert "timestamp" in result


def test_local_gmail_sync_diagnostic_job_returns_marker() -> None:
    result = run_local_gmail_sync_diagnostic_job("gmail-marker-123")

    assert result["status"] == "ok"
    assert result["marker"] == "gmail-marker-123"
    assert result["job_type"] == "gmail_sync_diagnostic"
    assert "timestamp" in result


def test_worker_queue_names_include_ai_parse_and_gmail_sync() -> None:
    assert get_worker_queue_names() == ["ai_parse", "gmail_sync"]


def test_windows_local_worker_uses_timer_death_penalty() -> None:
    assert WindowsLocalSimpleWorker.death_penalty_class is TimerDeathPenalty
