"""Safe-match validation for comic UPC barcodes.

Modern direct-market comics encode the publisher in the 12-digit UPC prefix and the
issue/variant/printing in the 5-digit supplement. This module refuses catalog matches
that contradict the barcode (wrong publisher, wrong issue, impossible era), so the app
returns ``no_safe_match`` instead of confidently identifying the wrong book.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.services.catalog_ingestion_service import normalize_upc

MatchStatus = Literal["exact_match", "no_safe_match", "ambiguous_base_upc", "not_found", "unreadable"]

# 6-digit UPC prefix -> canonical publisher keyword(s). Matched publisher must contain one.
PUBLISHER_PREFIXES: dict[str, tuple[str, ...]] = {
    "761941": ("dc",),          # DC Comics
    "759606": ("marvel",),      # Marvel
    "761568": ("dark horse",),  # Dark Horse (common direct-market prefix)
    "709853": ("image",),       # Image (common)
}

# Modern UPC era guard: a modern direct-market UPC should not resolve to a pre-1976 book.
MODERN_UPC_MIN_YEAR = 1976


@dataclass(frozen=True)
class ExtensionParse:
    raw: str
    issue_number: int | None
    variant_number: int | None
    printing: int | None


@dataclass(frozen=True)
class BarcodeValidation:
    status: MatchStatus
    reason: str


def base_upc(barcode: str) -> str:
    digits = normalize_upc(barcode)
    return digits[:12] if len(digits) >= 12 else digits


def supplement_extension(barcode: str) -> str:
    digits = normalize_upc(barcode)
    return digits[12:17] if len(digits) >= 17 else ""


def parse_comic_upc_extension(extension: str) -> ExtensionParse | None:
    """Parse a 5-digit DC/Marvel supplement: 039 2 1 -> issue 39, variant 2, printing 1."""
    digits = re.sub(r"\D", "", extension or "")
    if len(digits) != 5:
        return None
    issue = int(digits[:3])
    variant = int(digits[3])
    printing = int(digits[4])
    return ExtensionParse(
        raw=digits,
        issue_number=issue if issue > 0 else None,
        variant_number=variant,
        printing=printing,
    )


def expected_publisher_keywords(barcode: str) -> tuple[str, ...]:
    prefix = normalize_upc(barcode)[:6]
    return PUBLISHER_PREFIXES.get(prefix, ())


def publisher_matches_expected(actual_publisher: str | None, keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True  # No known prefix rule -> nothing to enforce.
    actual = (actual_publisher or "").casefold()
    if not actual.strip():
        return False
    return any(keyword in actual for keyword in keywords)


def _simple_issue_int(value: str | None) -> int | None:
    text = (value or "").strip().lstrip("#")
    if text.isdigit():
        return int(text)
    if re.fullmatch(r"\d+\.0", text):
        return int(float(text))
    return None


def _year_int(value: str | None) -> int | None:
    match = re.search(r"(18|19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def validate_barcode_catalog_match(
    barcode: str,
    *,
    publisher: str | None,
    issue_number: str | None,
    year: str | None,
) -> BarcodeValidation:
    """Return exact_match only when the catalog record is consistent with the barcode."""
    normalized = normalize_upc(barcode)
    keywords = expected_publisher_keywords(normalized)

    # 1) Publisher family must match the UPC prefix (e.g. 761941 -> DC).
    if not publisher_matches_expected(publisher, keywords):
        return BarcodeValidation(
            "no_safe_match",
            f"Barcode prefix {normalized[:6]} expects {'/'.join(keywords)} but matched publisher "
            f"is {publisher or 'unknown'}.",
        )

    # 2) Extension-encoded issue number must agree with the matched issue (when both are plain ints).
    parsed = parse_comic_upc_extension(supplement_extension(normalized))
    if parsed is not None and parsed.issue_number is not None:
        matched_issue = _simple_issue_int(issue_number)
        if matched_issue is not None and matched_issue != parsed.issue_number:
            return BarcodeValidation(
                "no_safe_match",
                f"Barcode extension encodes issue #{parsed.issue_number} but matched issue is "
                f"#{matched_issue}.",
            )

    # 3) Modern direct-market UPC must not resolve to a pre-1976 record.
    if keywords:
        matched_year = _year_int(year)
        if matched_year is not None and matched_year < MODERN_UPC_MIN_YEAR:
            return BarcodeValidation(
                "no_safe_match",
                f"Modern UPC matched a {matched_year} record (before {MODERN_UPC_MIN_YEAR}).",
            )

    return BarcodeValidation("exact_match", "Catalog record is consistent with the barcode.")
