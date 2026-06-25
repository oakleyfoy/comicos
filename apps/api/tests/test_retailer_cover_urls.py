from app.services.retailer_sync.retailer_cover_urls import absolutize_retailer_image_url, resolve_retailer_cover_url


def test_absolutize_dcbs_cover_path() -> None:
    url = absolutize_retailer_image_url("/files/MAY265025.jpg", "dcbs")
    assert url == "https://www.dcbservice.com/files/MAY265025.jpg"


def test_resolve_cover_from_parse_diagnostics() -> None:
    raw = {
        "image_url": "/files/MAY265025.jpg",
        "parse_diagnostics": {"remote_dcbs_image_url": "https://www.dcbservice.com/files/MAY265025.jpg"},
    }
    assert resolve_retailer_cover_url(raw, retailer="dcbs") == "https://www.dcbservice.com/files/MAY265025.jpg"
