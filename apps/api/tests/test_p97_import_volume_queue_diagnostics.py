from __future__ import annotations

from app.services.p97_requested_volume_import_service import wait_for_comicvine_budget


def test_wait_for_comicvine_budget_logs_and_returns_when_allowed() -> None:
    logs: list[str] = []

    class _Budget:
        def should_pause_for_420(self) -> bool:
            return False

        def evaluate(self):
            from app.services.p97_comicvine_rate_budget import RateBudgetDecision

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
