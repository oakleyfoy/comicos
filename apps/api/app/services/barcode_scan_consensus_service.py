"""Multi-read barcode consensus, checksum validation, and safe normalization.

Comic scans should not auto-accept a single noisy frame. Callers collect 5–15 reads
and pass them to ``vote_barcode_reads``; a barcode is accepted only when the same
normalized value appears at least ``min_votes`` times (default 3).

Raw scanner output is preserved separately from the normalized lookup key (12-digit
base UPC + optional 5-digit supplement — never blind trim).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.services.barcode_validation_service import base_upc, supplement_extension
from app.services.catalog_ingestion_service import (
    barcode_usable_for_lookup,
    merge_comic_upc_decodes,
    normalize_upc,
    upc_check_digit_valid,
)
from app.services.photo_import_barcode_vision import normalize_comic_scan_barcode

DEFAULT_MIN_VOTES = 3
MAX_VOTE_SAMPLES = 15

BarcodeAcceptance = Literal["accepted", "rejected_checksum", "rejected_no_consensus", "rejected_empty"]


@dataclass(frozen=True)
class BarcodeScanValidation:
    acceptance: BarcodeAcceptance
    raw_scan: str
    normalized: str
    base_upc: str
    extension: str
    check_digit_valid: bool
    vote_count: int
    possible_corrected: str | None
    reason: str


def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def compute_upc_a_check_digit(twelve_or_eleven: str) -> str | None:
    """Return the 12th check digit for UPC-A (11 or 12 digit input)."""
    digits = _digits_only(twelve_or_eleven)
    if len(digits) == 12:
        digits = digits[:11]
    if len(digits) != 11 or not digits.isdigit():
        return None
    ean13 = "0" + digits
    total = sum(int(ch) * (1 if idx % 2 == 0 else 3) for idx, ch in enumerate(ean13))
    check = (10 - (total % 10)) % 10
    return str(check)


def suggest_corrected_barcode(raw: str) -> str | None:
    """When checksum fails, suggest a single-digit correction on the 12-digit UPC body."""
    digits = _digits_only(raw)
    if not digits:
        return None
    body12 = digits[:12] if len(digits) >= 12 else digits
    if upc_check_digit_valid(body12):
        return None
    if upc_check_digit_valid(digits):
        return None
    if len(digits) >= 17:
        body = digits[:12]
        supplement = digits[12:17]
        check = compute_upc_a_check_digit(body[:11])
        if check is None:
            return None
        corrected_body = body[:11] + check
        candidate = corrected_body + supplement
        if upc_check_digit_valid(corrected_body):
            return candidate
        return None
    if len(digits) in (11, 12, 13):
        body11 = digits[:11] if len(digits) >= 11 else digits
        check = compute_upc_a_check_digit(body11)
        if check is None:
            return None
        candidate12 = body11 + check
        if upc_check_digit_valid(candidate12):
            merged = merge_comic_upc_decodes([candidate12, digits]) or candidate12
            return normalize_comic_scan_barcode(merged) or merged
    return None


def normalize_scan_preserving_supplement(raw: str) -> str:
    """Normalized lookup key without dropping supplement digits."""
    merged = merge_comic_upc_decodes([_digits_only(raw)])
    if merged:
        return merged
    return normalize_comic_scan_barcode(raw) or normalize_upc(raw)


def validate_single_barcode_read(raw: str) -> BarcodeScanValidation:
    digits = _digits_only(raw)
    normalized = normalize_scan_preserving_supplement(raw)
    check_ok = bool(normalized) and upc_check_digit_valid(normalized[:12] if len(normalized) >= 12 else normalized)
    if not digits:
        return BarcodeScanValidation(
            acceptance="rejected_empty",
            raw_scan="",
            normalized="",
            base_upc="",
            extension="",
            check_digit_valid=False,
            vote_count=0,
            possible_corrected=None,
            reason="No barcode digits in scan.",
        )
    if not check_ok:
        corrected = suggest_corrected_barcode(digits)
        return BarcodeScanValidation(
            acceptance="rejected_checksum",
            raw_scan=digits[:64],
            normalized=normalized,
            base_upc=base_upc(normalized) if normalized else base_upc(digits),
            extension=supplement_extension(normalized) if normalized else supplement_extension(digits),
            check_digit_valid=False,
            vote_count=1,
            possible_corrected=corrected,
            reason="UPC/EAN check digit failed.",
        )
    return BarcodeScanValidation(
        acceptance="accepted",
        raw_scan=digits[:64],
        normalized=normalized[:64],
        base_upc=base_upc(normalized)[:16],
        extension=(supplement_extension(normalized) or None) or "",
        check_digit_valid=True,
        vote_count=1,
        possible_corrected=None,
        reason="Valid barcode.",
    )


def vote_barcode_reads(
    reads: list[str],
    *,
    min_votes: int = DEFAULT_MIN_VOTES,
) -> BarcodeScanValidation:
    """Pick the winning barcode when the same normalized value appears ``min_votes``+ times."""
    if min_votes < 1:
        min_votes = DEFAULT_MIN_VOTES
    samples = reads[:MAX_VOTE_SAMPLES]
    tallies: dict[str, list[str]] = {}
    for raw in samples:
        digits = _digits_only(raw)
        if not digits:
            continue
        key = normalize_scan_preserving_supplement(digits) or digits
        tallies.setdefault(key, []).append(digits)

    if not tallies:
        return validate_single_barcode_read("")

    winner_key, winner_raws = max(tallies.items(), key=lambda kv: len(kv[1]))
    vote_count = len(winner_raws)
    raw_scan = max(winner_raws, key=len)  # prefer longest raw (supplement present)

    if vote_count < min_votes:
        return BarcodeScanValidation(
            acceptance="rejected_no_consensus",
            raw_scan=raw_scan[:64],
            normalized=winner_key[:64],
            base_upc=base_upc(winner_key)[:16],
            extension=supplement_extension(winner_key) or "",
            check_digit_valid=upc_check_digit_valid(winner_key[:12] if len(winner_key) >= 12 else winner_key),
            vote_count=vote_count,
            possible_corrected=suggest_corrected_barcode(raw_scan),
            reason=f"Need {min_votes} identical reads; got {vote_count}.",
        )

    single = validate_single_barcode_read(raw_scan)
    if single.acceptance != "accepted":
        single = BarcodeScanValidation(
            acceptance=single.acceptance,
            raw_scan=single.raw_scan,
            normalized=single.normalized or winner_key[:64],
            base_upc=single.base_upc or base_upc(winner_key)[:16],
            extension=single.extension or supplement_extension(winner_key) or "",
            check_digit_valid=single.check_digit_valid,
            vote_count=vote_count,
            possible_corrected=single.possible_corrected,
            reason=single.reason,
        )
    else:
        single = BarcodeScanValidation(
            acceptance="accepted",
            raw_scan=raw_scan[:64],
            normalized=single.normalized,
            base_upc=single.base_upc,
            extension=single.extension,
            check_digit_valid=True,
            vote_count=vote_count,
            possible_corrected=None,
            reason=f"Consensus after {vote_count} reads.",
        )
    return single


def barcode_usable_after_validation(validation: BarcodeScanValidation) -> bool:
    return validation.acceptance == "accepted" and barcode_usable_for_lookup(validation.normalized)
