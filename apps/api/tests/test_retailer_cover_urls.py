from app.services.retailer_sync.retailer_cover_urls import (
    absolutize_retailer_image_url,
    dcbs_product_code_cover_url,
    resolve_retailer_cover_url,
)

_DCBS_MEDIA = "https://media.dcbservice.com/small/MAY265025.jpg"


def test_absolutize_dcbs_cover_path() -> None:
    url = absolutize_retailer_image_url("/files/MAY265025.jpg", "dcbs")
    assert url == _DCBS_MEDIA


def test_dcbs_product_code_cover_url() -> None:
    assert dcbs_product_code_cover_url("may265025") == _DCBS_MEDIA


def test_resolve_cover_from_parse_diagnostics() -> None:
    raw = {
        "retailer_item_id": "MAY265025",
        "image_url": "/files/MAY265025.jpg",
        "parse_diagnostics": {"remote_dcbs_image_url": "https://www.dcbservice.com/files/MAY265025.jpg"},
    }
    assert resolve_retailer_cover_url(raw, retailer="dcbs") == _DCBS_MEDIA


def test_resolve_dcbs_cover_from_retailer_item_id_only() -> None:
    raw = {"retailer_item_id": "MAY264642"}
    assert resolve_retailer_cover_url(raw, retailer="dcbs") == (
        "https://media.dcbservice.com/small/MAY264642.jpg"
    )
