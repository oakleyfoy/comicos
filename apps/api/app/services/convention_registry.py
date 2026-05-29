from __future__ import annotations

from dataclasses import dataclass


SESSION_STATUS_PLANNED = "planned"
SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_ARCHIVED = "archived"

BOOTH_STATUS_SETUP = "setup"
BOOTH_STATUS_ACTIVE = "active"
BOOTH_STATUS_PAUSED = "paused"
BOOTH_STATUS_CLOSED = "closed"

STAGE_STATUS_STAGED = "staged"
STAGE_STATUS_DISPLAYED = "displayed"
STAGE_STATUS_RESERVED = "reserved"
STAGE_STATUS_REMOVED = "removed"

ACTIVITY_SESSION_CREATED = "session_created"
ACTIVITY_INVENTORY_STAGED = "inventory_staged"
ACTIVITY_INVENTORY_REMOVED = "inventory_removed"
ACTIVITY_BOOTH_OPENED = "booth_opened"
ACTIVITY_BOOTH_CLOSED = "booth_closed"

SESSION_STATUSES: tuple[str, ...] = (
    SESSION_STATUS_PLANNED,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_ARCHIVED,
)

BOOTH_STATUSES: tuple[str, ...] = (
    BOOTH_STATUS_SETUP,
    BOOTH_STATUS_ACTIVE,
    BOOTH_STATUS_PAUSED,
    BOOTH_STATUS_CLOSED,
)

STAGE_STATUSES: tuple[str, ...] = (
    STAGE_STATUS_STAGED,
    STAGE_STATUS_DISPLAYED,
    STAGE_STATUS_RESERVED,
    STAGE_STATUS_REMOVED,
)

ACTIVITY_TYPES: tuple[str, ...] = (
    ACTIVITY_SESSION_CREATED,
    ACTIVITY_INVENTORY_STAGED,
    ACTIVITY_INVENTORY_REMOVED,
    ACTIVITY_BOOTH_OPENED,
    ACTIVITY_BOOTH_CLOSED,
)

SESSION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    SESSION_STATUS_PLANNED: frozenset({SESSION_STATUS_ACTIVE, SESSION_STATUS_ARCHIVED}),
    SESSION_STATUS_ACTIVE: frozenset({SESSION_STATUS_COMPLETED, SESSION_STATUS_ARCHIVED}),
    SESSION_STATUS_COMPLETED: frozenset({SESSION_STATUS_ARCHIVED}),
    SESSION_STATUS_ARCHIVED: frozenset(),
}

BOOTH_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    BOOTH_STATUS_SETUP: frozenset({BOOTH_STATUS_ACTIVE, BOOTH_STATUS_CLOSED}),
    BOOTH_STATUS_ACTIVE: frozenset({BOOTH_STATUS_PAUSED, BOOTH_STATUS_CLOSED}),
    BOOTH_STATUS_PAUSED: frozenset({BOOTH_STATUS_ACTIVE, BOOTH_STATUS_CLOSED}),
    BOOTH_STATUS_CLOSED: frozenset(),
}

STAGE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    STAGE_STATUS_STAGED: frozenset({STAGE_STATUS_DISPLAYED, STAGE_STATUS_RESERVED, STAGE_STATUS_REMOVED}),
    STAGE_STATUS_DISPLAYED: frozenset({STAGE_STATUS_RESERVED, STAGE_STATUS_REMOVED}),
    STAGE_STATUS_RESERVED: frozenset({STAGE_STATUS_DISPLAYED, STAGE_STATUS_REMOVED}),
    STAGE_STATUS_REMOVED: frozenset(),
}


@dataclass(frozen=True)
class ConventionStateDefinition:
    state_key: str
    state_group: str
    display_name: str


def list_session_statuses() -> tuple[str, ...]:
    return SESSION_STATUSES


def list_booth_statuses() -> tuple[str, ...]:
    return BOOTH_STATUSES


def list_stage_statuses() -> tuple[str, ...]:
    return STAGE_STATUSES


def list_activity_types() -> tuple[str, ...]:
    return ACTIVITY_TYPES


def validate_session_status(value: str) -> None:
    if value not in SESSION_STATUSES:
        raise ValueError(f"Invalid session status: {value}")


def validate_booth_status(value: str) -> None:
    if value not in BOOTH_STATUSES:
        raise ValueError(f"Invalid booth status: {value}")


def validate_stage_status(value: str) -> None:
    if value not in STAGE_STATUSES:
        raise ValueError(f"Invalid stage status: {value}")


def validate_activity_type(value: str) -> None:
    if value not in ACTIVITY_TYPES:
        raise ValueError(f"Invalid activity type: {value}")


def can_transition_session_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in SESSION_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_booth_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in BOOTH_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_stage_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in STAGE_STATUS_TRANSITIONS.get(current, frozenset())
