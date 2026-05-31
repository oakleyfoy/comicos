from __future__ import annotations

import httpx
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, User
from app.services.lunar_authenticated_client import LunarAuthenticatedClient
from app.services.lunar_feed_import import import_latest_lunar_csv_from_remote, import_lunar_csv_bytes
from lunar_feed_test_helpers import MOCK_LOGIN_HTML, MOCK_RESOURCES_HTML, SAMPLE_CSV


def _mock_client() -> LunarAuthenticatedClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/login":
            return httpx.Response(200, text=MOCK_LOGIN_HTML)
        if request.url.path == "/account/login":
            return httpx.Response(200, text="ok")
        if request.url.path == "/home/resources":
            return httpx.Response(200, text=MOCK_RESOURCES_HTML)
        if request.url.path.endswith(".csv"):
            return httpx.Response(200, content=SAMPLE_CSV.encode("utf-8"))
        return httpx.Response(404)

    return LunarAuthenticatedClient(base_url="https://example.test", transport=httpx.MockTransport(handler))


def test_import_lunar_csv_upload(client, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    with Session(get_engine()) as session:
        owner = User(email="lunar-upload@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        summary = import_lunar_csv_bytes(
            session,
            owner_user_id=int(owner.id or 0),
            file_name="upload.csv",
            content_bytes=SAMPLE_CSV.encode("utf-8"),
        )
        assert summary.records_processed == 1
        assert summary.records_created > 0
        issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner.id)).all()
        assert len(issues) == 1


def test_import_latest_lunar_csv_from_remote(client, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    with Session(get_engine()) as session:
        owner = User(email="lunar-remote@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        summary = import_latest_lunar_csv_from_remote(
            session,
            owner_user_id=int(owner.id or 0),
            client=_mock_client(),
        )
        assert summary.source_type == "REMOTE"
        assert summary.file_period == "2026-06"
