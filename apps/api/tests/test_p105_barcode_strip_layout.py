"""Wide barcode-strip photos (not full covers) should still allow supplement OCR."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.p105_comic_barcode_regions import (
    compute_barcode_region_geometry,
    is_likely_barcode_strip,
)
from app.services.p105_comic_barcode_read_service import read_comic_barcode_from_image_bytes


def test_is_likely_barcode_strip() -> None:
    assert is_likely_barcode_strip(1024, 291)
    assert not is_likely_barcode_strip(800, 1200)


def test_strip_geometry_allows_supplement_ocr() -> None:
    img = Image.new("RGB", (1024, 291), color=(210, 210, 210))
    geometry = compute_barcode_region_geometry(img)
    assert geometry.supplement_ocr_allowed is True
    assert geometry.geometry_failed is False


def test_known_main_upc_enables_ocr_path_on_user_strip() -> None:
    candidates = [
        Path(__file__).resolve().parents[3]
        / ".cursor/projects/c-comic-os-p41-feed/assets/"
        "c__Users_shell_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
        "image-1d9dc94d-491b-4a9b-9a24-90aeec1a5bcd.png",
        Path(
            r"C:\Users\shell\.cursor\projects\c-comic-os-p41-feed\assets"
            r"\c__Users_shell_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
            r"image-1d9dc94d-491b-4a9b-9a24-90aeec1a5bcd.png"
        ),
    ]
    asset = next((p for p in candidates if p.is_file()), None)
    if asset is None:
        return
    result = read_comic_barcode_from_image_bytes(
        asset.read_bytes(),
        known_main_upc="761568002140",
        log_context="test_strip",
    )
    assert result.main_upc == "761568002140"
    # Without vision API key supplement may stay empty; OCR path must have run (not skipped at geometry).
    assert "barcode strip" in " ".join(
        str(result.region_ocr_debug.get("geometry", {}).get("notes", ""))
        if isinstance(result.region_ocr_debug, dict)
        else ""
    ).lower() or result.review_reason != "barcode_not_detected"
