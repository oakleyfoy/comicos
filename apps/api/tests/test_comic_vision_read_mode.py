"""Quick vs accurate comic vision profiles."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.core.config import get_settings
from app.services.comic_vision_read_mode import ComicVisionReadMode, normalize_vision_read_mode, resolve_vision_profile
from app.services.gpt_comic_vision_client import prepare_image_bytes_for_vision


def test_normalize_vision_read_mode_defaults_quick() -> None:
    assert normalize_vision_read_mode(None) == ComicVisionReadMode.QUICK
    assert normalize_vision_read_mode("quick") == ComicVisionReadMode.QUICK
    assert normalize_vision_read_mode("accurate") == ComicVisionReadMode.ACCURATE


def test_resolve_vision_profile_quick_uses_mini_and_low_detail() -> None:
    settings = get_settings()
    profile = resolve_vision_profile(settings, ComicVisionReadMode.QUICK)
    assert profile["model"] == settings.photo_import_quick_vision_model
    assert profile["image_detail"] == settings.photo_import_quick_image_detail
    assert int(profile["max_image_side_px"]) == settings.photo_import_quick_max_image_side_px


def test_prepare_image_shrinks_large_photo() -> None:
    img = Image.new("RGB", (3000, 4000), color=(20, 20, 20))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    raw = buf.getvalue()
    out = prepare_image_bytes_for_vision(raw, max_side_px=1280)
    with Image.open(BytesIO(out)) as resized:
        assert max(resized.size) <= 1280
    assert len(out) < len(raw)
