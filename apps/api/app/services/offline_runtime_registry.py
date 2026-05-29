from __future__ import annotations

from dataclasses import dataclass


DEVICE_STATUS_ACTIVE = "active"
DEVICE_STATUS_INACTIVE = "inactive"
DEVICE_STATUS_SUSPENDED = "suspended"

SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_EXPIRED = "expired"
SESSION_STATUS_TERMINATED = "terminated"

CONTRACT_TYPE_INVENTORY = "inventory"
CONTRACT_TYPE_TRANSACTION = "transaction"
CONTRACT_TYPE_LOOKUP = "lookup"
CONTRACT_TYPE_METADATA = "metadata"

DEVICE_STATUSES: tuple[str, ...] = (
    DEVICE_STATUS_ACTIVE,
    DEVICE_STATUS_INACTIVE,
    DEVICE_STATUS_SUSPENDED,
)

SESSION_STATUSES: tuple[str, ...] = (
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_EXPIRED,
    SESSION_STATUS_TERMINATED,
)

SYNC_CONTRACT_TYPES: tuple[str, ...] = (
    CONTRACT_TYPE_INVENTORY,
    CONTRACT_TYPE_TRANSACTION,
    CONTRACT_TYPE_LOOKUP,
    CONTRACT_TYPE_METADATA,
)

DEVICE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    DEVICE_STATUS_ACTIVE: frozenset({DEVICE_STATUS_INACTIVE, DEVICE_STATUS_SUSPENDED}),
    DEVICE_STATUS_INACTIVE: frozenset({DEVICE_STATUS_ACTIVE, DEVICE_STATUS_SUSPENDED}),
    DEVICE_STATUS_SUSPENDED: frozenset({DEVICE_STATUS_INACTIVE, DEVICE_STATUS_ACTIVE}),
}

SESSION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    SESSION_STATUS_ACTIVE: frozenset({SESSION_STATUS_EXPIRED, SESSION_STATUS_TERMINATED}),
    SESSION_STATUS_EXPIRED: frozenset(),
    SESSION_STATUS_TERMINATED: frozenset(),
}


@dataclass(frozen=True)
class OfflineRuntimeStateDefinition:
    state_key: str
    state_group: str
    display_name: str


OFFLINE_RUNTIME_STATE_DEFINITIONS: tuple[OfflineRuntimeStateDefinition, ...] = (
    OfflineRuntimeStateDefinition(DEVICE_STATUS_ACTIVE, "device", "Active device"),
    OfflineRuntimeStateDefinition(DEVICE_STATUS_INACTIVE, "device", "Inactive device"),
    OfflineRuntimeStateDefinition(DEVICE_STATUS_SUSPENDED, "device", "Suspended device"),
    OfflineRuntimeStateDefinition(SESSION_STATUS_ACTIVE, "session", "Active session"),
    OfflineRuntimeStateDefinition(SESSION_STATUS_EXPIRED, "session", "Expired session"),
    OfflineRuntimeStateDefinition(SESSION_STATUS_TERMINATED, "session", "Terminated session"),
)


def list_device_statuses() -> tuple[str, ...]:
    return DEVICE_STATUSES


def list_session_statuses() -> tuple[str, ...]:
    return SESSION_STATUSES


def list_sync_contract_types() -> tuple[str, ...]:
    return SYNC_CONTRACT_TYPES


def validate_device_status(value: str) -> None:
    if value not in DEVICE_STATUSES:
        raise ValueError(f"Invalid device status: {value}")


def validate_session_status(value: str) -> None:
    if value not in SESSION_STATUSES:
        raise ValueError(f"Invalid session status: {value}")


def validate_sync_contract_type(value: str) -> None:
    if value not in SYNC_CONTRACT_TYPES:
        raise ValueError(f"Invalid sync contract type: {value}")


def can_transition_device_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in DEVICE_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_session_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in SESSION_STATUS_TRANSITIONS.get(current, frozenset())
