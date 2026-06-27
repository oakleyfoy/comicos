"""Safe-match validation refuses implausible catalog records for comic UPCs."""

from __future__ import annotations

from app.services.barcode_validation_service import (
    parse_comic_upc_extension,
    supplement_extension,
    validate_barcode_catalog_match,
)

SUPERMAN_39_FULL = "76194134192703921"  # 761941... DC prefix + 03921 supplement


def test_extension_parses_issue_variant_printing() -> None:
    parsed = parse_comic_upc_extension("03921")
    assert parsed is not None
    assert parsed.issue_number == 39
    assert parsed.variant_number == 2
    assert parsed.printing == 1


def test_extension_requires_five_digits() -> None:
    assert parse_comic_upc_extension("0392") is None
    assert parse_comic_upc_extension("") is None


def test_supplement_extension_extracted_from_full_barcode() -> None:
    assert supplement_extension(SUPERMAN_39_FULL) == "03921"
    assert supplement_extension("761941341927") == ""


def test_bad_record_rejected_when_publisher_is_harvey() -> None:
    # 761941 prefix is DC; a Harvey/1952/#13 record must be refused.
    result = validate_barcode_catalog_match(
        SUPERMAN_39_FULL,
        publisher="Harvey",
        issue_number="13",
        year="1952",
    )
    assert result.status == "no_safe_match"
    assert "761941" in result.reason


def test_dc_record_passes_when_consistent() -> None:
    result = validate_barcode_catalog_match(
        SUPERMAN_39_FULL,
        publisher="DC Comics",
        issue_number="39",
        year="2015",
    )
    assert result.status == "exact_match"


def test_dc_prefix_inferred_when_publisher_missing() -> None:
    result = validate_barcode_catalog_match(
        SUPERMAN_39_FULL,
        publisher=None,
        issue_number="39",
        year="2015",
    )
    assert result.status == "exact_match"


def test_issue_mismatch_rejected_even_for_dc() -> None:
    result = validate_barcode_catalog_match(
        SUPERMAN_39_FULL,
        publisher="DC Comics",
        issue_number="13",
        year="2015",
    )
    assert result.status == "no_safe_match"
    assert "#39" in result.reason


def test_modern_upc_rejected_for_prewar_year() -> None:
    result = validate_barcode_catalog_match(
        SUPERMAN_39_FULL,
        publisher="DC Comics",
        issue_number="39",
        year="1952",
    )
    assert result.status == "no_safe_match"


def test_marvel_prefix_requires_marvel_publisher() -> None:
    marvel_full = "75960608579600511"
    assert validate_barcode_catalog_match(
        marvel_full, publisher="DC Comics", issue_number="5", year="2016"
    ).status == "no_safe_match"
    assert validate_barcode_catalog_match(
        marvel_full, publisher="Marvel", issue_number="5", year="2016"
    ).status == "exact_match"


def test_unknown_prefix_does_not_enforce_publisher() -> None:
    # No known prefix rule -> publisher cannot be used to reject. Extension 00100 -> issue #1.
    result = validate_barcode_catalog_match(
        "12345678901200100",
        publisher="Whatever Publishing",
        issue_number="1",
        year="2000",
    )
    assert result.status == "exact_match"
