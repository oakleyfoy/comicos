from __future__ import annotations

import re

CANONICAL_LUNAR_ISSUE_PREFIX = "lunar-issue-"
LEGACY_LUNAR_FLAT_PREFIX = "lunar-"


def is_canonical_lunar_issue_uuid(release_uuid: str) -> bool:
    return release_uuid.startswith(CANONICAL_LUNAR_ISSUE_PREFIX)


def is_legacy_flat_lunar_issue_uuid(release_uuid: str) -> bool:
    """Old flat imports used lunar-{product_code} as the issue release_uuid."""
    if not release_uuid.startswith(LEGACY_LUNAR_FLAT_PREFIX):
        return False
    return not is_canonical_lunar_issue_uuid(release_uuid) and not release_uuid.startswith("lunar-var-")


def classify_lunar_issue_row(*, release_uuid: str) -> str:
    if is_canonical_lunar_issue_uuid(release_uuid):
        return "canonical_lunar_issue"
    if is_legacy_flat_lunar_issue_uuid(release_uuid):
        return "legacy_flat_variant_issue"
    return "other_issue"


def normalize_lunar_issue_number(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        return "1"
    if cleaned.upper().startswith("ISSUE "):
        cleaned = cleaned[6:].strip()
    return cleaned.lstrip("#").strip() or "1"


def parse_issue_number_from_title(title: str) -> str | None:
    match = re.search(r"#\s*([0-9]+(?:\.[0-9]+)?)", title)
    if match:
        return match.group(1)
    return None
