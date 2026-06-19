from __future__ import annotations

from PIL import Image

from app.services.photo_import_crop_service import (
    expand_bbox_for_comic_crop,
    extract_and_save_crop,
    resolve_crop_abs_path,
)


def _pixel_area(image_path, bbox: dict[str, float]) -> int:
    with Image.open(image_path) as img:
        w, h = img.size
        x = int(bbox["x"] * w)
        y = int(bbox["y"] * h)
        bw = max(1, int(bbox["width"] * w))
        bh = max(1, int(bbox["height"] * h))
        return bw * bh


def test_expand_bbox_increases_crop_area(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_crop_service as crop_mod

    monkeypatch.setattr(crop_mod, "REPO_ROOT", tmp_path)
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (1000, 800), color=(10, 20, 30)).save(src, format="JPEG")
    raw = {"x": 0.4, "y": 0.2, "width": 0.2, "height": 0.5}
    expanded = expand_bbox_for_comic_crop(raw)
    assert _pixel_area(src, expanded) > _pixel_area(src, raw)


def test_expanded_bbox_stays_inside_image() -> None:
    expanded = expand_bbox_for_comic_crop({"x": 0.0, "y": 0.0, "width": 0.25, "height": 0.8})
    assert expanded["x"] >= 0.0
    assert expanded["y"] >= 0.0
    assert expanded["x"] + expanded["width"] <= 1.0 + 1e-9
    assert expanded["y"] + expanded["height"] <= 1.0 + 1e-9


def test_portrait_aspect_correction_widens_narrow_bbox() -> None:
    narrow = {"x": 0.45, "y": 0.1, "width": 0.1, "height": 0.8}
    expanded = expand_bbox_for_comic_crop(narrow)
    assert expanded["width"] > narrow["width"]


def test_edge_bbox_does_not_fail(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_crop_service as crop_mod

    monkeypatch.setattr(crop_mod, "REPO_ROOT", tmp_path)
    src = tmp_path / "edge.jpg"
    Image.new("RGB", (400, 600), color=(255, 255, 255)).save(src, format="JPEG")
    result = extract_and_save_crop(
        src,
        {"x": 0.0, "y": 0.05, "width": 0.18, "height": 0.9},
        session_id=1,
        image_id=2,
        idx=0,
    )
    assert resolve_crop_abs_path(result.relative_path) is not None
    assert result.width > 0 and result.height > 0
    assert result.expanded_bbox["x"] >= 0.0


def test_extract_and_save_crop_writes_file(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_crop_service as crop_mod

    monkeypatch.setattr(crop_mod, "REPO_ROOT", tmp_path)
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (200, 300), color=(10, 20, 30)).save(src, format="JPEG")
    result = extract_and_save_crop(
        src,
        {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6},
        session_id=9,
        image_id=3,
        idx=0,
    )
    abs_path = resolve_crop_abs_path(result.relative_path)
    assert abs_path is not None
    assert abs_path.is_file()
    assert result.width > 0 and result.height > 0
    assert result.crop_quality in {"good", "warning", "poor"}
