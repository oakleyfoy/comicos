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
    expand_books_to_match_bboxes,
    grid_bboxes_for_count,
    is_full_frame_bbox,
    parse_books_from_ai_payload,
)


def test_parse_books_from_ai_payload_supports_multiple_keys() -> None:
    payload = {
        "books": [
            {"bbox": {"x": 0, "y": 0, "width": 0.2, "height": 0.5}, "series_guess": "A"},
            {"bounding_box": {"x": 0.2, "y": 0, "width": 0.2, "height": 0.5}, "series_guess": "B"},
        ]
    }
    books = parse_books_from_ai_payload(payload)
    assert len(books) == 2


def test_expand_books_to_match_bboxes_creates_six_from_one() -> None:
    bboxes = grid_bboxes_for_count(6)
    expanded = expand_books_to_match_bboxes([{"series_guess": "Merged"}], bboxes, reason="test")
    assert len(expanded) == 6
    assert not is_full_frame_bbox(expanded[0]["bbox"])


def test_run_ai_recognition_creates_six_detections_and_crops(tmp_path, monkeypatch) -> None:
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

    src = api_root / "data" / "photo_import" / "uploads" / "group.jpg"
    src.parent.mkdir(parents=True)
    Image.new("RGB", (1200, 800), color=(40, 40, 40)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    six_books = {
        "books": [
            {
                "bbox": {"x": i * 0.16, "y": 0.1, "width": 0.14, "height": 0.8},
                "series_guess": f"Series {i + 1}",
                "confidence": 0.7,
            }
            for i in range(6)
        ]
    }

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision", return_value=six_books):
        with Session(engine) as session:
            session.add(PhotoImportSession(id=1, user_id=1, session_token="t", expires_at=expires))
            session.add(
                PhotoImportImage(
                    id=10,
                    session_id=1,
                    user_id=1,
                    storage_path=rel_path,
                    mime_type="image/jpeg",
                    file_size=1,
                )
            )
            session.commit()
            run_ai_recognition_for_image(session, image_id=10)
            rows = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 10)).all()
            assert len(rows) == 6
            paths = {row.crop_path for row in rows}
            assert len(paths) == 6
            for row in rows:
                assert row.crop_path != rel_path


def test_group_photo_hard_guard_splits_one_full_frame_into_six(tmp_path, monkeypatch) -> None:
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

    src = api_root / "data" / "photo_import" / "group.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), color=(30, 30, 30)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    one_merged = {
        "books": [
            {
                "bbox": {"x": 0, "y": 0, "width": 1, "height": 1},
                "series_guess": "",
                "confidence": 0.05,
            }
        ]
    }

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision", return_value=one_merged):
        with mock.patch.object(ai_mod, "_call_openai_bbox_segmentation", return_value={"comic_count": 1, "bboxes": []}):
            with Session(engine) as session:
                session.add(PhotoImportSession(id=3, user_id=1, session_token="t3", expires_at=expires))
                session.add(
                    PhotoImportImage(
                        id=12,
                        session_id=3,
                        user_id=1,
                        storage_path=rel_path,
                        mime_type="image/jpeg",
                        file_size=1,
                    )
                )
                session.commit()
                run_ai_recognition_for_image(session, image_id=12)
                rows = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 12)).all()
                assert len(rows) == 6


def test_should_run_segmentation_when_multiple_books_share_full_frame() -> None:
    from app.services.photo_import_segmentation_service import should_run_bbox_segmentation

    books = [
        {"bbox": {"x": 0, "y": 0, "width": 1, "height": 1}, "series_guess": "A"},
        {"bbox": {"x": 0, "y": 0, "width": 1, "height": 1}, "series_guess": "B"},
    ]
    assert should_run_bbox_segmentation(books, image_width=1200, image_height=800) is True


def test_fallback_full_image_only_when_ai_unavailable(tmp_path, monkeypatch) -> None:
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

    src = api_root / "data" / "photo_import" / "solo.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 600), color=(10, 10, 10)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(
        ai_mod,
        "_call_openai_vision",
        side_effect=ai_mod.RecognitionConfigError("no key"),
    ):
        with Session(engine) as session:
            session.add(PhotoImportSession(id=2, user_id=1, session_token="t2", expires_at=expires))
            session.add(
                PhotoImportImage(
                    id=11,
                    session_id=2,
                    user_id=1,
                    storage_path=rel_path,
                    mime_type="image/jpeg",
                    file_size=1,
                )
            )
            session.commit()
            run_ai_recognition_for_image(session, image_id=11)
            rows = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 11)).all()
            assert len(rows) == 1
            assert is_full_frame_bbox(
                {
                    "x": rows[0].bbox_x,
                    "y": rows[0].bbox_y,
                    "width": rows[0].bbox_width,
                    "height": rows[0].bbox_height,
                }
            )
