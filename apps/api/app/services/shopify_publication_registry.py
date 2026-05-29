from __future__ import annotations

PUBLICATION_STATUS_DRAFT = "draft"
PUBLICATION_STATUS_READY = "ready"
PUBLICATION_STATUS_PUBLISHED_INTERNAL = "published_internal"
PUBLICATION_STATUS_UNPUBLISHED_INTERNAL = "unpublished_internal"

SYNC_STATUS_PENDING = "pending"
SYNC_STATUS_COMPLETED = "completed"
SYNC_STATUS_FAILED = "failed"

MAPPING_STATUS_MAPPED = "mapped"
MAPPING_STATUS_UNMAPPED = "unmapped"
MAPPING_STATUS_INVALID = "invalid"

PUBLICATION_STATUSES = (
    PUBLICATION_STATUS_DRAFT,
    PUBLICATION_STATUS_READY,
    PUBLICATION_STATUS_PUBLISHED_INTERNAL,
    PUBLICATION_STATUS_UNPUBLISHED_INTERNAL,
)
SYNC_STATUSES = (SYNC_STATUS_PENDING, SYNC_STATUS_COMPLETED, SYNC_STATUS_FAILED)
MAPPING_STATUSES = (MAPPING_STATUS_MAPPED, MAPPING_STATUS_UNMAPPED, MAPPING_STATUS_INVALID)


def normalize_publication_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in PUBLICATION_STATUSES:
        raise ValueError(f"Unsupported publication status: {status}")
    return normalized


def normalize_sync_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in SYNC_STATUSES:
        raise ValueError(f"Unsupported sync status: {status}")
    return normalized


def normalize_mapping_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in MAPPING_STATUSES:
        raise ValueError(f"Unsupported mapping status: {status}")
    return normalized


def derive_publication_status(*, storefront_status: str, mapping_status: str) -> str:
    storefront_normalized = normalize_publication_status(storefront_status)
    mapping_normalized = normalize_mapping_status(mapping_status)
    if mapping_normalized == MAPPING_STATUS_INVALID:
        return PUBLICATION_STATUS_UNPUBLISHED_INTERNAL
    if storefront_normalized == PUBLICATION_STATUS_PUBLISHED_INTERNAL:
        return PUBLICATION_STATUS_PUBLISHED_INTERNAL
    if storefront_normalized == PUBLICATION_STATUS_READY and mapping_normalized == MAPPING_STATUS_MAPPED:
        return PUBLICATION_STATUS_READY
    return storefront_normalized
