from __future__ import annotations

from PIL import Image

from app.services.photo_import_crop_service import extract_and_save_crop, resolve_crop_abs_path


def test_extract_and_save_crop_writes_file(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_crop_service as crop_mod

    monkeypatch.setattr(crop_mod, "REPO_ROOT", tmp_path)
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (200, 300), color=(10, 20, 30)).save(src, format="JPEG")
    rel = extract_and_save_crop(
        src,
        {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6},
        session_id=9,
        image_id=3,
        idx=0,
    )
    abs_path = resolve_crop_abs_path(rel)
    assert abs_path is not None
    assert abs_path.is_file()
    with Image.open(abs_path) as cropped:
        assert cropped.width > 0
        assert cropped.height > 0
