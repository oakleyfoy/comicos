"""RQ entrypoint for P86 weekly release lifecycle capture."""

from __future__ import annotations

from app.services.release_lifecycle_cron import run_release_lifecycle_weekly_cron


def run_scheduled_release_lifecycle_weekly() -> dict[str, object]:
    result = run_release_lifecycle_weekly_cron()
    return {
        "status": result.status,
        "exit_code": result.exit_code,
        "message": result.message,
        "runs": result.runs,
        "report_id": result.report_id,
    }
