from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseImportRun, User
from test_inventory import auth_headers, register_and_login
from test_release_import import _sample_feed


def test_release_import_api_owner_scoped(client: TestClient) -> None:
    owner_email = "release-import-api@example.com"
    outsider_email = "release-import-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    json_response = client.post(
        "/api/v1/release-imports/json",
        headers=auth_headers(owner_token),
        json={"file_name": "feed.json", "feed": _sample_feed().model_dump(mode="json")},
    )
    assert json_response.status_code == 201, json_response.text
    run_id = json_response.json()["data"]["id"]

    csv_body = (
        "publisher,series_name,issue_number,title,release_date,cover_price\n"
        "Image,API CSV,2,API CSV #2,2026-10-01,4.99\n"
    )
    csv_response = client.post(
        "/api/v1/release-imports/csv",
        headers=auth_headers(owner_token),
        files={"file": ("api.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert csv_response.status_code == 201, csv_response.text

    runs = client.get("/api/v1/release-imports/runs", headers=auth_headers(owner_token))
    detail = client.get(f"/api/v1/release-imports/runs/{run_id}", headers=auth_headers(owner_token))
    errors = client.get("/api/v1/release-imports/errors", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/release-imports/dashboard", headers=auth_headers(owner_token))
    outsider_runs = client.get("/api/v1/release-imports/runs", headers=auth_headers(outsider_token))
    outsider_detail = client.get(f"/api/v1/release-imports/runs/{run_id}", headers=auth_headers(outsider_token))

    assert runs.status_code == 200
    assert detail.status_code == 200
    assert errors.status_code == 200
    assert dashboard.status_code == 200
    assert len(runs.json()["data"]["items"]) >= 2
    assert dashboard.json()["data"]["recent_imports"]
    assert outsider_runs.json()["data"]["items"] == []
    assert outsider_detail.status_code == 404

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        assert len(session.exec(select(ReleaseImportRun).where(ReleaseImportRun.owner_user_id == owner_user_id)).all()) >= 2
