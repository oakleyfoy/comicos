"""P88 marketplace URL validation tests."""

from app.services.marketplace.url_validation import validate_marketplace_url


def test_valid_ebay_url() -> None:
    result = validate_marketplace_url("https://www.ebay.com/itm/1234567890")
    assert result.is_valid is True
    assert result.marketplace == "EBAY"
    assert result.normalized_url is not None


def test_rejects_http() -> None:
    result = validate_marketplace_url("http://www.ebay.com/itm/1")
    assert result.is_valid is False
    assert result.error_message


def test_rejects_unknown_host() -> None:
    result = validate_marketplace_url("https://evil.example.com/listing")
    assert result.is_valid is False
