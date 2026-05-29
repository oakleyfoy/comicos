from __future__ import annotations

from dataclasses import dataclass


SALE_STATUS_DRAFT = "draft"
SALE_STATUS_COMPLETED = "completed"
SALE_STATUS_VOIDED = "voided"

LINE_ITEM_STATUS_ADDED = "added"
LINE_ITEM_STATUS_REMOVED = "removed"
LINE_ITEM_STATUS_SOLD = "sold"

PAYMENT_STATUS_RECORDED = "recorded"
PAYMENT_STATUS_VOIDED = "voided"

PAYMENT_METHOD_CASH = "cash"
PAYMENT_METHOD_CARD_EXTERNAL = "card_external"
PAYMENT_METHOD_VENMO_EXTERNAL = "venmo_external"
PAYMENT_METHOD_PAYPAL_EXTERNAL = "paypal_external"
PAYMENT_METHOD_OTHER_EXTERNAL = "other_external"

SALE_SOURCE_MOBILE = "mobile"
SALE_SOURCE_CONVENTION = "convention"
SALE_SOURCE_OFFLINE = "offline"

SALE_STATUSES: tuple[str, ...] = (
    SALE_STATUS_DRAFT,
    SALE_STATUS_COMPLETED,
    SALE_STATUS_VOIDED,
)

LINE_ITEM_STATUSES: tuple[str, ...] = (
    LINE_ITEM_STATUS_ADDED,
    LINE_ITEM_STATUS_REMOVED,
    LINE_ITEM_STATUS_SOLD,
)

PAYMENT_STATUSES: tuple[str, ...] = (
    PAYMENT_STATUS_RECORDED,
    PAYMENT_STATUS_VOIDED,
)

PAYMENT_METHODS: tuple[str, ...] = (
    PAYMENT_METHOD_CASH,
    PAYMENT_METHOD_CARD_EXTERNAL,
    PAYMENT_METHOD_VENMO_EXTERNAL,
    PAYMENT_METHOD_PAYPAL_EXTERNAL,
    PAYMENT_METHOD_OTHER_EXTERNAL,
)

SALE_SOURCES: tuple[str, ...] = (
    SALE_SOURCE_MOBILE,
    SALE_SOURCE_CONVENTION,
    SALE_SOURCE_OFFLINE,
)

SALE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    SALE_STATUS_DRAFT: frozenset({SALE_STATUS_COMPLETED, SALE_STATUS_VOIDED}),
    SALE_STATUS_COMPLETED: frozenset(),
    SALE_STATUS_VOIDED: frozenset(),
}

LINE_ITEM_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    LINE_ITEM_STATUS_ADDED: frozenset({LINE_ITEM_STATUS_REMOVED, LINE_ITEM_STATUS_SOLD}),
    LINE_ITEM_STATUS_REMOVED: frozenset(),
    LINE_ITEM_STATUS_SOLD: frozenset(),
}

PAYMENT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    PAYMENT_STATUS_RECORDED: frozenset({PAYMENT_STATUS_VOIDED}),
    PAYMENT_STATUS_VOIDED: frozenset(),
}


@dataclass(frozen=True)
class QuickSaleStateDefinition:
    state_key: str
    state_group: str
    display_name: str


def list_sale_statuses() -> tuple[str, ...]:
    return SALE_STATUSES


def list_line_item_statuses() -> tuple[str, ...]:
    return LINE_ITEM_STATUSES


def list_payment_statuses() -> tuple[str, ...]:
    return PAYMENT_STATUSES


def list_payment_methods() -> tuple[str, ...]:
    return PAYMENT_METHODS


def list_sale_sources() -> tuple[str, ...]:
    return SALE_SOURCES


def validate_sale_status(value: str) -> None:
    if value not in SALE_STATUSES:
        raise ValueError(f"Invalid sale status: {value}")


def validate_line_item_status(value: str) -> None:
    if value not in LINE_ITEM_STATUSES:
        raise ValueError(f"Invalid line item status: {value}")


def validate_payment_status(value: str) -> None:
    if value not in PAYMENT_STATUSES:
        raise ValueError(f"Invalid payment status: {value}")


def validate_payment_method(value: str) -> None:
    if value not in PAYMENT_METHODS:
        raise ValueError(f"Invalid payment method: {value}")


def validate_sale_source(value: str) -> None:
    if value not in SALE_SOURCES:
        raise ValueError(f"Invalid sale source: {value}")


def can_transition_sale_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in SALE_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_line_item_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in LINE_ITEM_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_payment_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in PAYMENT_STATUS_TRANSITIONS.get(current, frozenset())
