from __future__ import annotations

import re
from dataclasses import dataclass

COVER_RE = re.compile(r"\bCVR\s+([A-Z])\b", re.IGNORECASE)
COVER_WORD_RE = re.compile(r"\bCOVER\s+([A-Z])\b", re.IGNORECASE)
RATIO_INC_RE = re.compile(r"\bINC\s+1\s*:\s*(\d+)\b", re.IGNORECASE)
RATIO_BARE_RE = re.compile(r"\b1\s*:\s*(\d+)\b")
ORDER_RATIO_RE = re.compile(r"for every\s+(\d+)\s+copies ordered", re.IGNORECASE)

SPECIAL_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bVIRGIN\b", re.IGNORECASE), "Virgin Variant", "VIRGIN"),
    (re.compile(r"\bFOIL\b", re.IGNORECASE), "Foil Variant", "FOIL"),
    (re.compile(r"\bBLANK\b", re.IGNORECASE), "Blank Variant", "BLANK"),
    (re.compile(r"\bSKETCH\b", re.IGNORECASE), "Sketch Variant", "SKETCH"),
    (re.compile(r"\bMETAL\b", re.IGNORECASE), "Metal Variant", "METAL"),
    (re.compile(r"\bGLOW\b", re.IGNORECASE), "Glow Variant", "GLOW"),
    (re.compile(r"\bSIGNED\b", re.IGNORECASE), "Signed Edition", "SIGNED"),
    (re.compile(r"\bSPECIAL\s+ED(?:ITION)?\b", re.IGNORECASE), "Special Edition", "SPECIAL_EDITION"),
    (re.compile(r"\bCARD\s+STOCK\b", re.IGNORECASE), "Card Stock Variant", "CARD_STOCK"),
)


@dataclass(frozen=True)
class LunarVariantClassification:
    variant_name: str
    cover_code: str | None
    ratio_value: int | None
    ratio_type: str | None
    is_incentive_variant: bool
    variant_type: str
    cover_artist: str | None = None
    variant_description: str = ""


def _extract_cover_code(text: str) -> str | None:
    match = COVER_RE.search(text) or COVER_WORD_RE.search(text)
    if match:
        return match.group(1).upper()
    return None


def _extract_ratio(text: str) -> tuple[int | None, str | None, bool]:
    match = RATIO_INC_RE.search(text)
    if match:
        value = int(match.group(1))
        return value, "INC", True
    match = ORDER_RATIO_RE.search(text)
    if match:
        value = int(match.group(1))
        return value, "ORDER", True
    match = RATIO_BARE_RE.search(text)
    if match:
        value = int(match.group(1))
        return value, "RATIO", value > 1
    return None, None, False


def _extract_cover_artist(title: str) -> str | None:
    match = re.search(r"CVR\s+[A-Z]\s+([A-Z][A-Z\s\.\'-]+?)(?:\s+CARD|\s+INC|\s+FOIL|\s+VIRGIN|$)", title, re.IGNORECASE)
    if match:
        artist = match.group(1).strip()
        if len(artist) > 2:
            return artist.title()
    return None


def classify_lunar_variant(
    *,
    title: str,
    variant_desc: str = "",
    full_title: str = "",
) -> LunarVariantClassification:
    combined = " ".join(part for part in (full_title, title, variant_desc) if part).strip()
    upper = combined.upper()
    cover_code = _extract_cover_code(combined)
    ratio_value, ratio_type, is_incentive = _extract_ratio(combined)
    special_label = ""
    special_type = ""
    for pattern, label, vtype in SPECIAL_PATTERNS:
        if pattern.search(combined):
            special_label = label
            special_type = vtype
            break

    cover_artist = _extract_cover_artist(combined)

    if cover_code:
        variant_name = f"Cover {cover_code}"
        if ratio_value:
            variant_name = f"{variant_name} 1:{ratio_value}"
        if special_label and special_label not in variant_name:
            variant_name = f"{variant_name} {special_label}"
        variant_type = "INCENTIVE" if is_incentive else "COVER"
    elif ratio_value:
        variant_name = f"1:{ratio_value}"
        if special_label:
            variant_name = f"{variant_name} {special_label}"
        variant_type = "INCENTIVE"
        is_incentive = True
    elif special_label:
        variant_name = special_label
        variant_type = special_type or "SPECIAL"
    elif "RETAILER" in upper and "INCENTIVE" in upper:
        variant_name = "Retailer Incentive Variant"
        variant_type = "INCENTIVE"
        is_incentive = True
    else:
        variant_name = "Standard Cover"
        variant_type = "OPEN_ORDER"

    return LunarVariantClassification(
        variant_name=variant_name.strip(),
        cover_code=cover_code,
        ratio_value=ratio_value,
        ratio_type=ratio_type,
        is_incentive_variant=is_incentive,
        variant_type=variant_type,
        cover_artist=cover_artist,
        variant_description=variant_desc or combined[:240],
    )
