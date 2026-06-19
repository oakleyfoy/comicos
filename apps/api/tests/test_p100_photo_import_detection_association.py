from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.photo_import import PhotoImportDetectedBook, PhotoImportImage, PhotoImportSession
from app.services.photo_import_ai_recognition_service import run_ai_recognition_for_image
from app.services.photo_import_segmentation_service import (
    combine_books_with_bboxes,
    expand_books_to_match_bboxes,
)


def _book(series: str, x: float) -> dict:
    return {
        "series_guess": series,
        "visible_title_text": series,
        "bbox": {"x": x, "y": 0.05, "width": 0.28, "height": 0.9},
        "confidence": 0.8,
    }


def _three_column_bboxes() -> list[dict[str, float]]:
    return [
        {"x": 0.0, "y": 0.0, "width": 0.33, "height": 1.0},
        {"x": 0.33, "y": 0.0, "width": 0.34, "height": 1.0},
        {"x": 0.67, "y": 0.0, "width": 0.33, "height": 1.0},
    ]


def test_combine_books_with_bboxes_pairs_by_spatial_order_not_ai_list_order() -> None:
    """AI list order shuffled; each book carries its own bbox at the correct column."""
    books = [
        _book("Foolkiller", 0.66),
        _book("Captain America", 0.02),
        _book("Babe", 0.34),
    ]
    bboxes = _three_column_bboxes()
    combined = combine_books_with_bboxes(books, bboxes, reason="test")
    assert [c["series_guess"] for c in combined] == [
        "Captain America",
        "Babe",
        "Foolkiller",
    ]
    for entry in combined:
        cx = entry["bbox"]["x"] + entry["bbox"]["width"] / 2
        series = entry["series_guess"]
        if series == "Captain America":
            assert entry["bbox"]["x"] < 0.34
        elif series == "Babe":
            assert 0.32 <= entry["bbox"]["x"] < 0.67
        else:
            assert entry["bbox"]["x"] >= 0.67


def test_captain_america_crop_not_paired_with_foolkiller_metadata() -> None:
    books = [
        _book("Foolkiller", 0.66),
        _book("Captain America", 0.02),
        _book("Babe", 0.34),
    ]
    expanded = expand_books_to_match_bboxes(books, _three_column_bboxes(), reason="test")
    leftmost = min(expanded, key=lambda e: e["bbox"]["x"])
    assert leftmost["series_guess"] == "Captain America"
    assert leftmost["series_guess"] != "Foolkiller"


def test_run_ai_recognition_keeps_series_with_matching_bbox(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_ai_recognition_service as ai_mod
    import app.services.photo_import_crop_service as crop_mod
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setattr(storage_mod, "LEGACY_APPS_ROOT", tmp_path / "apps")
    monkeypatch.setattr(storage_mod, "PHOTO_IMPORT_ROOT", api_root / "data" / "photo_import")
    monkeypatch.setattr(crop_mod, "REPO_ROOT", api_root)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    src = api_root / "data" / "photo_import" / "1" / "7" / "strip.jpg"
    src.parent.mkdir(parents=True)
    canvas = Image.new("RGB", (900, 300))
    colors = [(200, 0, 0), (0, 0, 200), (0, 180, 0)]
    for i, color in enumerate(colors):
        patch = Image.new("RGB", (300, 300), color=color)
        canvas.paste(patch, (i * 300, 0))
    canvas.save(src, format="JPEG")
    rel = "data/photo_import/1/7/strip.jpg"

    payload = {
        "books": [
            _book("Foolkiller", 0.66),
            _book("Captain America", 0.02),
            _book("Babe", 0.34),
        ]
    }

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision", return_value=payload):
        with Session(engine) as session:
            session.add(PhotoImportSession(id=7, user_id=1, session_token="t7", expires_at=expires))
            session.add(
                PhotoImportImage(
                    id=70,
                    session_id=7,
                    user_id=1,
                    storage_path=rel,
                    mime_type="image/jpeg",
                    file_size=1,
                    width=900,
                    height=300,
                )
            )
            session.commit()
            run_ai_recognition_for_image(session, image_id=70)
            rows = session.exec(
                select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 70)
            ).all()
            assert len(rows) == 3
            rows_by_x = sorted(rows, key=lambda r: float(r.bbox_x))
            assert rows_by_x[0].ai_series == "Captain America"
            assert rows_by_x[1].ai_series == "Babe"
            assert rows_by_x[2].ai_series == "Foolkiller"
            assert rows_by_x[0].ai_series != "Foolkiller"
