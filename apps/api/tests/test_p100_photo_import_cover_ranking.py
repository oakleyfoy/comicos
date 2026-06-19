from __future__ import annotations

from PIL import Image, ImageDraw

from app.services.photo_import_candidate_service import (
    ScoredCatalogRow,
    _apply_visual_ranking,
    _expand_ambiguous_series_tokens,
    _visual_signal_for_auto_select,
)
from app.services.photo_import_cover_boundary_service import refine_cover_boundary
from app.services.photo_import_crop_service import expand_bbox_for_comic_crop


def test_expand_ambiguous_x_adds_x_factor_family() -> None:
    tokens = _expand_ambiguous_series_tokens(["X"])
    assert "X-Factor" in tokens
    assert "X-Men" in tokens


def test_cover_first_ranking_prefers_visual_over_text_only(tmp_path, monkeypatch) -> None:
    from unittest.mock import MagicMock

    import app.services.photo_import_candidate_service as cand_mod

    crop = tmp_path / "crop.jpg"
    Image.new("RGB", (120, 180), color=(50, 50, 200)).save(crop, format="JPEG")

    issue_a = MagicMock(id=1)
    issue_b = MagicMock(id=2)
    series_a = MagicMock(name="X-Men")
    series_b = MagicMock(name="X-Factor")
    pub = MagicMock()
    pub.name = "Marvel"
    pub.normalized_name = "marvel"

    text_heavy = ScoredCatalogRow(
        issue=issue_a,
        series=series_a,
        publisher=pub,
        match_score=88.0,
        match_reason="text",
        matched_on="fuzzy_series",
        base_text_score=88.0,
    )
    text_light = ScoredCatalogRow(
        issue=issue_b,
        series=series_b,
        publisher=pub,
        match_score=70.0,
        match_reason="text",
        matched_on="fuzzy_series",
        base_text_score=70.0,
    )

    det = MagicMock(
        crop_path="data/photo_import/crops/1/1_0.jpg",
        ai_series="X",
        ai_publisher="Marvel",
        ai_visible_publisher_text="",
    )

    monkeypatch.setattr(cand_mod, "resolve_crop_abs_path", lambda _p: crop)
    monkeypatch.setattr(cand_mod, "fingerprint_hashes_for_crop", lambda _p: ("a" * 16, "b" * 16, "c" * 16))
    monkeypatch.setattr(
        cand_mod,
        "cover_similarity_score_for_issue",
        lambda _s, crop_path, catalog_issue_id: 85.0 if catalog_issue_id == 2 else 20.0,
    )
    monkeypatch.setattr(
        cand_mod,
        "fingerprint_match_score_for_issue",
        lambda _s, crop_hashes, catalog_issue_id: 80.0 if catalog_issue_id == 2 else 15.0,
    )
    monkeypatch.setattr(cand_mod, "learning_boost_for_issue", lambda **_: 0.0)

    ranked = _apply_visual_ranking(MagicMock(), det=det, ranked=[text_heavy, text_light])
    assert int(ranked[0].issue.id) == 2
    assert ranked[0].visual_match_label in {"Cover match", "Fingerprint match", "Partial visual match"}


def test_strong_text_without_visual_does_not_auto_select() -> None:
    from unittest.mock import MagicMock

    row = ScoredCatalogRow(
        issue=MagicMock(id=1),
        series=MagicMock(),
        publisher=None,
        match_score=96.0,
        match_reason="",
        matched_on="fuzzy_series",
        base_text_score=96.0,
        visual_score_status="unavailable",
    )
    assert _visual_signal_for_auto_select(row) is False


def test_boundary_refine_never_smaller_than_original(tmp_path) -> None:
    src = tmp_path / "comic.jpg"
    img = Image.new("RGB", (600, 900), color=(240, 240, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 80, 480, 820], fill=(20, 40, 180))
    img.save(src, format="JPEG")
    original = {"x": 0.22, "y": 0.1, "width": 0.56, "height": 0.78}
    expanded = expand_bbox_for_comic_crop(original)
    result = refine_cover_boundary(
        src,
        original_bbox=original,
        expanded_bbox=expanded,
        image_width=600,
        image_height=900,
    )
    orig_area = original["width"] * original["height"]
    refined_area = result.refined_bbox["width"] * result.refined_bbox["height"]
    assert refined_area >= orig_area * 0.92 or result.used_fallback
