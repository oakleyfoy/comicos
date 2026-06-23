from __future__ import annotations

import io

import pytest

from app.services.catalog_ingestion_service import upc_check_digit_valid
from app.services.photo_import_upc_barcode_decoder import (
    _collect_valid_upc,
    _opencv_available,
    decode_upc_from_image_bytes,
)


def test_collect_valid_upc() -> None:
    assert _collect_valid_upc(["649857003921", "761941343730"]) == "761941343730"


@pytest.mark.skipif(not _opencv_available(), reason="opencv barcode detector not installed")
def test_decode_generated_upca() -> None:
    barcode = pytest.importorskip("barcode")
    from barcode.writer import ImageWriter

    buf = io.BytesIO()
    barcode.get("upca", "761941343730", writer=ImageWriter()).write(buf)
    hit = decode_upc_from_image_bytes(buf.getvalue())
    assert hit is not None
    code, _source = hit
    assert upc_check_digit_valid(code)
    assert code.endswith("343730") or code == "761941343730"
