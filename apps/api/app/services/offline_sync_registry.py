from __future__ import annotations

from dataclasses import dataclass


QUEUE_STATUS_PENDING = "pending"
QUEUE_STATUS_PROCESSING = "processing"
QUEUE_STATUS_COMPLETED = "completed"
QUEUE_STATUS_FAILED = "failed"

CONFLICT_STATUS_OPEN = "open"
CONFLICT_STATUS_ACKNOWLEDGED = "acknowledged"
CONFLICT_STATUS_RESOLVED_MANUAL = "resolved_manual"

CHANGE_TYPE_CREATE = "create"
CHANGE_TYPE_UPDATE = "update"
CHANGE_TYPE_DELETE = "delete"
CHANGE_TYPE_LOOKUP = "lookup"

QUEUE_STATUSES: tuple[str, ...] = (
    QUEUE_STATUS_PENDING,
    QUEUE_STATUS_PROCESSING,
    QUEUE_STATUS_COMPLETED,
    QUEUE_STATUS_FAILED,
)

CONFLICT_STATUSES: tuple[str, ...] = (
    CONFLICT_STATUS_OPEN,
    CONFLICT_STATUS_ACKNOWLEDGED,
    CONFLICT_STATUS_RESOLVED_MANUAL,
)

CHANGE_TYPES: tuple[str, ...] = (
    CHANGE_TYPE_CREATE,
    CHANGE_TYPE_UPDATE,
    CHANGE_TYPE_DELETE,
    CHANGE_TYPE_LOOKUP,
)

QUEUE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUE_STATUS_PENDING: frozenset({QUEUE_STATUS_PROCESSING, QUEUE_STATUS_FAILED}),
    QUEUE_STATUS_PROCESSING: frozenset({QUEUE_STATUS_COMPLETED, QUEUE_STATUS_FAILED}),
    QUEUE_STATUS_COMPLETED: frozenset(),
    QUEUE_STATUS_FAILED: frozenset({QUEUE_STATUS_PENDING}),
}

CONFLICT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    CONFLICT_STATUS_OPEN: frozenset({CONFLICT_STATUS_ACKNOWLEDGED}),
    CONFLICT_STATUS_ACKNOWLEDGED: frozenset({CONFLICT_STATUS_RESOLVED_MANUAL}),
    CONFLICT_STATUS_RESOLVED_MANUAL: frozenset(),
}


@dataclass(frozen=True)
class OfflineSyncStateDefinition:
    state_key: str
    state_group: str
    display_name: str


OFFLINE_SYNC_STATE_DEFINITIONS: tuple[OfflineSyncStateDefinition, ...] = (
    OfflineSyncStateDefinition(QUEUE_STATUS_PENDING, "queue", "Pending sync"),
    OfflineSyncStateDefinition(QUEUE_STATUS_PROCESSING, "queue", "Processing sync"),
    OfflineSyncStateDefinition(QUEUE_STATUS_COMPLETED, "queue", "Completed sync"),
    OfflineSyncStateDefinition(QUEUE_STATUS_FAILED, "queue", "Failed sync"),
    OfflineSyncStateDefinition(CONFLICT_STATUS_OPEN, "conflict", "Open conflict"),
    OfflineSyncStateDefinition(CONFLICT_STATUS_ACKNOWLEDGED, "conflict", "Acknowledged conflict"),
    OfflineSyncStateDefinition(CONFLICT_STATUS_RESOLVED_MANUAL, "conflict", "Manually resolved conflict"),
)


def list_queue_statuses() -> tuple[str, ...]:
    return QUEUE_STATUSES


def list_conflict_statuses() -> tuple[str, ...]:
    return CONFLICT_STATUSES


def list_change_types() -> tuple[str, ...]:
    return CHANGE_TYPES


def validate_queue_status(value: str) -> None:
    if value not in QUEUE_STATUSES:
        raise ValueError(f"Invalid queue status: {value}")


def validate_conflict_status(value: str) -> None:
    if value not in CONFLICT_STATUSES:
        raise ValueError(f"Invalid conflict status: {value}")


def validate_change_type(value: str) -> None:
    if value not in CHANGE_TYPES:
        raise ValueError(f"Invalid change type: {value}")


def can_transition_queue_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in QUEUE_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_conflict_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in CONFLICT_STATUS_TRANSITIONS.get(current, frozenset())
