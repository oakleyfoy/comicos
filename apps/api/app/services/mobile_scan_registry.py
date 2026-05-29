from __future__ import annotations

import re
from dataclasses import dataclass


SCAN_TYPE_BARCODE = "barcode"
SCAN_TYPE_QR = "qr"
SCAN_TYPE_UPC = "upc"
SCAN_TYPE_INVENTORY_IDENTIFIER = "inventory_identifier"

SCAN_STATUS_CAPTURED = "captured"
SCAN_STATUS_LOOKUP_COMPLETE = "lookup_complete"
SCAN_STATUS_STAGED = "staged"
SCAN_STATUS_REJECTED = "rejected"

STAGING_STATUS_PENDING = "pending"
STAGING_STATUS_APPROVED = "approved"
STAGING_STATUS_ARCHIVED = "archived"

SCAN_TYPES: tuple[str, ...] = (
    SCAN_TYPE_BARCODE,
    SCAN_TYPE_QR,
    SCAN_TYPE_UPC,
    SCAN_TYPE_INVENTORY_IDENTIFIER,
)

SCAN_STATUSES: tuple[str, ...] = (
    SCAN_STATUS_CAPTURED,
    SCAN_STATUS_LOOKUP_COMPLETE,
    SCAN_STATUS_STAGED,
    SCAN_STATUS_REJECTED,
)

STAGING_STATUSES: tuple[str, ...] = (
    STAGING_STATUS_PENDING,
    STAGING_STATUS_APPROVED,
    STAGING_STATUS_ARCHIVED,
)

SCAN_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    SCAN_STATUS_CAPTURED: frozenset({SCAN_STATUS_LOOKUP_COMPLETE, SCAN_STATUS_REJECTED}),
    SCAN_STATUS_LOOKUP_COMPLETE: frozenset({SCAN_STATUS_STAGED, SCAN_STATUS_REJECTED}),
    SCAN_STATUS_STAGED: frozenset({SCAN_STATUS_REJECTED}),
    SCAN_STATUS_REJECTED: frozenset(),
}

STAGING_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    STAGING_STATUS_PENDING: frozenset({STAGING_STATUS_APPROVED, STAGING_STATUS_ARCHIVED}),
    STAGING_STATUS_APPROVED: frozenset({STAGING_STATUS_ARCHIVED}),
    STAGING_STATUS_ARCHIVED: frozenset(),
}

LOOKUP_TYPE_INVENTORY_ITEM = "inventory_item"
LOOKUP_TYPE_MARKETPLACE_LISTING = "marketplace_listing"
LOOKUP_TYPE_STOREFRONT_MAPPING = "storefront_mapping"
LOOKUP_TYPE_KNOWN_UPC = "known_upc"

LOOKUP_TYPES: tuple[str, ...] = (
    LOOKUP_TYPE_INVENTORY_ITEM,
    LOOKUP_TYPE_KNOWN_UPC,
    LOOKUP_TYPE_MARKETPLACE_LISTING,
    LOOKUP_TYPE_STOREFRONT_MAPPING,
)


@dataclass(frozen=True)
class MobileScanStateDefinition:
    state_key: str
    state_group: str
    display_name: str


MOBILE_SCAN_STATE_DEFINITIONS: tuple[MobileScanStateDefinition, ...] = (
    MobileScanStateDefinition(SCAN_STATUS_CAPTURED, "scan", "Captured"),
    MobileScanStateDefinition(SCAN_STATUS_LOOKUP_COMPLETE, "scan", "Lookup complete"),
    MobileScanStateDefinition(SCAN_STATUS_STAGED, "scan", "Staged"),
    MobileScanStateDefinition(SCAN_STATUS_REJECTED, "scan", "Rejected"),
    MobileScanStateDefinition(STAGING_STATUS_PENDING, "staging", "Pending intake"),
    MobileScanStateDefinition(STAGING_STATUS_APPROVED, "staging", "Approved intake"),
    MobileScanStateDefinition(STAGING_STATUS_ARCHIVED, "staging", "Archived intake"),
)


def list_scan_types() -> tuple[str, ...]:
    return SCAN_TYPES


def list_scan_statuses() -> tuple[str, ...]:
    return SCAN_STATUSES


def list_staging_statuses() -> tuple[str, ...]:
    return STAGING_STATUSES


def list_lookup_types() -> tuple[str, ...]:
    return LOOKUP_TYPES


def validate_scan_type(value: str) -> None:
    if value not in SCAN_TYPES:
        raise ValueError(f"Invalid scan type: {value}")


def validate_scan_status(value: str) -> None:
    if value not in SCAN_STATUSES:
        raise ValueError(f"Invalid scan status: {value}")


def validate_staging_status(value: str) -> None:
    if value not in STAGING_STATUSES:
        raise ValueError(f"Invalid staging status: {value}")


def can_transition_scan_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in SCAN_STATUS_TRANSITIONS.get(current, frozenset())


def can_transition_staging_status(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in STAGING_STATUS_TRANSITIONS.get(current, frozenset())


def normalize_scan_value(scan_type: str, scan_value: str) -> str:
    validate_scan_type(scan_type)
    trimmed = scan_value.strip()
    if scan_type in {SCAN_TYPE_BARCODE, SCAN_TYPE_UPC}:
        digits = re.sub(r"\D", "", trimmed)
        return digits or trimmed.lower()
    if scan_type == SCAN_TYPE_QR:
        return trimmed
    if scan_type == SCAN_TYPE_INVENTORY_IDENTIFIER:
        return trimmed.lower()
    return trimmed.lower()
