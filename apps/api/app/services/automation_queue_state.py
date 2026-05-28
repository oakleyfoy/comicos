from __future__ import annotations

from datetime import datetime


ALLOWED_JOB_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"AVAILABLE"},
    "AVAILABLE": {"RESERVED", "CANCELLED"},
    "RESERVED": {"RUNNING", "AVAILABLE"},
    "RUNNING": {"COMPLETED", "FAILED"},
    "FAILED": {"RETRY_PENDING", "DEAD_LETTER"},
    "RETRY_PENDING": {"AVAILABLE"},
}


def validate_job_transition(*, from_status: str, to_status: str) -> None:
    if to_status not in ALLOWED_JOB_TRANSITIONS.get(from_status, set()):
        raise ValueError(f"Invalid automation job transition: {from_status} -> {to_status}")


def build_transition_metadata(*, from_status: str, to_status: str, occurred_at: datetime, metadata_json: dict) -> dict:
    return {
        "from_status": from_status,
        "to_status": to_status,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z") if occurred_at.tzinfo else occurred_at.isoformat(),
        "metadata_json": metadata_json,
    }
