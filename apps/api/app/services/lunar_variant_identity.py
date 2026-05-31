from __future__ import annotations

import hashlib

from app.services.lunar_variant_classifier import LunarVariantClassification

def build_issue_release_uuid(*, publisher: str, series_name: str, issue_number: str) -> str:
    parts = [publisher.strip(), series_name.strip(), issue_number.strip()]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"lunar-issue-{digest}"


def build_variant_uuid(
    *,
    source_item_code: str,
    upc: str = "",
    classification: LunarVariantClassification,
) -> str:
    parts = [
        source_item_code.strip(),
        upc.strip(),
        classification.cover_code or "",
        str(classification.ratio_value or ""),
        classification.ratio_type or "",
        classification.variant_name,
        classification.variant_description[:120],
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"lunar-var-{digest}"


def build_canonical_issue_title(*, series_name: str, issue_number: str) -> str:
    return f"{series_name} #{issue_number}"
