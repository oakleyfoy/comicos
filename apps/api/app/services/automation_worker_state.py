from __future__ import annotations

from datetime import datetime


ALLOWED_WORKER_TRANSITIONS: dict[str, set[str]] = {
    "STARTING": {"IDLE"},
    "IDLE": {"RESERVED"},
    "RESERVED": {"RUNNING"},
    "RUNNING": {"IDLE", "ERROR", "SHUTTING_DOWN"},
    "SHUTTING_DOWN": {"OFFLINE"},
    "ERROR": {"OFFLINE"},
}


def validate_worker_transition(*, from_status: str, to_status: str) -> None:
    if to_status not in ALLOWED_WORKER_TRANSITIONS.get(from_status, set()):
        raise ValueError(f"Invalid automation worker transition: {from_status} -> {to_status}")


def build_worker_transition_metadata(*, from_status: str, to_status: str, occurred_at: datetime, metadata_json: dict) -> dict:
    return {
        "from_status": from_status,
        "to_status": to_status,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z") if occurred_at.tzinfo else occurred_at.isoformat(),
        "metadata_json": metadata_json,
    }
