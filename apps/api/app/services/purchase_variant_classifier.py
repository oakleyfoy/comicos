"""P53-03 — deterministic variant type classification from release metadata."""

from __future__ import annotations

import re

from app.models.release_intelligence import ReleaseVariant

RATIO_TEXT_RE = re.compile(r"\b1\s*:\s*(\d+)\b", re.IGNORECASE)
KNOWN_RATIO_DENOMINATORS = frozenset({10, 25, 50, 100})

COVER_A_RE = re.compile(
    r"\b(cover\s+a|a\s+cover|main\s+cover|cvr\s+a|standard\s+cover\s+a)\b",
    re.IGNORECASE,
)
OPEN_ORDER_RE = re.compile(
    r"\b(open\s+order|regular\s+cover|cover\s+[b-z]|cvr\s+[b-z])\b",
    re.IGNORECASE,
)
INCENTIVE_RE = re.compile(r"\b(incentive|inc\s+1\s*:|retailer\s+incentive)\b", re.IGNORECASE)
STORE_EXCLUSIVE_RE = re.compile(
    r"\b(store\s+exclusive|retailer\s+exclusive|exclusive\s+to)\b",
    re.IGNORECASE,
)


def parse_ratio_denominator(*, text: str, ratio_value: int | None) -> int | None:
    if ratio_value is not None and ratio_value > 0:
        return int(ratio_value)
    match = RATIO_TEXT_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def classify_purchase_variant_type(
    *,
    variant: ReleaseVariant | None,
    fallback_label: str = "Cover A",
) -> tuple[str, str]:
    """
    Return (variant_type, cover_label).
    variant_type is one of PURCHASE_VARIANT_TYPES.
    """
    if variant is None:
        return "COVER_A", fallback_label

    name = (variant.variant_name or "").strip()
    vtype_field = (variant.variant_type or "").strip()
    combined = f"{name} {vtype_field}".strip()
    lower = combined.lower()

    cover_label = name or fallback_label

    if STORE_EXCLUSIVE_RE.search(combined):
        return "STORE_EXCLUSIVE", cover_label

    if variant.is_incentive_variant or INCENTIVE_RE.search(combined):
        return "INCENTIVE", cover_label

    ratio_denom = parse_ratio_denominator(text=combined, ratio_value=variant.ratio_value)
    if ratio_denom is not None and ratio_denom > 1:
        return "RATIO", cover_label

    if COVER_A_RE.search(combined) or lower in {"cover", "cover a", "a"}:
        return "COVER_A", cover_label

    if OPEN_ORDER_RE.search(combined) or vtype_field.upper() in {"OPEN_ORDER", "COVER", "OPEN"}:
        return "OPEN_ORDER", cover_label

    if vtype_field.upper() in {"INCENTIVE"}:
        return "INCENTIVE", cover_label
    if vtype_field.upper() in {"RATIO", "RATIO_VARIANT"}:
        return "RATIO", cover_label
    if vtype_field.upper() in {"STORE_EXCLUSIVE", "EXCLUSIVE"}:
        return "STORE_EXCLUSIVE", cover_label

    return "UNKNOWN", cover_label


def ratio_risk_tier(denominator: int | None) -> str:
    """Lowest risk at 1:10; 1:100 is highest risk."""
    if denominator is None:
        return "unknown"
    if denominator <= 10:
        return "low"
    if denominator <= 25:
        return "moderate"
    if denominator <= 50:
        return "high"
    return "extreme"
