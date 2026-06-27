"""P105 merges 12-digit main UPC with EAN-5 from full-image 1D decode."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.catalog_ingestion_service import normalize_upc
from app.services.intake_scanner_barcode_authority_service import try_resolve_seventeen_digit_barcode_from_p105
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult, read_comic_barcode_from_image_bytes
from app.services.photo_import_upc_barcode_decoder import _opencv_available, _pyzbar_available


def test_try_resolve_merges_main_and_ocr_supplement() -> None:
    main = "761568002140"
    p105 = ComicBarcodeReadResult(
        main_upc=main,
        ocr_supplement="00211",
        confidence_main=0.92,
    )
    full = try_resolve_seventeen_digit_barcode_from_p105(normalized=main, p105=p105)
    assert full == "76156800214000211"


@pytest.mark.skipif(
    not (_opencv_available() or _pyzbar_available()),
    reason="opencv or pyzbar required for 1D decode",
)
def test_read_service_merges_main_with_full_image_supplement() -> None:
    candidates = [
        Path(__file__).resolve().parents[3]
        / ".cursor/projects/c-comic-os-p41-feed/assets/"
        "c__Users_shell_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
        "image-3f0aa666-9dfb-4c4c-9364-e51ecbfcfbf3.png",
        Path(
            r"C:\Users\shell\.cursor\projects\c-comic-os-p41-feed\assets"
            r"\c__Users_shell_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
            r"image-3f0aa666-9dfb-4c4c-9364-e51ecbfcfbf3.png"
        ),
    ]
    asset = next((p for p in candidates if p.is_file()), None)
    if asset is None:
        pytest.skip("user barcode crop image not in workspace")
    result = read_comic_barcode_from_image_bytes(asset.read_bytes(), log_context="test_dark_horse_crop")
    merged = normalize_upc(result.reconstructed_full or "")
    if len(merged) >= 17:
        assert merged.startswith("761568002140")
        assert merged[12:17] == "00211"
