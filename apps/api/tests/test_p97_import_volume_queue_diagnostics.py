from __future__ import annotations

from app.services.p97_comicvine_rate_budget import RateBudgetDecision
from app.services.p97_requested_volume_import_service import wait_for_comicvine_budget


def test_wait_for_comicvine_budget_logs_and_returns_when_allowed() -> None:
    logs: list[str] = []

    class _Budget:
        def should_pause_for_420(self) -> bool:
            return False

        def evaluate(self):
            return RateBudgetDecision(
                allowed=True,
                reason="OK",
                seconds_until_next_request=0.0,
                requests_last_hour=0,
                paused_for_420=False,
                pause_until=None,
            )

    assert wait_for_comicvine_budget(
        _Budget(),  # type: ignore[arg-type]
        log_fn=logs.append,
        context="test",
    )
    assert any("allowed immediately" in line for line in logs)


def test_wait_for_comicvine_budget_sleeps_120_second_chunks() -> None:
    logs: list[str] = []
    sleeps: list[float] = []
    evaluate_calls = 0

    class _Budget:
        def should_pause_for_420(self) -> bool:
            return False

        def evaluate(self) -> RateBudgetDecision:
            nonlocal evaluate_calls
            evaluate_calls += 1
            if evaluate_calls <= 2:
                return RateBudgetDecision(
                    allowed=False,
                    reason="HOURLY_BUDGET_EXHAUSTED",
                    seconds_until_next_request=500.0,
                    requests_last_hour=151,
                    paused_for_420=False,
                    pause_until=None,
                )
            return RateBudgetDecision(
                allowed=True,
                reason="OK",
                seconds_until_next_request=0.0,
                requests_last_hour=149,
                paused_for_420=False,
                pause_until=None,
            )

    assert wait_for_comicvine_budget(
        _Budget(),  # type: ignore[arg-type]
        sleep_fn=sleeps.append,
        log_fn=logs.append,
        context="test",
    )
    assert sleeps == [120.0]
    assert any("sleeping 120.0s" in line and "HOURLY_BUDGET_EXHAUSTED" in line for line in logs)
