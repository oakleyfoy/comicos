"""Deploy/endpoint/payload debug: build-info, stale candidate clearing, full-cover handoff."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

import app.services.intake_queue_service as svc
from app.models.asset_ledger import User
from app.models.intake_queue import (
    ITEM_NEEDS_FULL_COVER_PHOTO,
    ITEM_QUEUED,
    IntakeItemCandidate,
    IntakeSession,
    IntakeSessionItem,
)
from app.services.build_info_service import build_build_info
from starlette.datastructures import Headers, UploadFile


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _jpeg_bytes(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), color=(8, 8, 8)).save(buf, format="JPEG")
    return buf.getvalue()


def _upload(raw: bytes, name: str = "fullcover.jpg") -> UploadFile:
    return UploadFile(
        filename=name,
        file=BytesIO(raw),
        headers=Headers({"content-type": "image/jpeg"}),
    )


def _seed_item_with_candidates(session: Session, *, storage_path: str) -> IntakeSessionItem:
    session.add(User(id=1, email="o@example.com", password_hash="x"))
    session.commit()
    intake = IntakeSession(
        user_id=1,
        session_token="tok-debug",
        status="active",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add(intake)
    session.commit()
    item = IntakeSessionItem(
        session_id=int(intake.id),
        user_id=1,
        storage_path=storage_path,
        normalized_barcode="75960620629200111",
        status=ITEM_NEEDS_FULL_COVER_PHOTO,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    # Stale fingerprint candidates from the barcode-strip scan (e.g. Silver Surfer #84).
    for rank, series in enumerate(["Silver Surfer", "Superman: The Man of Steel", "Supergirl"]):
        session.add(
            IntakeItemCandidate(
                item_id=int(item.id),
                catalog_issue_id=1000 + rank,
                publisher="Marvel" if rank == 0 else "DC Comics",
                series=series,
                issue_number=str(84 - rank),
                score=70.0,
                source="fingerprint",
                rank=rank,
            )
        )
    session.commit()
    return item


def test_full_cover_upload_clears_stale_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = tmp_path / "scan.jpg"
    primary.write_bytes(_jpeg_bytes(900, 280))

    def _resolve(rel, **k):
        return primary

    monkeypatch.setattr(svc, "resolve_photo_import_storage_path", _resolve)
    monkeypatch.setattr(svc, "relative_path_under_repo_root", lambda p: Path(p).name)
    kicked: list[int] = []
    monkeypatch.setattr(svc, "run_intake_item_async", lambda item_id: kicked.append(item_id))

    engine = _engine()
    with Session(engine) as session:
        item = _seed_item_with_candidates(session, storage_path="scan.jpg")
        item_id = int(item.id)
        assert len(svc.candidates_for_item(session, item_id=item_id)) == 3

        result = asyncio.run(
            svc.attach_full_cover_photo_to_intake_item(
                session,
                item_id=item_id,
                owner_user_id=1,
                upload=_upload(_jpeg_bytes(800, 1200)),
            )
        )

        assert kicked == [item_id]
        assert result.status == ITEM_QUEUED
        # Stale barcode-strip candidates are gone.
        assert svc.candidates_for_item(session, item_id=item_id) == []
        # Full-cover path is recorded for the reprocess handoff.
        payload = json.loads(result.barcode_read_json)
        assert payload["full_cover_storage_path"]
        assert payload.get("needs_full_cover_photo") is None
        assert result.selected_catalog_issue_id is None


def test_stale_candidates_not_rendered_after_full_cover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = tmp_path / "scan.jpg"
    primary.write_bytes(_jpeg_bytes(900, 280))
    monkeypatch.setattr(svc, "resolve_photo_import_storage_path", lambda rel, **k: primary)
    monkeypatch.setattr(svc, "relative_path_under_repo_root", lambda p: Path(p).name)
    monkeypatch.setattr(svc, "run_intake_item_async", lambda item_id: None)

    from app.api.intake_queue import _item_to_read

    engine = _engine()
    with Session(engine) as session:
        item = _seed_item_with_candidates(session, storage_path="scan.jpg")
        item_id = int(item.id)
        asyncio.run(
            svc.attach_full_cover_photo_to_intake_item(
                session,
                item_id=item_id,
                owner_user_id=1,
                upload=_upload(_jpeg_bytes(800, 1200)),
            )
        )
        refreshed = session.get(IntakeSessionItem, item_id)
        read = _item_to_read(session, refreshed, token="tok-debug")
        assert read.candidates == []
        assert read.barcode_read is not None
        assert read.barcode_read.get("full_cover_storage_path")


def test_token_full_cover_endpoint_reprocesses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The phone hand-off endpoint authes by session token (no login) and requeues."""
    primary = tmp_path / "scan.jpg"
    primary.write_bytes(_jpeg_bytes(900, 280))
    monkeypatch.setattr(svc, "resolve_photo_import_storage_path", lambda rel, **k: primary)
    monkeypatch.setattr(svc, "relative_path_under_repo_root", lambda p: Path(p).name)
    kicked: list[int] = []
    monkeypatch.setattr(svc, "run_intake_item_async", lambda item_id: kicked.append(item_id))

    from app.api.intake_queue import session_full_cover_photo_endpoint

    engine = _engine()
    with Session(engine) as session:
        item = _seed_item_with_candidates(session, storage_path="scan.jpg")
        item_id = int(item.id)

        read = asyncio.run(
            session_full_cover_photo_endpoint(
                token="tok-debug",
                item_id=item_id,
                file=_upload(_jpeg_bytes(800, 1200)),
                session=session,
            )
        )

        assert kicked == [item_id]
        assert read.status == ITEM_QUEUED
        # Stale candidates cleared via the shared reprocess path.
        assert svc.candidates_for_item(session, item_id=item_id) == []


def test_token_full_cover_endpoint_rejects_foreign_item(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An item that does not belong to the token's session must 404."""
    from fastapi import HTTPException

    from app.api.intake_queue import session_full_cover_photo_endpoint

    engine = _engine()
    with Session(engine) as session:
        item = _seed_item_with_candidates(session, storage_path="scan.jpg")
        # Second session owned by a different token; its token can't touch the first item.
        other = IntakeSession(
            user_id=1,
            session_token="tok-other",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(other)
        session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                session_full_cover_photo_endpoint(
                    token="tok-other",
                    item_id=int(item.id),
                    file=_upload(_jpeg_bytes(800, 1200)),
                    session=session,
                )
            )
        assert exc.value.status_code == 404


def test_build_info_reports_feature_flags() -> None:
    from app.core.config import get_settings

    info = build_build_info(get_settings())
    flags = info["feature_flags"]
    assert set(flags) == {
        "full_cover_followup_enabled",
        "mobile_capture_enabled",
        "suppress_unsafe_fingerprint_enabled",
    }
    assert info["service"] == "comic-os-api"
    assert info["runtime"]
    assert "build_time" in info


def test_build_info_endpoint_exists() -> None:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.core.config import Settings, get_settings
    from app.schemas.debug import BuildInfoResponse

    app = FastAPI()

    @app.get("/api/ops/build-info", response_model=BuildInfoResponse)
    def _build_info(settings: Settings = Depends(get_settings)) -> BuildInfoResponse:
        return BuildInfoResponse(**build_build_info(settings))

    client = TestClient(app)
    resp = client.get("/api/ops/build-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "comic-os-api"
    assert "git_sha" in body
    assert body["feature_flags"]["mobile_capture_enabled"] in (True, False)
