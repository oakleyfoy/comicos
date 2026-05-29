from __future__ import annotations

from dataclasses import dataclass


TRUST_STATUS_TRUSTED = "trusted"
TRUST_STATUS_UNTRUSTED = "untrusted"
TRUST_STATUS_SUSPENDED = "suspended"

POLICY_STATUS_ACTIVE = "active"
POLICY_STATUS_INACTIVE = "inactive"

ACCESS_RESULT_ALLOWED = "allowed"
ACCESS_RESULT_DENIED = "denied"

POLICY_KEY_REQUIRE_TRUSTED_DEVICE = "require_trusted_device"
POLICY_KEY_BLOCK_SUSPENDED_DEVICE = "block_suspended_device"
POLICY_KEY_REQUIRE_ACTIVE_SESSION = "require_active_session"
POLICY_KEY_ALLOW_OFFLINE_ACTIONS = "allow_offline_actions"

TRUST_STATUSES: tuple[str, ...] = (
    TRUST_STATUS_TRUSTED,
    TRUST_STATUS_UNTRUSTED,
    TRUST_STATUS_SUSPENDED,
)

POLICY_STATUSES: tuple[str, ...] = (
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_INACTIVE,
)

ACCESS_RESULTS: tuple[str, ...] = (
    ACCESS_RESULT_ALLOWED,
    ACCESS_RESULT_DENIED,
)

POLICY_KEYS: tuple[str, ...] = (
    POLICY_KEY_REQUIRE_TRUSTED_DEVICE,
    POLICY_KEY_BLOCK_SUSPENDED_DEVICE,
    POLICY_KEY_REQUIRE_ACTIVE_SESSION,
    POLICY_KEY_ALLOW_OFFLINE_ACTIONS,
)

TRUST_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    TRUST_STATUS_TRUSTED: frozenset({TRUST_STATUS_UNTRUSTED, TRUST_STATUS_SUSPENDED}),
    TRUST_STATUS_UNTRUSTED: frozenset({TRUST_STATUS_TRUSTED, TRUST_STATUS_SUSPENDED}),
    TRUST_STATUS_SUSPENDED: frozenset({TRUST_STATUS_TRUSTED, TRUST_STATUS_UNTRUSTED}),
}

POLICY_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    POLICY_STATUS_ACTIVE: frozenset({POLICY_STATUS_INACTIVE}),
    POLICY_STATUS_INACTIVE: frozenset({POLICY_STATUS_ACTIVE}),
}


@dataclass(frozen=True)
class MobileDeviceSecurityStateDefinition:
    state_key: str
    state_group: str
    display_name: str


def list_trust_statuses() -> tuple[str, ...]:
    return TRUST_STATUSES


def list_policy_statuses() -> tuple[str, ...]:
    return POLICY_STATUSES


def list_access_results() -> tuple[str, ...]:
    return ACCESS_RESULTS


def list_policy_keys() -> tuple[str, ...]:
    return POLICY_KEYS


def validate_trust_status(value: str) -> None:
    if value not in TRUST_STATUSES:
        raise ValueError(f"Invalid trust status: {value}")


def validate_policy_status(value: str) -> None:
    if value not in POLICY_STATUSES:
        raise ValueError(f"Invalid policy status: {value}")


def validate_access_result(value: str) -> None:
    if value not in ACCESS_RESULTS:
        raise ValueError(f"Invalid access result: {value}")


def validate_policy_key(value: str) -> None:
    if value not in POLICY_KEYS:
        raise ValueError(f"Invalid policy key: {value}")


def can_transition_trust_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in TRUST_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_policy_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in POLICY_STATUS_TRANSITIONS.get(current, frozenset())
