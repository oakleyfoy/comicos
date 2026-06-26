"""Barcode multi-frame voting and checksum validation."""

from app.services.barcode_scan_consensus_service import (
    DEFAULT_MIN_VOTES,
    suggest_corrected_barcode,
    validate_single_barcode_read,
    vote_barcode_reads,
)

SUPERMAN_39 = "76194134192703921"


def test_vote_requires_three_identical_reads() -> None:
    two = vote_barcode_reads([SUPERMAN_39, SUPERMAN_39], min_votes=DEFAULT_MIN_VOTES)
    assert two.acceptance == "rejected_no_consensus"
    assert two.vote_count == 2

    three = vote_barcode_reads([SUPERMAN_39, SUPERMAN_39, SUPERMAN_39], min_votes=DEFAULT_MIN_VOTES)
    assert three.acceptance == "accepted"
    assert three.normalized == SUPERMAN_39
    assert three.vote_count == 3


def test_checksum_failure_rejects_single_read() -> None:
    bad = "761941341927"  # valid prefix but wrong check on 12-digit body if truncated wrong
    # Use known bad check digit on 12-digit UPC
    invalid = "761941341928"
    result = validate_single_barcode_read(invalid)
    assert result.acceptance == "rejected_checksum"
    assert result.check_digit_valid is False


def test_valid_full_barcode_accepted() -> None:
    result = validate_single_barcode_read(SUPERMAN_39)
    assert result.acceptance == "accepted"
    assert result.base_upc == "761941341927"
    assert result.extension == "03921"


def test_suggest_corrected_only_when_checksum_fixable() -> None:
    valid = suggest_corrected_barcode(SUPERMAN_39)
    assert valid is None
