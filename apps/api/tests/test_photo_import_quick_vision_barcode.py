"""Quick (streaming) vision read runs barcode extraction after GPT parse."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.models.photo_import import PhotoImportImage, PhotoImportSession
from app.services.comic_vision_read_mode import ComicVisionReadMode
from app.services.photo_import_vision_sandbox_service import VisionSandboxReadResult


def test_quick_vision_stream_applies_barcode_extraction(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod
    from app.services.photo_import_vision_stream_service import iter_vision_read_sse

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.core.config import get_settings

    get_settings.cache_clear()

    src = api_root / "photo.jpg"
    Image.new("RGB", (100, 150), color=(1, 2, 3)).save(src, format="JPEG")
    rel = str(src.relative_to(api_root)).replace("\\", "/")

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    fake_result = VisionSandboxReadResult(
        publisher="DC",
        series="Superman",
        issue_number="39",
        issue_title="",
        variant_description="",
        year="2018",
        cover_date="",
        barcode="",
        confidence=0.9,
        reasoning="Issue 39 visible",
        possible_alternates=[],
        raw_response={},
        raw_response_text="{}",
    )

    enrich = mock.Mock()
    parsed = {"comics": [{"publisher": "DC", "series": "Superman", "issue_number": "39", "confidence": 0.9}]}

    with Session(engine) as session:
        session.add(
            PhotoImportSession(
                id=1,
                user_id=1,
                session_token="tok",
                expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            )
        )
        session.add(
            PhotoImportImage(
                id=5,
                session_id=1,
                user_id=1,
                storage_path=rel,
                mime_type="image/jpeg",
                file_size=1,
            )
        )
        session.commit()

        with mock.patch(
            "app.services.photo_import_vision_stream_service.stream_comic_vision_text",
            return_value=iter(['{"comics":[]}']),
        ):
            with mock.patch(
                "app.services.photo_import_vision_stream_service.parse_streamed_json_content",
                return_value=parsed,
            ):
                with mock.patch(
                    "app.services.photo_import_vision_sandbox_service._parse_sandbox_payload",
                    return_value=fake_result,
                ):
                    with mock.patch(
                        "app.services.photo_import_vision_sandbox_service.enrich_vision_results_with_barcode",
                        enrich,
                    ) as enrich_mod:
                        events = list(
                            iter_vision_read_sse(
                                session,
                                image_id=5,
                                mode=ComicVisionReadMode.QUICK,
                                force=True,
                            )
                        )

    enrich_mod.assert_called_once()
    args, kwargs = enrich_mod.call_args
    assert kwargs.get("image_id") == 5
    assert kwargs.get("allow_gpt_barcode_fallback") is True
    assert any("done" in e for e in events)

    get_settings.cache_clear()
